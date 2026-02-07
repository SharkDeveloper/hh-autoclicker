"""
Модуль аутентификации для HH Auto Apply
"""
import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from src.core.session_manager import SessionManager


class AuthModule:
    """Обработка аутентификации на hh.ru"""
    
    def __init__(self, session_manager: SessionManager):
        """
        Инициализация модуля аутентификации
        
        Args:
            session_manager (SessionManager): Экземпляр менеджера сессий
        """
        self.session = session_manager
        self.driver = session_manager.driver
        self.logger = logging.getLogger(__name__)
        self.wait = WebDriverWait(self.driver, 10)
        
    def login(self, credentials: dict) -> bool:
        """
        Выполнение входа на hh.ru
        
        Args:
            credentials (dict): Учетные данные пользователя с 'username' и 'password'
            
        Returns:
            bool: True если вход успешен, False в противном случае
        """
        try:
            # Переход на страницу входа
            self.driver.get("https://hh.ru/account/login")
            self.logger.info("Переход на страницу входа")
            
            # Ожидание загрузки страницы
            time.sleep(2)
            
            # Поиск и заполнение поля имени пользователя
            username_field = self.wait.until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            username_field.clear()
            username_field.send_keys(credentials.get('username', ''))
            
            # Поиск и заполнение поля пароля
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.clear()
            password_field.send_keys(credentials.get('password', ''))
            
            # Отправка формы
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            # Ожидание завершения входа
            time.sleep(5)
            
            # Проверка успешности входа
            if self.check_auth_status():
                self.logger.info("Вход выполнен успешно")
                return True
            else:
                self.logger.error("Вход не выполнен")
                return False
                
        except Exception as e:
            self.logger.error(f"Ошибка при входе: {e}")
            return False
            
    def check_auth_status(self) -> bool:
        """
        Проверка статуса аутентификации
        
        Returns:
            bool: True если аутентифицирован, False в противном случае
        """
        try:
            self.driver.get("https://hh.ru/")
            time.sleep(2)
            
            # Проверка наличия элементов, указывающих на статус входа
            try:
                # Поиск ссылки на профиль пользователя или кнопки выхода
                self.driver.find_element(By.XPATH, "//a[contains(@href, '/applicant')]")
                self.logger.info("Пользователь аутентифицирован")
                return True
            except:
                self.logger.info("Пользователь не аутентифицирован")
                return False
                
        except Exception as e:
            self.logger.error(f"Ошибка проверки статуса аутентификации: {e}")
            return False
            
    def logout(self):
        """Выполнение выхода из hh.ru"""
        try:
            self.driver.get("https://hh.ru/account/logout")
            self.logger.info("Выход выполнен успешно")
        except Exception as e:
            self.logger.error(f"Ошибка при выходе: {e}")