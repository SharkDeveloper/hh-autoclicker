"""
Точка входа worker-сервиса.
Инициализирует браузер, авторизуется на hh.ru, запускает Kafka consumer.
"""
import os
import sys
import logging

from utils.logger import setup_logger
from core.session_manager import SessionManager
from core.auth_module import AuthModule
from consumer import JobConsumer

logger = setup_logger(__name__, "logs/worker.log")


def init_browser_and_auth(hh_login: str, hh_password: str) -> SessionManager:
    """Инициализировать браузер и авторизоваться на hh.ru."""
    logger.info("Инициализация браузера...")
    session_manager = SessionManager()

    try:
        session_manager.get_driver()
        auth_module = AuthModule(session_manager)

        logger.info(f"Авторизация на hh.ru под логином {hh_login}...")
        ok = auth_module.login({"username": hh_login, "password": hh_password})
        if not ok or not auth_module.check_auth_status():
            raise RuntimeError(
                "Авторизация не удалась — проверьте HH_LOGIN и HH_PASSWORD"
            )
        logger.info("Авторизация прошла успешно")
        return session_manager
    except Exception as e:
        logger.error(f"Ошибка при инициализации браузера/авторизации: {e}")
        session_manager.close()
        raise


def main():
    logger.info("Запуск worker-сервиса HH AutoApply")

    required_env_vars = [
        "DATABASE_URL",
        "KAFKA_BOOTSTRAP_SERVERS",
        "FERNET_KEY",
        "HH_LOGIN",
        "HH_PASSWORD",
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
        session_manager = init_browser_and_auth(hh_login, hh_password)

        consumer = JobConsumer()
        consumer.set_session_manager(session_manager)

        logger.info("Worker готов к приему задач из Kafka")
        consumer.run()

    except KeyboardInterrupt:
        logger.info("Worker остановлен по сигналу")
    except Exception as e:
        logger.error(f"Критическая ошибка в worker: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if consumer:
            try:
                consumer.consumer.close()
                consumer.producer.close()
            except Exception:
                pass
        if session_manager:
            session_manager.close()
        logger.info("Worker завершил работу")


if __name__ == "__main__":
    main()
