"""
Модуль поиска для HH Auto Apply
"""
import logging
import time
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from src.core.session_manager import SessionManager


class SearchModule:
    """Обработка функциональности поиска вакансий"""
    
    def __init__(self, session_manager: SessionManager):
        """
        Инициализация модуля поиска
        
        Args:
            session_manager (SessionManager): Экземпляр менеджера сессий
        """
        self.session = session_manager
        self.driver = session_manager.driver
        self.logger = logging.getLogger(__name__)
        self.wait = WebDriverWait(self.driver, 10)
        
    def search_vacancies(self, query: Dict[str, Any]) -> List[str]:
        """
        Поиск вакансий по параметрам запроса
        
        Args:
            query (dict): Параметры поиска
            
        Returns:
            list: Список URL вакансий
        """
        try:
            # Построение URL поиска
            base_url = "https://hh.ru/search/vacancy"
            search_params = []
            
            # Добавление текстового поиска
            if 'text' in query:
                search_params.append(f"text={query['text']}")
                
            # Добавление фильтра по зарплате
            if 'salary' in query:
                search_params.append(f"salary={query['salary']}")
                
            # Добавление фильтра по региону
            if 'area' in query:
                search_params.append(f"area={query['area']}")
                
            # Добавление фильтра по опыту
            if 'experience' in query:
                search_params.append(f"experience={query['experience']}")
                
            # Добавление фильтра по типу занятости
            if 'employment' in query:
                employment = query['employment']
                if isinstance(employment, list):
                    for emp in employment:
                        search_params.append(f"employment={emp}")
                else:
                    search_params.append(f"employment={employment}")
                    
            # Добавление фильтра по графику работы
            if 'schedule' in query:
                schedule = query['schedule']
                if isinstance(schedule, list):
                    for sch in schedule:
                        search_params.append(f"schedule={sch}")
                else:
                    search_params.append(f"schedule={schedule}")
            
            # Построение полного URL
            if search_params:
                url = f"{base_url}?{'&'.join(search_params)}"
            else:
                url = base_url
                
            self.logger.info(f"Поиск вакансий с URL: {url}")
            
            # Переход к результатам поиска
            self.driver.get(url)
            time.sleep(3)
            
            # Извлечение URL вакансий
            vacancy_urls = self._extract_vacancy_urls()
            
            self.logger.info(f"Найдено {len(vacancy_urls)} вакансий")
            return vacancy_urls
            
        except Exception as e:
            self.logger.error(f"Ошибка поиска вакансий: {e}")
            return []
            
    def _extract_vacancy_urls(self) -> List[str]:
        """
        Извлечение URL вакансий со страницы результатов поиска
        
        Returns:
            list: Список URL вакансий
        """
        vacancy_urls = []
        
        try:
            # Поиск всех ссылок на вакансии
            vacancy_elements = self.driver.find_elements(
                By.XPATH, "//a[contains(@href, '/vacancy/') and @href]"
            )
            
            for element in vacancy_elements:
                href = element.get_attribute('href')
                if href and '/vacancy/' in href and href not in vacancy_urls:
                    # Очистка URL от параметров запроса
                    clean_url = href.split('?')[0]
                    vacancy_urls.append(clean_url)
                    
        except Exception as e:
            self.logger.error(f"Ошибка извлечения URL вакансий: {e}")
            
        return vacancy_urls
        
    def get_recommendations(self) -> List[str]:
        """
        Получение рекомендованных вакансий из личного кабинета пользователя
        
        Returns:
            list: Список URL рекомендованных вакансий
        """
        try:
            # Переход на страницу рекомендаций
            self.driver.get("https://hh.ru/applicant/recommendations")
            time.sleep(3)
            
            # Извлечение URL вакансий из рекомендаций
            vacancy_urls = self._extract_vacancy_urls()
            
            self.logger.info(f"Найдено {len(vacancy_urls)} рекомендованных вакансий")
            return vacancy_urls
            
        except Exception as e:
            self.logger.error(f"Ошибка получения рекомендаций: {e}")
            return []