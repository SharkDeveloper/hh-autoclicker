"""
Менеджер конфигурации для HH Auto Apply
"""
import json
import logging
import os
from typing import Dict, Any


class ConfigManager:
    """
    Класс для управления конфигурацией приложения HH Auto Apply.

    Загружает и предоставляет доступ к настройкам приложения, включая
    фильтры поиска, учетные данные и другие параметры конфигурации.
    """
    
    def __init__(self, config_path: str):
        """
        Инициализация менеджера конфигурации
        
        Args:
            config_path (str): Путь к файлу конфигурации
        """
        self.config_path = config_path
        # Инициализация logger напрямую как атрибут
        self._logger = logging.getLogger('hh_auto_apply.config_manager')
        self.config = self._load_config()
        
    @property
    def logger(self):
        """
        Свойство для доступа к logger
        
        Returns:
            logging.Logger: Логгер конфигурации
        """
        return self._logger
        
    def _load_config(self) -> Dict[str, Any]:
        """
        Загрузка конфигурации из файла
        
        Returns:
            dict: Данные конфигурации
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.logger.info(f"Конфигурация загружена из {self.config_path}")
            return config
        except FileNotFoundError:
            self.logger.warning(f"Файл конфигурации {self.config_path} не найден, используются значения по умолчанию")
            return {}
        except json.JSONDecodeError as e:
            self.logger.error(f"Ошибка разбора файла конфигурации: {e}")
            return {}
            
    def get_search_filters(self) -> Dict[str, Any]:
        """
        Получение фильтров поиска из конфигурации
        
        Returns:
            dict: Фильтры поиска
        """
        return self.config.get('search_filters', {})
        
    def get_credentials(self) -> Dict[str, str]:
        """
        Получение учётных данных пользователя.
        Env-переменные HH_USERNAME и HH_PASSWORD имеют приоритет над конфигом.
        
        Returns:
            dict: Учётные данные пользователя
        """
        creds = self.config.get('credentials', {})
        return {
            'username': os.environ.get('HH_USERNAME') or creds.get('username', ''),
            'password': os.environ.get('HH_PASSWORD') or creds.get('password', ''),
        }
        
    def get_application_settings(self) -> Dict[str, Any]:
        """
        Получение настроек приложения
        
        Returns:
            dict: Настройки приложения
        """
        return self.config.get('application', {})
