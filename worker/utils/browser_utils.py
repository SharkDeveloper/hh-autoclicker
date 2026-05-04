"""
Утилиты браузера для HH Auto Apply
"""
import logging
import time
import random
from typing import Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def setup_browser_utils():
    """Настройка логирования для утилит браузера"""
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(__name__)


class BrowserUtils:
    """Вспомогательные функции для операций браузера"""
    
    def __init__(self, driver: WebDriver):
        """
        Инициализация утилит браузера
        
        Args:
            driver (WebDriver): Экземпляр Selenium WebDriver
        """
        self.driver = driver
        self.logger = logging.getLogger(__name__)
        self.wait = WebDriverWait(driver, 10)
        
    def human_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """
        Добавление человекоподобной задержки между действиями
        
        Args:
            min_seconds (float): Минимальная задержка в секундах
            max_seconds (float): Максимальная задержка в секундах
        """
        delay = random.uniform(min_seconds, max_seconds)
        self.logger.info(f"Ожидание {delay:.2f} секунд (человеческая задержка)")
        time.sleep(delay)
        
    def safe_click(self, xpath: str, timeout: int = 10) -> bool:
        """
        Безопасное нажатие на элемент с логикой повторных попыток
        
        Args:
            xpath (str): XPath элемента для нажатия
            timeout (int): Таймаут в секундах
            
        Returns:
            bool: True если нажатие успешно, False в противном случае
        """
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            element.click()
            self.logger.info(f"Успешно нажат элемент: {xpath}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка нажатия на элемент {xpath}: {e}")
            return False
            
    def wait_for_element(self, xpath: str, timeout: int = 10) -> bool:
        """
        Ожидание появления элемента на странице
        
        Args:
            xpath (str): XPath элемента для ожидания
            timeout (int): Таймаут в секундах
            
        Returns:
            bool: True если элемент найден, False в противном случае
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            return True
        except:
            return False
            
    def scroll_to_element(self, xpath: str):
        """
        Прокрутка к элементу с использованием JavaScript
        
        Args:
            xpath (str): XPath элемента для прокрутки
        """
        try:
            element = self.driver.find_element(By.XPATH, xpath)
            self.driver.execute_script("arguments[0].scrollIntoView();", element)
            self.logger.info(f"Прокрутка к элементу: {xpath}")
        except Exception as e:
            self.logger.error(f"Ошибка прокрутки к элементу {xpath}: {e}")
            
    def is_element_present(self, xpath: str) -> bool:
        """
        Проверка наличия элемента на странице
        
        Args:
            xpath (str): XPath элемента для проверки
            
        Returns:
            bool: True если элемент присутствует, False в противном случае
        """
        try:
            self.driver.find_element(By.XPATH, xpath)
            return True
        except:
            return False