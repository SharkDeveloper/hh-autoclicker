"""
Kafka consumer для worker-сервиса.
Читает задачи из топика apply-jobs, запускает autoclicker, публикует результаты.
"""
import json
import logging
import os
import sys
from typing import Dict, Any, List
from kafka import KafkaConsumer, KafkaProducer
from cryptography.fernet import Fernet

# Добавляем родительскую директорию в путь для импорта модулей worker
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import get_logger
from utils.db_utils import get_db_connection, update_job_status, is_already_applied, save_apply_result
from core.session_manager import SessionManager
from core.auth_module import AuthModule
from core.search_module import SearchModule
from core.recommendations_module import RecommendationsModule
from core.apply_module import ApplyModule
from core.resume_module import ResumeModule

logger = get_logger(__name__)


class JobConsumer:
    def __init__(self):
        self.bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self.topic_jobs = os.environ.get("KAFKA_TOPIC_JOBS", "apply-jobs")
        self.topic_results = os.environ.get("KAFKA_TOPIC_RESULTS", "apply-results")
        
        # Инициализация Kafka consumer и producer
        self.consumer = KafkaConsumer(
            self.topic_jobs,
            bootstrap_servers=self.bootstrap_servers,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            group_id="worker-group",
            auto_offset_reset='earliest',
            enable_auto_commit=True
        )
        self.producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # Инициализация модулей браузера (будут созданы позже)
        self.session_manager = None
        self.auth_module = None
        self.search_module = None
        self.recommendations_module = None
        self.apply_module = None
        self.resume_module = None
        
        # Fernet для расшифровки пароля
        fernet_key = os.environ.get("FERNET_KEY")
        if not fernet_key:
            raise ValueError("FERNET_KEY environment variable is not set")
        self.fernet = Fernet(fernet_key.encode())
        
        logger.info(f"JobConsumer инициализирован, слушает топик {self.topic_jobs}")
    
    def init_browser_modules(self):
        """Инициализировать модули браузера (вызывается после авторизации)."""
        if not self.session_manager:
            self.session_manager = SessionManager()
            driver = self.session_manager.get_driver()
            
            self.auth_module = AuthModule(driver)
            self.search_module = SearchModule(driver)
            self.recommendations_module = RecommendationsModule(driver)
            self.apply_module = ApplyModule(driver)
            self.resume_module = ResumeModule(driver)
    
    def decrypt_password(self, encrypted_password: str) -> str:
        """Расшифровать пароль hh.ru с помощью Fernet."""
        try:
            return self.fernet.decrypt(encrypted_password.encode()).decode()
        except Exception as e:
            logger.error(f"Ошибка расшифровки пароля: {e}")
            raise
    
    def process_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработать задачу на отклик.
        
        Returns:
            Словарь с результатами для отправки в apply-results.
        """
        job_id = job_data["job_id"]
        user_id = job_data["user_id"]
        mode = job_data["mode"]
        hh_login = job_data["hh_login"]
        hh_password_enc = job_data["hh_password_enc"]
        resume_id = job_data.get("resume_id")
        cover_letter = job_data.get("cover_letter", "")
        filters = job_data.get("filters", {})
        rate_limit = job_data.get("rate_limit", 20)
        delay_range = job_data.get("delay_range", [1, 3])
        vacancy_urls = job_data.get("vacancy_urls", [])
        
        # Расшифровка пароля
        hh_password = self.decrypt_password(hh_password_enc)
        
        # Подключение к БД
        conn = get_db_connection()
        
        # Обновляем статус задачи на 'running'
        update_job_status(conn, job_id, 'running')
        
        # Инициализируем браузер и авторизуемся, если ещё не сделано
        if not self.session_manager:
            self.init_browser_modules()
            self.auth_module.login(hh_login, hh_password)
        
        applies = []
        total_sent = 0
        total_skipped = 0
        total_errors = 0
        
        try:
            if mode == "auto":
                # Поиск по фильтрам
                search_url = self.search_module.build_search_url(filters)
                vacancies = self.search_module.parse_vacancies(search_url, max_pages=5)
                
                for vacancy in vacancies[:rate_limit]:
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
            
            elif mode == "recommendations":
                # Рекомендации по resume_id
                vacancies = self.recommendations_module.parse_recommendations(resume_id, max_pages=5)
                
                for vacancy in vacancies[:rate_limit]:
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
            
            elif mode == "manual":
                # Ручной режим по списку URL
                for url in vacancy_urls[:rate_limit]:
                    vacancy = {"url": url, "title": "Manual", "company": "Unknown"}
                    # Извлекаем vacancy_id из URL
                    import re
                    match = re.search(r'/vacancy/(\d+)', url)
                    vacancy_id = match.group(1) if match else "unknown"
                    vacancy["id"] = vacancy_id
                    
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
            
            else:
                raise ValueError(f"Неизвестный режим: {mode}")
            
            # Обновляем статус задачи на 'done'
            update_job_status(conn, job_id, 'done')
            
            return {
                "job_id": job_id,
                "user_id": user_id,
                "status": "done",
                "applies": applies,
                "total_sent": total_sent,
                "total_skipped": total_skipped,
                "total_errors": total_errors,
                "finished_at": datetime.utcnow().isoformat() + "Z"
            }
            
        except Exception as e:
            logger.error(f"Ошибка при обработке задачи {job_id}: {e}")
            # Обновляем статус задачи на 'failed'
            update_job_status(conn, job_id, 'failed')
            
            return {
                "job_id": job_id,
                "user_id": user_id,
                "status": "failed",
                "applies": applies,
                "total_sent": total_sent,
                "total_skipped": total_skipped,
                "total_errors": total_errors,
                "finished_at": datetime.utcnow().isoformat() + "Z",
                "error": str(e)
            }
        finally:
            conn.close()
    
    def _process_single_vacancy(self, conn, job_id, user_id, vacancy, resume_id, cover_letter, delay_range):
        """Обработать одну вакансию: проверить дедупликацию, откликнуться, сохранить результат."""
        from datetime import datetime
        
        vacancy_id = vacancy.get("id", "")
        vacancy_url = vacancy.get("url", "")
        vacancy_title = vacancy.get("title", "")
        company = vacancy.get("company", "")
        
        # Проверка дедупликации
        if is_already_applied(conn, user_id, vacancy_id):
            result = {
                "vacancy_id": vacancy_id,
                "vacancy_url": vacancy_url,
                "vacancy_title": vacancy_title,
                "company": company,
                "status": "skipped",
                "error_msg": "Already applied"
            }
            save_apply_result(conn, job_id, user_id, result)
            return result
        
        # Пытаемся откликнуться
        try:
            self.apply_module.apply_to_vacancy(
                vacancy_url,
                resume_id=resume_id,
                cover_letter=cover_letter,
                delay_min=delay_range[0],
                delay_max=delay_range[1]
            )
            result = {
                "vacancy_id": vacancy_id,
                "vacancy_url": vacancy_url,
                "vacancy_title": vacancy_title,
                "company": company,
                "status": "sent",
                "error_msg": None
            }
            save_apply_result(conn, job_id, user_id, result)
            return result
        except Exception as e:
            logger.error(f"Ошибка при отклике на вакансию {vacancy_id}: {e}")
            result = {
                "vacancy_id": vacancy_id,
                "vacancy_url": vacancy_url,
                "vacancy_title": vacancy_title,
                "company": company,
                "status": "error",
                "error_msg": str(e)
            }
            save_apply_result(conn, job_id, user_id, result)
            return result
    
    def publish_result(self, result: Dict[str, Any]):
        """Опубликовать результат в топик apply-results."""
        try:
            self.producer.send(self.topic_results, result)
            self.producer.flush()
            logger.info(f"Результат задачи {result['job_id']} опубликован в {self.topic_results}")
        except Exception as e:
            logger.error(f"Ошибка при публикации результата: {e}")
    
    def run(self):
        """Основной цикл consumer."""
        logger.info("Запуск consumer...")
        try:
            for message in self.consumer:
                job_data = message.value
                logger.info(f"Получена задача: {job_data['job_id']} (режим: {job_data['mode']})")
                
                # Обработка задачи
                result = self.process_job(job_data)
                
                # Публикация результата
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
    # Для тестирования
    consumer = JobConsumer()
    consumer.run()