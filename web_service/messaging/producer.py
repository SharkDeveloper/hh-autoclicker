"""Kafka-продюсер для веб-сервиса."""
import json
import logging
import os

from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)

BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC_JOBS = os.environ.get("KAFKA_TOPIC_JOBS", "apply-jobs")

_producer = None


def get_producer():
    global _producer
    if _producer is None:
        _producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            retries=3,
            max_in_flight_requests_per_connection=1,
        )
        logger.info(f"Kafka producer создан для {BOOTSTRAP_SERVERS}")
    return _producer


async def publish_job(job_data: dict):
    producer = get_producer()
    try:
        future = producer.send(TOPIC_JOBS, job_data)
        result = future.get(timeout=10)
        logger.info(f"Задача {job_data.get('job_id')} опубликована в {TOPIC_JOBS}, раздел {result.partition}")
    except KafkaError as e:
        logger.error(f"Ошибка при публикации задачи в Kafka: {e}")
        raise
