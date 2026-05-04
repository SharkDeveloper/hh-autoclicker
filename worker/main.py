"""
Точка входа worker-сервиса.
Инициализирует браузер, авторизуется на hh.ru, запускает Kafka consumer.
"""
import os
import sys
import logging
import time
from utils.logger import setup_logger
from core.session_manager import SessionManager
from core.auth_module import AuthModule
from consumer import JobConsumer

# Настройка логирования
logger = setup_logger(__name__)


def init_browser_and_auth(hh_login: str, hh_password: str) -> SessionManager:
    """
    Инициализировать браузер и авторизоваться на hh.ru.
    
    Args:
        hh_login: логин hh.ru
        hh_password: пароль hh.ru
    
    Returns:
        SessionManager: менеджер сессии браузера.
    """
    logger.info("Инициализация браузера...")
    session_manager = SessionManager()
    
    try:
        driver = session_manager.get_driver()
        auth_module = AuthModule(driver)
        
        logger.info(f"Авторизация на hh.ru под логином {hh_login}...")
        auth_module.login(hh_login, hh_password)
        logger.info("Авторизация успешна")
        
        return session_manager
    except Exception as e:
        logger.error(f"Ошибка при инициализации браузера/авторизации: {e}")
        session_manager.close()
        raise


def main():
    """Основная функция worker-сервиса."""
    logger.info("Запуск worker-сервиса HH AutoApply")
    
    # Проверка обязательных переменных окружения
    required_env_vars = [
        "DATABASE_URL",
        "KAFKA_BOOTSTRAP_SERVERS",
        "FERNET_KEY",
        "HH_LOGIN",
        "HH_PASSWORD"
    ]
    
    missing = [var for var in required_env_vars if not os.environ.get(var)]
    if missing:
        logger.error(f"Отсутствуют обязательные переменные окружения: {missing}")
        sys.exit(1)
    
    hh_login = os.environ["HH_LOGIN"]
    hh_password = os.environ["HH_PASSWORD"]
    
    session_manager = None
    consumer = None
    
    try:
        # Инициализация браузера и авторизация
        session_manager = init_browser_and_auth(hh_login, hh_password)
        
        # Создание и запуск consumer
        consumer = JobConsumer()
        # Передаём session_manager в consumer (можно через атрибут)
        consumer.session_manager = session_manager
        
        logger.info("Worker готов к приёму задач из Kafka")
        consumer.run()
        
    except KeyboardInterrupt:
        logger.info("Worker остановлен по сигналу")
    except Exception as e:
        logger.error(f"Критическая ошибка в worker: {e}", exc_info=True)
    finally:
        if consumer:
            try:
                consumer.consumer.close()
                consumer.producer.close()
            except:
                pass
        if session_manager:
            session_manager.close()
        logger.info("Worker завершил работу")


if __name__ == "__main__":
    main()