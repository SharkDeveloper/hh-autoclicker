"""
Kafka producer для web-сервиса.
Публикует задачи в топик apply-jobs.
"""
import json
import logging
import os
from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)

# Конфигурация Kafka
BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC_JOBS = os.environ.get("KAFKA_TOPIC_JOBS", "apply-jobs")

# Глобальный producer (создаётся при первом использовании)
_producer = None


def get_producer():
    """
    Создать и вернуть Kafka producer (singleton).
    
    Returns:
        KafkaProducer: настроенный producer.
    """
    global _producer
    if _producer is None:
        try:
            _producer = KafkaProducer(
                bootstrap_servers=BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',  # Гарантированная доставка
                retries=3,
                max_in_flight_requests_per_connection=1,
            )
            logger.info(f"Kafka producer создан для {BOOTSTRAP_SERVERS}")
        except Exception as e:
            logger.error(f"Ошибка создания Kafka producer: {e}")
            raise
    return _producer


async def publish_job(job_data: dict):
    """
    Публиковать задачу в топик apply-jobs.
    
    Args:
        job_data: словарь с данными задачи (соответствует схеме KafkaJobMessage)
    
    Raises:
        KafkaError: если не удалось отправить сообщение
    """
    producer = get_producer()
    
    try:
        future = producer.send(TOPIC_JOBS, job_data)
        # Ждём подтверждения
        result = future.get(timeout=10)
        logger.info(f"Задача {job_data.get('job_id')} опубликована в {TOPIC_JOBS}, partition {result.partition}")
    except KafkaError as e:
        logger.error(f"Ошибка при публикации задачи в Kafka: {e}")
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при публикации задачи: {e}")
        raise


def close_producer():
    """Закрыть producer (вызывается при shutdown)."""
    global _producer
    if _producer:
        _producer.close()
        _producer = None
        logger.info("Kafka producer закрыт")