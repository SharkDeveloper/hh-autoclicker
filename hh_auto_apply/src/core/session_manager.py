"""
Менеджер сессий для HH Auto Apply
"""
import logging
import pickle
import time
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from typing import Dict, Any, Optional
from src.core.config_manager import ConfigManager


def _find_chromium_binary() -> str:
    """
    Поиск исполняемого файла Chromium в системе.
    Приоритет: env CHROMIUM_BINARY → which chromium → стандартные пути.
    """
    import os
    # 1. Env-переменная (Docker/CI)
    env_path = os.environ.get("CHROMIUM_BINARY", "")
    if env_path and os.path.exists(env_path):
        return env_path

    # 2. which chromium
    for cmd in ["chromium", "chromium-browser", "google-chrome"]:
        try:
            result = subprocess.run(["which", cmd], capture_output=True, text=True)
            path = result.stdout.strip()
            if path and os.path.exists(path):
                return path
        except Exception:
            pass

    # 3. Фолбэк на стандартные пути
    fallback_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/run/current-system/sw/bin/chromium",
    ]
    for p in fallback_paths:
        if os.path.exists(p):
            return p

    return "chromium"


def _find_chromedriver_binary() -> str:
    """
    Поиск исполняемого файла chromedriver в системе.
    Приоритет: env CHROMEDRIVER_BINARY → which chromedriver → стандартные пути.
    """
    import os
    # 1. Env-переменная (Docker/CI)
    env_path = os.environ.get("CHROMEDRIVER_BINARY", "")
    if env_path and os.path.exists(env_path):
        return env_path

    # 2. which chromedriver
    try:
        result = subprocess.run(["which", "chromedriver"], capture_output=True, text=True)
        path = result.stdout.strip()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass

    # 3. Стандартные пути
    fallback_paths = [
        "/usr/bin/chromedriver",
        "/usr/lib/chromium/chromedriver",
    ]
    for p in fallback_paths:
        if os.path.exists(p):
            return p

    return "chromedriver"


class SessionManager:
    """Управление сессиями браузера"""

    def __init__(self, config: ConfigManager):
        """
        Инициализация менеджера сессий

        Args:
            config (ConfigManager): Экземпляр менеджера конфигурации
        """
        self.config = config
        self.driver: Optional[webdriver.Chrome] = None
        self.session_file = "session.pkl"
        self.logger = logging.getLogger(__name__)

    def create_driver(self) -> webdriver.Chrome:
        """
        Создание и настройка WebDriver

        Returns:
            webdriver.Chrome: Настроенный Chrome WebDriver
        """
        chrome_options = Options()

        # Путь к системному Chromium
        chromium_binary = _find_chromium_binary()
        chrome_options.binary_location = chromium_binary
        self.logger.info(f"Используется Chromium: {chromium_binary}")

        # Получение настроек приложения
        app_settings = self.config.get_application_settings()

        # Настройка headless режима
        if app_settings.get('headless', True):
            chrome_options.add_argument("--headless=new")

        # Меры против обнаружения
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Дополнительные опции для стабильности
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--remote-debugging-port=0")

        # Установка user agent для имитации человека
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36"
        )
        chrome_options.add_argument(f"user-agent={user_agent}")

        # Путь к системному chromedriver
        chromedriver_binary = _find_chromedriver_binary()
        self.logger.info(f"Используется chromedriver: {chromedriver_binary}")
        service = Service(executable_path=chromedriver_binary)

        # Создание драйвера
        try:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
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
                self.driver = None
                self.logger.info("Сессия браузера закрыта")
            except Exception as e:
                self.logger.error(f"Ошибка закрытия сессии браузера: {e}")
