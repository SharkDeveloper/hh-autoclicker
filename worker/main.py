"""
Точка входа worker-сервиса (мультипользовательский режим).
Инициализирует браузер, запускает Kafka consumer. Авторизация на hh.ru
выполняется лениво — под конкретного пользователя при получении задачи.
HH_LOGIN/HH_PASSWORD из окружения больше не читаются: учётные данные
приходят в Kafka-сообщении задачи (пароль — зашифрованный Fernet).
"""
import os
import sys

from utils.logger import setup_logger
from core.session_manager import SessionManager
from consumer import JobConsumer

logger = setup_logger(__name__, "logs/worker.log")


def main():
    logger.info("Запуск worker-сервиса HH AutoApply")

    required_env_vars = [
        "DATABASE_URL",
        "KAFKA_BOOTSTRAP_SERVERS",
        "FERNET_KEY",
    ]
    missing = [var for var in required_env_vars if not os.environ.get(var)]
    if missing:
        logger.error(f"Отсутствуют обязательные переменные окружения: {missing}")
        sys.exit(1)

    session_manager = None
    consumer = None

    try:
        # Никакой авторизации на старте — только поднимаем Chromium.
        logger.info("Инициализация браузера...")
        session_manager = SessionManager()
        session_manager.get_driver()

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
