"""
Модуль откликов для HH Auto Apply
"""
import logging
import time
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
        self.driver = session_manager.driver
        self.logger = logging.getLogger(__name__)
        self.wait = WebDriverWait(self.driver, 10)
        self.applied_db = AppliedVacanciesDB()
        
    def apply_to_vacancy(self, vacancy_url: str, cover_letter: str = "") -> bool:
        """
        Отклик на конкретную вакансию
        
        Args:
            vacancy_url (str): URL вакансии для отклика
            cover_letter (str): Текст сопроводительного письма (опционально)
            
        Returns:
            bool: True если отклик успешен, False в противном случае
        """
        try:
            # Извлечение ID вакансии из URL
            vacancy_id = self._extract_vacancy_id(vacancy_url)
            
            # Проверка, не откликались ли уже
            if self.applied_db.is_applied(vacancy_id):
                self.logger.info(f"Уже откликались на вакансию {vacancy_id}")
                return True
                
            # Переход на страницу вакансии
            self.logger.info(f"Отклик на вакансию: {vacancy_url}")
            self.driver.get(vacancy_url)
            time.sleep(2)
            
            # Поиск кнопки отклика
            try:
                apply_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'bloko-button') and contains(@data-qa, 'vacancy-response')]"))
                )
                apply_button.click()
                self.logger.info("Нажата кнопка отклика")
            except:
                # Попытка найти альтернативную кнопку отклика
                try:
                    apply_button = self.driver.find_element(By.XPATH, "//button[contains(@data-qa, 'vacancy-response')]")
                    apply_button.click()
                    self.logger.info("Нажата альтернативная кнопка отклика")
                except:
                    self.logger.warning("Кнопка отклика не найдена, вакансия может быть недоступна")
                    return False
                    
            # Ожидание формы отклика
            time.sleep(2)
            
            # Проверка необходимости выбора резюме
            try:
                resume_selector = self.driver.find_element(By.XPATH, "//div[contains(@class, 'resume') and contains(@class, 'bloko-radio')]")
                # Выбор первого резюме, если доступно
                resume_selector.click()
                self.logger.info("Выбрано резюме")
            except:
                self.logger.info("Выбор резюме не требуется")
                
            # Добавление сопроводительного письма, если предоставлено
            if cover_letter:
                try:
                    cover_letter_field = self.driver.find_element(By.XPATH, "//textarea[contains(@data-qa, 'vacancy-response-popup-form-letter')]")
                    cover_letter_field.clear()
                    cover_letter_field.send_keys(cover_letter)
                    self.logger.info("Добавлено сопроводительное письмо")
                except:
                    self.logger.warning("Поле сопроводительного письма не найдено")
                    
            # Отправка отклика
            try:
                submit_button = self.driver.find_element(By.XPATH, "//button[contains(@data-qa, 'vacancy-response-submit')]")
                submit_button.click()
                self.logger.info("Отклик отправлен")
            except:
                self.logger.error("Кнопка отправки не найдена")
                return False
                
            # Ожидание подтверждения
            time.sleep(3)
            
            # Добавление в базу данных отвеченных
            self.applied_db.add_applied(vacancy_id)
            
            self.logger.info(f"Успешно откликнулись на вакансию {vacancy_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка отклика на вакансию {vacancy_url}: {e}")
            return False
            
    def apply_batch(self, vacancy_urls: List[str], rate_limit: int = 20) -> Dict[str, Any]:
        """
        Пакетный отклик на несколько вакансий с ограничением скорости
        
        Args:
            vacancy_urls (list): Список URL вакансий для отклика
            rate_limit (int): Максимальное количество откликов в минуту (по умолчанию: 20)
            
        Returns:
            dict: Результаты пакетного отклика
        """
        results = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        # Расчет задержки между откликами
        delay = 60 / rate_limit if rate_limit > 0 else 0
        
        for i, url in enumerate(vacancy_urls):
            self.logger.info(f"Обработка вакансии {i+1}/{len(vacancy_urls)}: {url}")
            
            # Отклик на вакансию
            if self.apply_to_vacancy(url):
                results['success'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(url)
                
            # Задержка между откликами (кроме последней)
            if i < len(vacancy_urls) - 1 and delay > 0:
                self.logger.info(f"Ожидание {delay:.1f} секунд перед следующим откликом")
                time.sleep(delay)
                
        self.logger.info(f"Пакетный отклик завершен: {results}")
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
            # Извлечение ID из URL вида https://hh.ru/vacancy/12345678
            parts = vacancy_url.strip('/').split('/')
            return parts[-1]
        except:
            return vacancy_url