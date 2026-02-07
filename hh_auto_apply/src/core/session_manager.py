"""
Менеджер сессий для HH Auto Apply
"""
import logging
import pickle
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from typing import Dict, Any
from src.core.config_manager import ConfigManager


class SessionManager:
    """Управление сессиями браузера"""
    
    def __init__(self, config: ConfigManager):
        """
        Инициализация менеджера сессий
        
        Args:
            config (ConfigManager): Экземпляр менеджера конфигурации
        """
        self.config = config
        self.driver = None
        self.session_file = "session.pkl"
        self.logger = logging.getLogger(__name__)
        
    def create_driver(self) -> webdriver.Chrome:
        """
        Создание и настройка WebDriver
        
        Returns:
            webdriver.Chrome: Настроенный Chrome WebDriver
        """
        chrome_options = Options()
        
        # Получение настроек приложения
        app_settings = self.config.get_application_settings()
        
        # Настройка headless режима
        if app_settings.get('headless', True):
            chrome_options.add_argument("--headless")
            
        # Меры против обнаружения
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Дополнительные опции для стабильности
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        
        # Установка user agent для имитации человека
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        chrome_options.add_argument(f"user-agent={user_agent}")
        
        # Создание драйвера
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.logger.info("WebDriver успешно создан")
        except Exception as e:
            self.logger.error(f"Ошибка создания WebDriver: {e}")
            raise
            
        return self.driver
        
    def save_session(self):
        """Сохранение текущего состояния сессии"""
        if self.driver:
            try:
                cookies = self.driver.get_cookies()
                with open(self.session_file, 'wb') as f:
                    pickle.dump(cookies, f)
                self.logger.info("Сессия успешно сохранена")
            except Exception as e:
                self.logger.error(f"Ошибка сохранения сессии: {e}")
                
    def restore_session(self) -> bool:
        """
        Восстановление сохраненной сессии
        
        Returns:
            bool: True если сессия восстановлена успешно, False в противном случае
        """
        try:
            with open(self.session_file, 'rb') as f:
                cookies = pickle.load(f)
                
            if self.driver:
                for cookie in cookies:
                    self.driver.add_cookie(cookie)
                self.logger.info("Сессия успешно восстановлена")
                return True
        except FileNotFoundError:
            self.logger.warning("Файл сессии не найден")
        except Exception as e:
            self.logger.error(f"Ошибка восстановления сессии: {e}")
            
        return False
        
    def close(self):
        """Закрытие сессии браузера"""
        if self.driver:
            try:
                self.save_session()
                self.driver.quit()
                self.logger.info("Сессия браузера закрыта")
            except Exception as e:
                self.logger.error(f"Ошибка закрытия сессии браузера: {e}")