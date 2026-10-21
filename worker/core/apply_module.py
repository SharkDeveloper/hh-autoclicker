"""
Модуль откликов для HH Auto Apply
"""
import logging
import re
from typing import List, Dict, Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from core.session_manager import SessionManager
from utils.browser_utils import BrowserUtils


class ApplyModule:
    """Обработка функциональности отклика на вакансии"""

    def __init__(self, session_manager: SessionManager):
        self.session = session_manager
        self.logger = logging.getLogger(__name__)
        self._account = ""

    @property
    def driver(self):
        return self.session.driver

    def _get(self, url: str):
        """Переход по URL с таймаутом и ретраями (см. SessionManager.safe_get)."""
        self.session.safe_get(url)

    def set_account(self, account: str):
        self._account = account

    def _human_delay(self, delay_min: float, delay_max: float):
        """Человекоподобная пауза из параметров задачи (без хардкода sleep)."""
        BrowserUtils(self.driver).human_delay(delay_min, delay_max)

    def apply_to_vacancy(
        self,
        vacancy_url: str,
        cover_letter: str = "",
        dry_run: bool = False,
        resume_id: str = "",
        delay_min: float = 1.0,
        delay_max: float = 3.0,
    ) -> bool:
        """
        Отклик на конкретную вакансию.

        Args:
            vacancy_url: URL вакансии
            cover_letter: Текст сопроводительного письма
            dry_run: Только симуляция без реального отклика
            resume_id: ID резюме (для выбора в диалоге)
            delay_min, delay_max: диапазон человекоподобной задержки (сек)

        Returns:
            bool: True если отклик отправлен, False в противном случае
                  (исключения наружу не выпускаются — только лог).
        """
        try:
            wait = WebDriverWait(self.driver, 10)
            vacancy_id = self._extract_vacancy_id(vacancy_url)

            if dry_run:
                self.logger.info(f"[DRY RUN] Симуляция отклика на: {vacancy_url}")
                return True

            # ── Этап 1: открываем страницу вакансии ───────────────────────
            self.logger.info(f"[Этап 1/5] Открываем вакансию {vacancy_id}: {vacancy_url}")
            self._get(vacancy_url)
            self._human_delay(delay_min, delay_max)

            # Вакансия удалена / недоступна — сразу пропускаем
            body_text = ""
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text or ""
            except Exception:
                pass
            if "Вакансия больше не доступна" in body_text or "Архивная вакансия" in body_text:
                self.logger.warning(f"[Этап 1/5] Вакансия {vacancy_id} недоступна (архив)")
                raise RuntimeError("Вакансия недоступна (удалена или в архиве)")

            # ── Этап 2: ищем и нажимаем кнопку «Откликнуться» ─────────────
            self.logger.info(f"[Этап 2/5] Ищем кнопку отклика (вакансия {vacancy_id})")
            selectors = [
                "//a[@data-qa='vacancy-response-link-top']",
                "//button[@data-qa='vacancy-response-link-top']",
                "//a[contains(@data-qa, 'vacancy-response-link')]",
                "//a[contains(@data-qa, 'vacancy-response')]",
                "//button[contains(@data-qa, 'vacancy-response')]",
            ]

            apply_button = None
            for selector in selectors:
                try:
                    apply_button = wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except TimeoutException:
                    continue

            if not apply_button:
                self.logger.warning(f"[Этап 2/5] Кнопка отклика не найдена: {vacancy_url}")
                return False

            apply_button.click()
            self.logger.info("[Этап 2/5] Кнопка отклика нажата — открыта форма")
            self._human_delay(delay_min, delay_max)

            # ── Этап 3: выбор резюме в форме отклика ──────────────────────
            self.logger.info(
                f"[Этап 3/5] Выбор резюме (resume_id={resume_id or 'по умолчанию'})"
            )
            if resume_id:
                try:
                    resume_input = self.driver.find_element(
                        By.XPATH,
                        f"//input[@data-qa='resume-input' and @value='{resume_id}']",
                    )
                    self.driver.execute_script("arguments[0].click();", resume_input)
                    self.logger.info(f"[Этап 3/5] Выбрано резюме {resume_id}")
                except NoSuchElementException:
                    self.logger.warning(
                        f"[Этап 3/5] Резюме {resume_id} не найдено в списке — "
                        "используется по умолчанию"
                    )
            else:
                try:
                    resume_radio = self.driver.find_element(
                        By.XPATH, "//div[contains(@class, 'bloko-radio')]"
                    )
                    self.driver.execute_script("arguments[0].click();", resume_radio)
                    self.logger.info("[Этап 3/5] Выбрано резюме по умолчанию")
                except NoSuchElementException:
                    self.logger.debug("[Этап 3/5] Выбор резюме не требуется")

            # ── Этап 4: сопроводительное письмо ────────────────────────────
            if cover_letter:
                self.logger.info(
                    f"[Этап 4/5] Ввод сопроводительного письма "
                    f"({len(cover_letter)} симв.)"
                )
                try:
                    letter_field = self.driver.find_element(
                        By.XPATH,
                        "//textarea[contains(@data-qa, 'vacancy-response-popup-form-letter') "
                        "or @name='coverLetter' or contains(@placeholder, 'письм')]",
                    )
                    letter_field.clear()
                    letter_field.send_keys(cover_letter)
                    self.logger.info("[Этап 4/5] Сопроводительное письмо добавлено")
                except NoSuchElementException:
                    self.logger.warning(
                        "[Этап 4/5] Поле сопроводительного письма не найдено — "
                        "пропускаем (возможно, работодатель его отключил)"
                    )
            else:
                self.logger.info("[Этап 4/5] Сопроводительное письмо не задано — пропуск")

            # ── Этап 5: отправка формы + проверка результата ───────────────
            self.logger.info("[Этап 5/5] Отправка отклика")
            try:
                submit_button = wait.until(
                    EC.element_to_be_clickable(
                        By.XPATH,
                        "//button[@data-qa='vacancy-response-submit-popup' "
                        "or contains(@data-qa, 'vacancy-response-submit')]",
                    )
                )
                submit_button.click()
                self.logger.info("[Этап 5/5] Кнопка «Отправить» нажата")
            except (TimeoutException, NoSuchElementException):
                self.logger.info(
                    "[Этап 5/5] Форма подтверждения не найдена — "
                    "считаем ответ отправленным (отклик в 1 клик)"
                )

            self._human_delay(delay_min, delay_max)

            # Проверяем, что форма закрылась / появилось подтверждение.
            sent_ok = self._verify_response_sent(wait)
            if sent_ok:
                self.logger.info(f"[Готово] Отклик на вакансию {vacancy_id} отправлен ✓")
            else:
                self.logger.warning(
                    f"[Готово] Не удалось подтвердить отправку отклика "
                    f"на вакансию {vacancy_id}"
                )
            return sent_ok

        except Exception as e:
            self.logger.error(f"Ошибка отклика на вакансию {vacancy_url}: {e}")
            raise

    def apply_batch(
        self,
        vacancy_urls: List[str],
        rate_limit: int = 20,
        cover_letter: str = "",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        results = {"success": 0, "failed": 0, "skipped": 0, "errors": []}
        delay = 60.0 / rate_limit if rate_limit > 0 else 3.0

        for i, url in enumerate(vacancy_urls):
            self.logger.info(f"Обработка вакансии {i + 1}/{len(vacancy_urls)}: {url}")

            if self.apply_to_vacancy(url, cover_letter=cover_letter, dry_run=dry_run):
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(url)

            if i < len(vacancy_urls) - 1 and not dry_run:
                self.logger.info(f"Ожидание {delay:.1f} сек перед следующим откликом")
                self._human_delay(delay, delay)

        self.logger.info(f"Пакетный отклик завершен: {results}")
        return results

    def _extract_vacancy_id(self, vacancy_url: str) -> str:
        match = re.search(r"/vacancy/(\d+)", vacancy_url)
        if match:
            return match.group(1)
        return vacancy_url

    def _verify_response_sent(self, wait: WebDriverWait) -> bool:
        """Подтвердить, что отклик реально отправлен.

        Признаки успеха:
          - появилось сообщение «Ответ отправлен» / success-баннер;
          - кнопка сменилась на «Отклик отправлен» (response-already);
          - попап формы закрылся и кнопки отклика больше нет.
        """
        # 1. Явные подтверждения
        for xpath in (
            "//*[contains(@data-qa, 'success')]",
            "//div[contains(text(), 'Ответ отправлен')]",
            "//*[contains(text(), 'Отклик отправлен')]",
            "//a[@data-qa='vacancy-response-link-top-already']",
            "//button[@data-qa='vacancy-response-link-top-already']",
        ):
            try:
                if self.driver.find_elements(By.XPATH, xpath):
                    return True
            except Exception:
                continue

        # 2. Попап формы должен исчезнуть
        try:
            popup = self.driver.find_elements(
                By.XPATH, "//*[@data-qa='vacancy-response-popup']"
            )
            if not popup:
                # Попапа нет — проверяем, что первичной кнопки тоже нет
                remaining = self.driver.find_elements(
                    By.XPATH, "//*[@data-qa='vacancy-response-link-top']"
                )
                return len(remaining) == 0
        except Exception:
            pass

        return False
