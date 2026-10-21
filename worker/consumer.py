"""
Kafka consumer для worker-сервиса.
Читает задачи из топика apply-jobs, запускает autoclicker, публикует результаты.
"""
import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import Dict, Any, List

from kafka import KafkaConsumer, KafkaProducer
from cryptography.fernet import Fernet

# Добавляем директорию worker в sys.path для импорта модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import get_module_logger
from utils.db_utils import (
    get_db_connection,
    update_job_status,
    is_already_applied,
    save_apply_result,
)
from core.session_manager import SessionManager
from core.auth_module import AuthModule
from core.search_module import SearchModule
from core.recommendations_module import RecommendationsModule
from core.apply_module import ApplyModule
from core.resume_module import ResumeModule

logger = get_module_logger(__name__)


class JobConsumer:
    def __init__(self):
        self.bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self.topic_jobs = os.environ.get("KAFKA_TOPIC_JOBS", "apply-jobs")
        self.topic_results = os.environ.get("KAFKA_TOPIC_RESULTS", "apply-results")

        self.consumer = KafkaConsumer(
            self.topic_jobs,
            bootstrap_servers=self.bootstrap_servers,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            group_id="worker-group",
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        self.producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )

        self.session_manager = None
        self.auth_module = None
        self.search_module = None
        self.recommendations_module = None
        self.apply_module = None
        self.resume_module = None

        # Мультипользовательское состояние текущей браузерной сессии
        self._current_user_id = None
        self._current_login = None

        fernet_key = os.environ.get("FERNET_KEY")
        if not fernet_key:
            raise ValueError("Переменная окружения FERNET_KEY не задана")
        self.fernet = Fernet(fernet_key.encode())

        logger.info(f"JobConsumer инициализирован, слушает топик {self.topic_jobs}")

    def set_session_manager(self, session_manager: SessionManager):
        """Привязать готовый SessionManager и инициализировать модули.

        Auth/Search/Apply/Resume принимают SessionManager;
        Recommendations исторически принимает driver.
        """
        self.session_manager = session_manager
        driver = session_manager.get_driver()
        self.auth_module = AuthModule(session_manager)
        self.search_module = SearchModule(session_manager)
        self.recommendations_module = RecommendationsModule(driver)
        self.apply_module = ApplyModule(session_manager)
        self.resume_module = ResumeModule(session_manager)

    def init_browser_modules(self):
        """Создать SessionManager и модули, если они ещё не созданы."""
        if not self.session_manager:
            self.session_manager = SessionManager()
        self.set_session_manager(self.session_manager)

    def decrypt_password(self, encrypted_password: str) -> str:
        try:
            return self.fernet.decrypt(encrypted_password.encode()).decode()
        except Exception as e:
            logger.error(f"Ошибка расшифровки пароля: {e}")
            raise

    @staticmethod
    def _urls_to_vacancies(urls: List[str]) -> List[Dict[str, str]]:
        """Преобразовать список URL вакансий в список словарей."""
        result = []
        for url in urls:
            match = re.search(r"/vacancy/(\d+)", url)
            if match:
                result.append({
                    "id": match.group(1),
                    "url": url,
                    "title": "",
                    "company": "",
                })
        return result

    def _ensure_logged_in(self, user_id: str, hh_login: str, hh_password_enc: str):
        """Гарантировать, что браузер залогинен под указанным пользователем.

        Модель «одна сессия браузера, много пользователей»:
        - если текущий user_id совпадает — ничего не делаем;
        - при смене пользователя сохраняем cookies предыдущего, чистим cookies,
          переключаем SessionManager и пробуем восстановить сессию из
          sessions/{user_id}.pkl;
        - если сохранённая сессия невалидна — свежий логин через AuthModule.
        """
        user_id = str(user_id)

        if self._current_user_id == user_id:
            return

        # Расшифровка пароля может упасть, если Fernet-ключ не совпадает —
        # даём понятный текст ошибки для UI.
        try:
            hh_password = self.decrypt_password(hh_password_enc)
        except Exception:
            raise RuntimeError(
                "Не удалось расшифровать пароль hh.ru (проверьте FERNET_KEY). "
                "Сохраните пароль заново в настройках."
            )

        driver = self.session_manager.get_driver()

        if self._current_user_id is not None:
            logger.info(
                f"Смена пользователя: {self._current_login or self._current_user_id} -> {hh_login}"
            )
            # Сохраняем cookies предыдущего пользователя (в его же файл)
            self.session_manager.save_session()
            driver.get("https://hh.ru/")
            driver.delete_all_cookies()

        self.session_manager.set_user(user_id)

        # Пробуем восстановить сохранённую сессию нового пользователя
        driver.get("https://hh.ru/")
        if self.session_manager.restore_session():
            if self.auth_module.check_auth_status():
                logger.info(f"Сессия восстановлена для {hh_login}")
                self._current_user_id = user_id
                self._current_login = hh_login
                return

        logger.info(f"Авторизация под {hh_login}...")
        ok = self.auth_module.login({"username": hh_login, "password": hh_password})
        if not ok or not self.auth_module.check_auth_status():
            raise RuntimeError(
                f"Неверный логин или пароль hh.ru ({hh_login}), либо hh.ru "
                "запросил подтверждение (CAPTCHA). Проверьте учётные данные "
                "в настройках."
            )
        self.session_manager.save_session()
        self._current_user_id = user_id
        self._current_login = hh_login
        logger.info(f"Авторизован под {hh_login}")

    def _is_cancel_requested(self, job_id: str) -> bool:
        """Проверить флаг запроса остановки задачи (ставится API /jobs/{id}/stop)."""
        try:
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT status, filters FROM jobs WHERE id = %s", (job_id,))
                    row = cur.fetchone()
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Ошибка при проверке флага остановки задачи {job_id}: {e}")
            return False
        if not row:
            return True  # задача удалена — останавливаемся
        status_val, filters = row[0], row[1]
        if status_val == "cancelled":
            return True
        if isinstance(filters, str):
            try:
                filters = json.loads(filters)
            except ValueError:
                filters = {}
        return bool((filters or {}).get("_cancel_requested"))

    def process_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        job_id = job_data["job_id"]
        user_id = job_data["user_id"]
        mode = job_data["mode"]
        hh_login = job_data["hh_login"]
        hh_password_enc = job_data["hh_password_enc"]
        resume_id = job_data.get("resume_id")
        cover_letter = job_data.get("cover_letter", "")
        filters = job_data.get("filters") or {}
        rate_limit = job_data.get("rate_limit", 20)
        delay_range = job_data.get("delay_range", [1, 3])
        vacancy_urls = job_data.get("vacancy_urls", [])

        conn = get_db_connection()

        # Задача могла быть отменена (pending → cancelled), пока лежала в очереди Kafka.
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM jobs WHERE id = %s", (job_id,))
            row = cur.fetchone()
        if not row or row[0] != "pending":
            current_status = row[0] if row else "удалена"
            logger.info(
                f"Задача {job_id} пропущена: статус '{current_status}' (не pending)"
            )
            conn.close()
            return {
                "job_id": job_id,
                "user_id": user_id,
                "status": current_status if row else "cancelled",
                "applies": [],
                "total_sent": 0,
                "total_skipped": 0,
                "total_errors": 0,
                "finished_at": datetime.utcnow().isoformat() + "Z",
            }

        update_job_status(conn, job_id, "running")

        # Логин «под задачу»: один Chromium, много пользователей.
        if not self.session_manager:
            self.init_browser_modules()
        self._ensure_logged_in(user_id, hh_login, hh_password_enc)

        applies: List[Dict[str, Any]] = []
        total_sent = 0
        total_skipped = 0
        total_errors = 0

        try:
            if mode == "auto":
                vacancy_url_list = self.search_module.search_vacancies(filters)
                vacancies = self._urls_to_vacancies(vacancy_url_list)
            elif mode == "recommendations":
                vacancies = self.recommendations_module.parse_recommendations(
                    resume_id, max_pages=5
                )
            elif mode == "manual":
                vacancies = self._urls_to_vacancies(vacancy_urls)
            else:
                raise ValueError(f"Неизвестный режим: {mode}")

            cancelled = False
            for vacancy in vacancies[:rate_limit]:
                # Проверка запроса остановки перед каждым откликом.
                if self._is_cancel_requested(job_id):
                    logger.info(f"Задача {job_id} остановлена по запросу пользователя")
                    update_job_status(conn, job_id, "cancelled")
                    cancelled = True
                    break

                result = self._process_single_vacancy(
                    conn, job_id, user_id, vacancy, resume_id, cover_letter, delay_range
                )
                applies.append(result)
                if result["status"] == "sent":
                    total_sent += 1
                elif result["status"] == "skipped":
                    total_skipped += 1
                else:
                    total_errors += 1

            if cancelled:
                final_status = "cancelled"
            else:
                update_job_status(conn, job_id, "done")
                final_status = "done"

            return {
                "job_id": job_id,
                "user_id": user_id,
                "status": final_status,
                "applies": applies,
                "total_sent": total_sent,
                "total_skipped": total_skipped,
                "total_errors": total_errors,
                "finished_at": datetime.utcnow().isoformat() + "Z",
            }

        except Exception as e:
            logger.error(f"Ошибка при обработке задачи {job_id}: {e}")
            update_job_status(conn, job_id, "failed")

            return {
                "job_id": job_id,
                "user_id": user_id,
                "status": "failed",
                "applies": applies,
                "total_sent": total_sent,
                "total_skipped": total_skipped,
                "total_errors": total_errors,
                "finished_at": datetime.utcnow().isoformat() + "Z",
                "error": str(e),
            }
        finally:
            conn.close()

    def _process_single_vacancy(
        self, conn, job_id, user_id, vacancy, resume_id, cover_letter, delay_range
    ) -> Dict[str, Any]:
        vacancy_id = str(vacancy.get("id", ""))
        vacancy_url = vacancy.get("url", "")
        vacancy_title = vacancy.get("title", "")
        company = vacancy.get("company", "")

        if is_already_applied(conn, user_id, vacancy_id):
            result = {
                "vacancy_id": vacancy_id,
                "vacancy_url": vacancy_url,
                "vacancy_title": vacancy_title,
                "company": company,
                "status": "skipped",
                "error_msg": "Already applied",
            }
            save_apply_result(conn, job_id, user_id, result)
            return result

        try:
            success = self.apply_module.apply_to_vacancy(
                vacancy_url,
                cover_letter=cover_letter,
                resume_id=resume_id or "",
                delay_min=float(delay_range[0]),
                delay_max=float(delay_range[1]),
            )
            result = {
                "vacancy_id": vacancy_id,
                "vacancy_url": vacancy_url,
                "vacancy_title": vacancy_title,
                "company": company,
                "status": "sent" if success else "error",
                "error_msg": None if success else "Кнопка отклика не найдена или отклик не отправлен",
            }
        except Exception as e:
            logger.error(f"Ошибка при отклике на вакансию {vacancy_id}: {e}")
            result = {
                "vacancy_id": vacancy_id,
                "vacancy_url": vacancy_url,
                "vacancy_title": vacancy_title,
                "company": company,
                "status": "error",
                "error_msg": str(e),
            }

        save_apply_result(conn, job_id, user_id, result)
        return result

    def publish_result(self, result: Dict[str, Any]):
        try:
            self.producer.send(self.topic_results, result)
            self.producer.flush()
            logger.info(
                f"Результат задачи {result['job_id']} опубликован в {self.topic_results}"
            )
        except Exception as e:
            logger.error(f"Ошибка при публикации результата: {e}")

    def run(self):
        logger.info("Запуск consumer...")
        try:
            for message in self.consumer:
                job_data = message.value
                logger.info(
                    f"Задача {job_data['job_id']} от user_id={job_data['user_id']} "
                    f"(mode={job_data['mode']})"
                )
                result = self.process_job(job_data)
                self.publish_result(result)
        except KeyboardInterrupt:
            logger.info("Consumer остановлен по сигналу")
        except Exception as e:
            logger.error(f"Критическая ошибка в consumer: {e}")
        finally:
            self.consumer.close()
            self.producer.close()
            if self.session_manager:
                self.session_manager.close()


if __name__ == "__main__":
    consumer = JobConsumer()
    consumer.run()
