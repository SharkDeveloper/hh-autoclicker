"""
Kafka producer для worker-сервиса.
Публикует результаты выполнения задач в топик apply-results.
"""
import json
import logging
import os
from kafka import KafkaProducer

logger = logging.getLogger(__name__)


def get_producer():
    """
    Создать и вернуть Kafka producer.
    
    Returns:
        KafkaProducer: настроенный producer.
    """
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )


def publish_result(result: dict):
    """
    Опубликовать результат в топик apply-results.
    
    Args:
        result: словарь с результатами задачи (соответствует схеме apply-results)
    """
    producer = None
    try:
        topic = os.environ.get("KAFKA_TOPIC_RESULTS", "apply-results")
        producer = get_producer()
        producer.send(topic, result)
        producer.flush()
        logger.info(f"Результат задачи {result.get('job_id')} опубликован в {topic}")
    except Exception as e:
        logger.error(f"Ошибка при публикации результата: {e}")
        raise
    finally:
        if producer:
            producer.close()


if __name__ == "__main__":
    # Пример использования для тестирования
    import sys
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_result = {
            "job_id": "test-job-id",
            "user_id": "test-user-id",
            "status": "done",
            "applies": [],
            "total_sent": 0,
            "total_skipped": 0,
            "total_errors": 0,
            "finished_at": "2024-01-01T12:00:00Z"
        }
        publish_result(test_result)
        print("Тестовый результат опубликован")