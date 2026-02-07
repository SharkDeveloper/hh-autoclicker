"""
Настройка логирования для HH Auto Apply
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logger(
    name: str, 
    log_file: str, 
    level: int = logging.INFO,
    max_bytes: int = 10*1024*1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Настройка логгера с ротацией файлов
    
    Args:
        name (str): Имя логгера
        log_file (str): Путь к файлу лога
        level (int): Уровень логирования (по умолчанию: INFO)
        max_bytes (int): Максимальный размер файла перед ротацией (по умолчанию: 10MB)
        backup_count (int): Количество резервных файлов для хранения (по умолчанию: 5)
        
    Returns:
        logging.Logger: Настроенный логгер
    """
    # Создание директории логов, если она не существует
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Создание логгера
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Предотвращение добавления нескольких обработчиков, если логгер уже существует
    if logger.handlers:
        return logger
    
    # Создание форматировщика
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Создание обработчика файлов с ротацией
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=max_bytes, 
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    
    # Создание обработчика консоли
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Добавление обработчиков к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_application_logger() -> logging.Logger:
    """
    Получение главного логгера приложения
    
    Returns:
        logging.Logger: Логгер приложения
    """
    return setup_logger(
        'hh_auto_apply',
        'logs/hh_auto_apply.log'
    )


def get_module_logger(module_name: str) -> logging.Logger:
    """
    Получение логгера для конкретного модуля
    
    Args:
        module_name (str): Имя модуля
        
    Returns:
        logging.Logger: Логгер модуля
    """
    return setup_logger(
        f'hh_auto_apply.{module_name}',
        f'logs/{module_name}.log'
    )