"""Точка входа worker-сервиса. Мультипользовательский режим — логин по задаче."""
import os
import sys

from utils.logger import setup_logger
from core.session_manager import SessionManager
from consumer import JobConsumer

logger = setup_logger(__name__, "logs/worker.log")


def main():
    logger.info("Запуск worker-сервиса HH AutoApply (multi-user)")

    required = ["DATABASE_URL", "KAFKA_BOOTSTRAP_SERVERS", "FERNET_KEY"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        logger.error(f"Отсутствуют обязательные переменные окружения: {missing}")
        sys.exit(1)

    sm = None
    consumer = None
    try:
        logger.info("Инициализация браузера (без логина)...")
        sm = SessionManager()
        sm.get_driver()

        consumer = JobConsumer()
        consumer.set_session_manager(sm)
        logger.info("Worker готов к приёму задач из Kafka")
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
        if sm:
            sm.close()
        logger.info("Worker завершил работу")


if __name__ == "__main__":
    main()
