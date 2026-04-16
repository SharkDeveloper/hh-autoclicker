"""
Модуль откликов для HH Auto Apply
"""
import logging
import time
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from src.core.session_manager import SessionManager
from src.utils.data_utils import AppliedVacanciesDB


class ApplyModule:
    """Обработка функциональности отклика на вакансии"""

    def __init__(self, session_manager: SessionManager):
        """
        Инициализация модуля откликов

        Args:
            session_manager (SessionManager): Экземпляр менеджера сессий
        """
        self.session = session_manager
        self.logger = logging.getLogger(__name__)
        self.applied_db = AppliedVacanciesDB()

    @property
    def driver(self):
        """Динамическое получение актуального драйвера"""
        return self.session.driver

    def apply_to_vacancy(self, vacancy_url: str, cover_letter: str = "",
                         dry_run: bool = False) -> bool:
        """
        Отклик на конкретную вакансию

        Args:
            vacancy_url (str): URL вакансии для отклика
            cover_letter (str): Текст сопроводительного письма (опционально)
            dry_run (bool): Если True — только симуляция без реального отклика

        Returns:
            bool: True если отклик успешен (или симулирован), False в противном случае
        """
        try:
            wait = WebDriverWait(self.driver, 10)

            # Извлечение ID вакансии из URL
            vacancy_id = self._extract_vacancy_id(vacancy_url)

            # Проверка, не откликались ли уже
            if self.applied_db.is_applied(vacancy_id):
                self.logger.info(f"Уже откликались на вакансию {vacancy_id}, пропускаем")
                return True

            if dry_run:
                self.logger.info(f"[DRY RUN] Симуляция отклика на: {vacancy_url}")
                return True

            # Переход на страницу вакансии
            self.logger.info(f"Открываем вакансию: {vacancy_url}")
            self.driver.get(vacancy_url)
            time.sleep(2)

            # Поиск кнопки отклика (несколько вариантов селекторов)
            apply_button = None

            selectors = [
                "//a[@data-qa='vacancy-response-link-top']",
                "//button[@data-qa='vacancy-response-link-top']",
                "//a[contains(@data-qa, 'vacancy-response')]",
                "//button[contains(@data-qa, 'vacancy-response')]",
                "//a[contains(@class, 'bloko-button') and contains(@data-qa, 'response')]",
            ]

            for selector in selectors:
                try:
                    apply_button = wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except TimeoutException:
                    continue

            if not apply_button:
                self.logger.warning(f"Кнопка отклика не найдена: {vacancy_url}")
                return False

            apply_button.click()
            self.logger.info("Кнопка отклика нажата")
            time.sleep(2)

            # Выбор резюме, если появился диалог
            try:
                resume_radio = self.driver.find_element(
                    By.XPATH,
                    "//div[contains(@class, 'resume') and contains(@class, 'bloko-radio')]"
                )
                resume_radio.click()
                self.logger.info("Резюме выбрано")
            except NoSuchElementException:
                pass

            # Добавление сопроводительного письма
            if cover_letter:
                try:
                    letter_field = self.driver.find_element(
                        By.XPATH,
                        "//textarea[contains(@data-qa, 'vacancy-response-popup-form-letter') "
                        "or @name='coverLetter' or contains(@placeholder, 'письм')]"
                    )
                    letter_field.clear()
                    letter_field.send_keys(cover_letter)
                    self.logger.info("Сопроводительное письмо добавлено")
                except NoSuchElementException:
                    self.logger.debug("Поле сопроводительного письма не найдено")

            # Отправка отклика
            try:
                submit_button = self.driver.find_element(
                    By.XPATH,
                    "//button[@data-qa='vacancy-response-submit-popup' "
                    "or contains(@data-qa, 'vacancy-response-submit')]"
                )
                submit_button.click()
                self.logger.info("Отклик отправлен")
            except NoSuchElementException:
                # Если нет всплывающего окна — возможно, отклик уже отправлен кнопкой
                self.logger.info("Форма подтверждения не найдена, считаем отклик отправленным")

            time.sleep(3)

            # Сохранение в базе данных
            self.applied_db.add_applied(vacancy_id, vacancy_url)
            self.logger.info(f"Вакансия {vacancy_id} добавлена в список отвеченных")
            return True

        except Exception as e:
            self.logger.error(f"Ошибка отклика на вакансию {vacancy_url}: {e}")
            return False

    def apply_batch(self, vacancy_urls: List[str], rate_limit: int = 20,
                    cover_letter: str = "", dry_run: bool = False) -> Dict[str, Any]:
        """
        Пакетный отклик на несколько вакансий с ограничением скорости

        Args:
            vacancy_urls (list): Список URL вакансий
            rate_limit (int): Максимальное количество откликов в минуту
            cover_letter (str): Текст сопроводительного письма
            dry_run (bool): Режим симуляции

        Returns:
            dict: Результаты пакетного отклика
        """
        results = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }

        # Задержка между откликами
        delay = 60.0 / rate_limit if rate_limit > 0 else 3.0

        for i, url in enumerate(vacancy_urls):
            self.logger.info(f"Обработка вакансии {i + 1}/{len(vacancy_urls)}: {url}")

            if self.apply_to_vacancy(url, cover_letter=cover_letter, dry_run=dry_run):
                results['success'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(url)

            # Задержка между откликами (в dry_run — без ожидания)
            if i < len(vacancy_urls) - 1 and not dry_run:
                self.logger.info(f"Ожидание {delay:.1f} сек перед следующим откликом")
                time.sleep(delay)

        self.logger.info(f"Пакетный отклик завершён: {results}")
        return results

    def _extract_vacancy_id(self, vacancy_url: str) -> str:
        """
        Извлечение ID вакансии из URL

        Args:
            vacancy_url (str): URL вакансии

        Returns:
            str: ID вакансии
        """
        try:
            parts = vacancy_url.strip('/').split('/')
            return parts[-1]
        except Exception:
            return vacancy_url
