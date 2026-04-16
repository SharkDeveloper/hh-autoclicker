"""
Модуль резюме для HH Auto Apply
"""
import logging
import time
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from src.core.session_manager import SessionManager


class ResumeModule:
    """Обработка функциональности управления резюме"""

    def __init__(self, session_manager: SessionManager):
        """
        Инициализация модуля резюме

        Args:
            session_manager (SessionManager): Экземпляр менеджера сессий
        """
        self.session = session_manager
        self.logger = logging.getLogger(__name__)

    @property
    def driver(self):
        """Динамическое получение актуального драйвера"""
        return self.session.driver

    def get_resumes(self) -> List[Dict[str, Any]]:
        """
        Получение списка резюме пользователя

        Returns:
            list: Список словарей с информацией о резюме
        """
        try:
            self.driver.get("https://hh.ru/applicant/resumes")
            time.sleep(3)

            resumes = []
            resume_elements = self.driver.find_elements(
                By.XPATH,
                "//div[@data-qa='resume' or contains(@class, 'resume-block')]"
            )

            for element in resume_elements:
                try:
                    try:
                        title_element = element.find_element(By.XPATH, ".//h3")
                        title = title_element.text
                    except NoSuchElementException:
                        title = "Неизвестно"

                    resume_id = element.get_attribute("data-qa-resume-id") or "unknown"

                    try:
                        status_element = element.find_element(
                            By.XPATH, ".//div[contains(@class, 'status')]"
                        )
                        is_published = "published" in status_element.text.lower()
                    except NoSuchElementException:
                        is_published = False

                    resumes.append({
                        'id': resume_id,
                        'title': title,
                        'published': is_published
                    })
                except Exception as e:
                    self.logger.warning(f"Ошибка извлечения информации о резюме: {e}")
                    continue

            self.logger.info(f"Найдено {len(resumes)} резюме")
            return resumes

        except Exception as e:
            self.logger.error(f"Ошибка получения резюме: {e}")
            return []

    def update_resume(self, resume_id: str) -> bool:
        """
        Обновление (публикация) резюме

        Args:
            resume_id (str): ID резюме для обновления

        Returns:
            bool: True если обновление успешно, False в противном случае
        """
        try:
            wait = WebDriverWait(self.driver, 10)
            resume_url = f"https://hh.ru/resume/{resume_id}"
            self.driver.get(resume_url)
            time.sleep(2)

            try:
                publish_button = wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH,
                         "//button[contains(@data-qa, 'resume-update') "
                         "or contains(@data-qa, 'resume-publish')]")
                    )
                )
                publish_button.click()
                self.logger.info(f"Резюме {resume_id} обновлено")
                return True
            except TimeoutException:
                self.logger.info(f"Резюме {resume_id} уже актуально")
                return True

        except Exception as e:
            self.logger.error(f"Ошибка обновления резюме {resume_id}: {e}")
            return False

    def check_resume_status(self, resume_id: str) -> Dict[str, Any]:
        """
        Проверка статуса и готовности резюме

        Args:
            resume_id (str): ID резюме для проверки

        Returns:
            dict: Информация о статусе резюме
        """
        try:
            resume_url = f"https://hh.ru/resume/{resume_id}"
            self.driver.get(resume_url)
            time.sleep(2)

            status_info = {
                'id': resume_id,
                'published': False,
                'complete': False,
                'warnings': []
            }

            try:
                status_element = self.driver.find_element(
                    By.XPATH, "//div[contains(@class, 'status')]"
                )
                status_info['published'] = "published" in status_element.text.lower()
            except NoSuchElementException:
                pass

            try:
                self.driver.find_element(
                    By.XPATH, "//div[contains(@data-qa, 'resume-completeness')]"
                )
                status_info['complete'] = True
            except NoSuchElementException:
                status_info['warnings'].append("Не удалось определить полноту резюме")

            return status_info

        except Exception as e:
            self.logger.error(f"Ошибка проверки статуса резюме {resume_id}: {e}")
            return {
                'id': resume_id,
                'published': False,
                'complete': False,
                'warnings': [str(e)]
            }
