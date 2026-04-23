"""
Модуль мониторинга для HH Auto Apply
"""
import logging
import time
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from src.core.session_manager import SessionManager


class MonitorModule:
    """Обработка мониторинга статуса откликов"""
    
    def __init__(self):
        """Инициализация модуля мониторинга"""
        self.logger = logging.getLogger(__name__)
        
    def check_application_status(self, session_manager: SessionManager) -> Dict[str, Any]:
        """
        Проверка статуса откликов
        
        Args:
            session_manager (SessionManager): Экземпляр менеджера сессий
            
        Returns:
            dict: Информация о статусе откликов
        """
        try:
            driver = session_manager.driver
            
            # Переход на страницу откликов
            driver.get("https://hh.ru/applicant/responses")
            time.sleep(3)
            
            status_info = {
                'total_responses': 0,
                'invitations': 0,
                'rejections': 0,
                'under_review': 0,
                'recent_invitations': []
            }
            
            # Получение общего количества откликов
            try:
                total_element = driver.find_element(By.XPATH, "//span[contains(@data-qa, 'total-responses')]")
                status_info['total_responses'] = int(total_element.text)
            except:
                pass
                
            # Подсчет различных статусов
            try:
                # Подсчет приглашений
                invitation_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'invitation')]")
                status_info['invitations'] = len(invitation_elements)
                
                # Подсчет отказов
                rejection_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'rejected')]")
                status_info['rejections'] = len(rejection_elements)
                
                # Подсчет находящихся на рассмотрении
                review_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'review')]")
                status_info['under_review'] = len(review_elements)
            except:
                pass
                
            # Получение последних приглашений
            try:
                invitation_items = driver.find_elements(By.XPATH, "//div[contains(@class, 'invitation-item')]")
                for item in invitation_items[:5]:  # Получить последние 5 приглашений
                    try:
                        company_element = item.find_element(By.XPATH, ".//a[contains(@class, 'company')]")
                        company = company_element.text if company_element else "Неизвестно"
                        
                        date_element = item.find_element(By.XPATH, ".//span[contains(@class, 'date')]")
                        date = date_element.text if date_element else "Неизвестно"
                        
                        status_info['recent_invitations'].append({
                            'company': company,
                            'date': date
                        })
                    except:
                        continue
            except:
                pass
                
            self.logger.info(f"Статус откликов: {status_info}")
            return status_info
            
        except Exception as e:
            self.logger.error(f"Ошибка проверки статуса откликов: {e}")
            return {
                'total_responses': 0,
                'invitations': 0,
                'rejections': 0,
                'under_review': 0,
                'recent_invitations': []
            }
            
    def export_report(self, status_info: Dict[str, Any], filename: str = "report.txt") -> bool:
        """
        Экспорт отчета о статусе откликов
        
        Args:
            status_info (dict): Информация о статусе для экспорта
            filename (str): Имя файла для экспорта
            
        Returns:
            bool: True если экспорт успешен, False в противном случае
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Отчет HH Auto Apply\n")
                f.write("=" * 30 + "\n\n")
                f.write(f"Всего откликов: {status_info['total_responses']}\n")
                f.write(f"Приглашений: {status_info['invitations']}\n")
                f.write(f"Отказов: {status_info['rejections']}\n")
                f.write(f"На рассмотрении: {status_info['under_review']}\n\n")
                
                if status_info['recent_invitations']:
                    f.write("Последние приглашения:\n")
                    f.write("-" * 20 + "\n")
                    for invitation in status_info['recent_invitations']:
                        f.write(f"{invitation['company']} - {invitation['date']}\n")
                        
            self.logger.info(f"Отчет экспортирован в {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка экспорта отчета: {e}")
            return False