"""
Главный класс приложения для HH Auto Apply
"""
import logging
from typing import Dict, Any
from src.core.config_manager import ConfigManager
from src.core.session_manager import SessionManager
from src.modules.auth_module import AuthModule
from src.modules.search_module import SearchModule
from src.modules.apply_module import ApplyModule
from src.modules.monitor_module import MonitorModule


class HHAutoApply:
    """Главный класс приложения"""
    
    def __init__(self, config_path: str):
        """
        Инициализация приложения
        
        Args:
            config_path (str): Путь к файлу конфигурации
        """
        self.config = ConfigManager(config_path)
        self.session = SessionManager(self.config)
        self.auth_module = AuthModule(self.session)
        self.search_module = SearchModule(self.session)
        self.apply_module = ApplyModule(self.session)
        self.monitor_module = MonitorModule()
        
        # Настройка логирования
        self.logger = logging.getLogger(__name__)
        self.logger.info("Приложение HH Auto Apply инициализировано")
        
    def run(self, mode: str = "auto"):
        """
        Запуск приложения в заданном режиме
        
        Args:
            mode (str): Режим работы приложения (по умолчанию: "auto")
        """
        self.logger.info(f"Запуск приложения в режиме {mode}")
        # Реализация будет добавлена позже
        pass