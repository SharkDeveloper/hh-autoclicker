"""
Модуль поиска для HH Auto Apply
"""
import logging
import time
from typing import List, Dict, Any
from urllib.parse import quote
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
        self.logger = logging.getLogger(__name__)

    @property
    def driver(self):
        """Динамическое получение актуального драйвера"""
        return self.session.driver

    def search_vacancies(self, query: Dict[str, Any]) -> List[str]:
        """
        Поиск вакансий по параметрам запроса

        Args:
            query (dict): Параметры поиска

        Returns:
            list: Список URL вакансий
        """
        try:
            base_url = "https://hh.ru/search/vacancy"
            search_params = []

            # Текстовый поиск (с URL-кодированием)
            if query.get('text'):
                search_params.append(f"text={quote(query['text'])}")

            # Фильтр по зарплате
            if query.get('salary') and int(query['salary']) > 0:
                search_params.append(f"salary={query['salary']}")
                search_params.append("only_with_salary=true")

            # Фильтр по региону
            if query.get('area'):
                search_params.append(f"area={query['area']}")

            # Фильтр по опыту
            if query.get('experience'):
                search_params.append(f"experience={query['experience']}")

            # Фильтр по типу занятости
            if query.get('employment'):
                employment = query['employment']
                if isinstance(employment, list):
                    for emp in employment:
                        if emp:
                            search_params.append(f"employment={emp}")
                elif employment:
                    search_params.append(f"employment={employment}")

            # Фильтр по графику работы
            if query.get('schedule'):
                schedule = query['schedule']
                if isinstance(schedule, list):
                    for sch in schedule:
                        if sch:
                            search_params.append(f"schedule={sch}")
                elif schedule:
                    search_params.append(f"schedule={schedule}")

            # Сортировка по дате (новые первые)
            search_params.append("order_by=publication_time")

            url = f"{base_url}?{'&'.join(search_params)}" if search_params else base_url
            self.logger.info(f"Поиск вакансий по URL: {url}")

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
            wait = WebDriverWait(self.driver, 10)
            # Ждём появления хотя бы одной карточки вакансии
            try:
                wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//a[contains(@href, '/vacancy/')]")
                    )
                )
            except Exception:
                self.logger.warning("Карточки вакансий не найдены на странице")
                return []

            # Ищем все ссылки на вакансии (data-qa='serp-item__title-link' — основной селектор)
            vacancy_elements = self.driver.find_elements(
                By.XPATH,
                "//a[@data-qa='serp-item__title-link' or "
                "(contains(@href, '/vacancy/') and @data-qa)]"
            )

            if not vacancy_elements:
                # Фолбэк — любые ссылки на вакансии
                vacancy_elements = self.driver.find_elements(
                    By.XPATH,
                    "//a[contains(@href, 'hh.ru/vacancy/') or "
                    "(contains(@href, '/vacancy/') and not(contains(@href, 'search')))]"
                )

            for element in vacancy_elements:
                href = element.get_attribute('href')
                if href and '/vacancy/' in href:
                    clean_url = href.split('?')[0]
                    # Исключаем системные страницы (не реальные вакансии)
                    if any(skip in clean_url for skip in [
                        '/search/vacancy',
                        '/vacancy/advanced',
                        '/vacancy/create',
                    ]):
                        continue
                    # Проверяем, что после /vacancy/ идёт числовой ID
                    parts = clean_url.rstrip('/').split('/vacancy/')
                    if len(parts) == 2 and parts[1].isdigit():
                        if clean_url not in vacancy_urls:
                            vacancy_urls.append(clean_url)

        except Exception as e:
            self.logger.error(f"Ошибка извлечения URL вакансий: {e}")

        return vacancy_urls

    def get_recommendations(self) -> List[str]:
        """
        Получение рекомендованных вакансий из личного кабинета

        Returns:
            list: Список URL рекомендованных вакансий
        """
        try:
            self.driver.get("https://hh.ru/applicant/recommendations")
            time.sleep(3)

            vacancy_urls = self._extract_vacancy_urls()
            self.logger.info(f"Найдено {len(vacancy_urls)} рекомендованных вакансий")
            return vacancy_urls

        except Exception as e:
            self.logger.error(f"Ошибка получения рекомендаций: {e}")
            return []
