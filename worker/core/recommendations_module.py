"""
Модуль для получения рекомендаций вакансий на hh.ru по resume_id.
Аналогичен search_module.py, но использует специальный URL с параметром resume.
"""
import logging
import time
import re
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.browser_utils import human_delay


class RecommendationsModule:
    """Обработка рекомендаций вакансий по resume_id"""

    def __init__(self, driver):
        """
        Инициализация модуля рекомендаций

        Args:
            driver: экземпляр WebDriver
        """
        self.driver = driver
        self.logger = logging.getLogger(__name__)

    def parse_recommendations(self, resume_id: str, max_pages: int = 5) -> List[Dict[str, str]]:
        """
        Парсинг рекомендаций вакансий по resume_id.

        Args:
            resume_id: ID резюме на hh.ru
            max_pages: максимальное количество страниц для парсинга

        Returns:
            Список словарей с информацией о вакансиях:
                - id: числовой ID вакансии
                - url: полный URL вакансии
                - title: заголовок вакансии
                - company: название компании
        """
        if not resume_id:
            self.logger.error("resume_id не указан")
            return []

        base_url = f"https://hh.ru/search/vacancy?resume={resume_id}"
        self.logger.info(f"Парсинг рекомендаций по resume_id {resume_id}")
        
        vacancies = []
        page = 0
        
        while page < max_pages:
            url = base_url if page == 0 else f"{base_url}&page={page}"
            self.logger.debug(f"Переход на страницу {page + 1}: {url}")
            
            try:
                self.driver.get(url)
                human_delay(2, 4)  # Задержка для загрузки страницы
                
                # Проверяем, есть ли вакансии на странице
                vacancy_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-qa="vacancy-serp__vacancy"]')
                if not vacancy_elements:
                    self.logger.info(f"На странице {page + 1} нет вакансий, завершаем парсинг")
                    break
                
                # Парсим каждую вакансию
                for element in vacancy_elements:
                    vacancy = self._parse_vacancy_element(element)
                    if vacancy:
                        vacancies.append(vacancy)
                
                self.logger.info(f"Страница {page + 1}: найдено {len(vacancy_elements)} вакансий")
                
                # Проверяем наличие кнопки "дальше"
                next_button = self.driver.find_elements(By.CSS_SELECTOR, '[data-qa="pager-next"]')
                if not next_button or 'bloko-button_disabled' in next_button[0].get_attribute('class'):
                    self.logger.info("Кнопка 'дальше' отсутствует или недоступна, завершаем парсинг")
                    break
                
                page += 1
                human_delay(1, 2)  # Задержка перед переходом на следующую страницу
                
            except Exception as e:
                self.logger.error(f"Ошибка при парсинге страницы {page + 1}: {e}")
                break
        
        self.logger.info(f"Всего найдено {len(vacancies)} рекомендаций")
        return vacancies

    def _parse_vacancy_element(self, element) -> Dict[str, str]:
        """
        Извлечь информацию о вакансии из элемента DOM.

        Args:
            element: WebElement вакансии

        Returns:
            Словарь с полями id, url, title, company или None при ошибке.
        """
        try:
            # Ссылка на вакансию
            link_elem = element.find_element(By.CSS_SELECTOR, '[data-qa="vacancy-serp__vacancy-title"]')
            vacancy_url = link_elem.get_attribute('href')
            
            # Извлекаем числовой ID вакансии из URL
            vacancy_id = self._extract_vacancy_id(vacancy_url)
            if not vacancy_id:
                self.logger.warning(f"Не удалось извлечь ID из URL: {vacancy_url}")
                return None
            
            # Заголовок вакансии
            title = link_elem.text.strip()
            
            # Компания
            company_elem = element.find_element(By.CSS_SELECTOR, '[data-qa="vacancy-serp__vacancy-employer"]')
            company = company_elem.text.strip() if company_elem else "Не указано"
            
            return {
                'id': vacancy_id,
                'url': vacancy_url,
                'title': title,
                'company': company
            }
            
        except Exception as e:
            self.logger.debug(f"Ошибка парсинга элемента вакансии: {e}")
            return None

    def _extract_vacancy_id(self, url: str) -> str:
        """
        Извлечь числовой ID вакансии из URL.
        
        Примеры:
            https://hh.ru/vacancy/12345678 → 12345678
            https://hh.ru/vacancy/12345678?query=... → 12345678
            https://spb.hh.ru/vacancy/12345678 → 12345678
        
        Returns:
            Строковый ID или пустая строка, если не найден.
        """
        if not url:
            return ""
        
        # Ищем паттерн /vacancy/цифры
        match = re.search(r'/vacancy/(\d+)', url)
        if match:
            return match.group(1)
        
        # Альтернативный паттерн для агрегаторов (не используем)
        return ""

    def get_recommendations(self, resume_id: str, limit: int = 20) -> List[Dict[str, str]]:
        """
        Упрощённый интерфейс для получения рекомендаций с лимитом.
        
        Args:
            resume_id: ID резюме
            limit: максимальное количество вакансий для возврата
        
        Returns:
            Список вакансий (не более limit)
        """
        vacancies = self.parse_recommendations(resume_id, max_pages=3)
        return vacancies[:limit]


if __name__ == "__main__":
    # Тестовый запуск (требует наличия драйвера)
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)
    
    module = RecommendationsModule(driver)
    # Используем тестовый resume_id (нужно заменить на реальный)
    test_resume_id = "d5113943ff09ef02170039ed1f597879424a41"
    results = module.get_recommendations(test_resume_id, limit=5)
    
    for v in results:
        print(f"{v['id']}: {v['title']} - {v['company']}")
    
    driver.quit()