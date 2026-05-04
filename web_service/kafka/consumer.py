"""
Kafka consumer для web-сервиса.
Читает результаты выполнения задач из топика apply-results и записывает их в БД.
"""
import asyncio
import json
import logging
import os
from typing import Dict, Any
from kafka import KafkaConsumer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import AsyncSessionLocal
from db.models import Job, Apply
from core.config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC_RESULTS

logger = logging.getLogger(__name__)


async def process_result_message(message: Dict[str, Any]):
    """
    Обработать сообщение с результатами задачи.
    
    Args:
        message: десериализованное JSON-сообщение из Kafka
    """
    job_id = message.get("job_id")
    user_id = message.get("user_id")
    status = message.get("status")  # "done" или "failed"
    applies = message.get("applies", [])
    finished_at = message.get("finished_at")
    
    if not job_id:
        logger.error("Получено сообщение без job_id")
        return
    
    logger.info(f"Обработка результатов задачи {job_id}, статус {status}")
    
    async with AsyncSessionLocal() as session:
        try:
            # Находим задачу
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"Задача {job_id} не найдена в БД")
                return
            
            # Обновляем статус задачи
            job.status = status
            if finished_at:
                from datetime import datetime
                # Преобразуем строку в datetime (если нужно)
                # job.finished_at = datetime.fromisoformat(finished_at.replace('Z', '+00:00'))
                pass
            
            # Сохраняем результаты откликов
            for apply_data in applies:
                apply = Apply(
                    job_id=job_id,
                    user_id=user_id,
                    vacancy_id=apply_data.get("vacancy_id", ""),
                    vacancy_url=apply_data.get("vacancy_url", ""),
                    vacancy_title=apply_data.get("vacancy_title", ""),
                    company=apply_data.get("company", ""),
                    status=apply_data.get("status", "error"),
                    error_msg=apply_data.get("error_msg"),
                )
                session.add(apply)
            
            await session.commit()
            logger.info(f"Результаты задачи {job_id} сохранены в БД")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке результатов задачи {job_id}: {e}")
            await session.rollback()


def start_kafka_consumer():
    """
    Запустить Kafka consumer в отдельном потоке.
    """
    consumer = KafkaConsumer(
        KAFKA_TOPIC_RESULTS,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        group_id="web-group",
        auto_offset_reset='earliest',
        enable_auto_commit=True,
    )
    
    logger.info(f"Kafka consumer запущен, слушает топик {KAFKA_TOPIC_RESULTS}")
    
    try:
        for message in consumer:
            try:
                # Запускаем обработку в asyncio event loop
                asyncio.create_task(process_result_message(message.value))
            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения Kafka: {e}")
    except KeyboardInterrupt:
        logger.info("Kafka consumer остановлен по сигналу")
    except Exception as e:
        logger.error(f"Критическая ошибка в Kafka consumer: {e}")
    finally:
        consumer.close()


async def start_kafka_consumer_background():
    """
    Запустить Kafka consumer в фоновом режиме (asyncio task).
    """
    loop = asyncio.get_event_loop()
    
    # Запускаем consumer в отдельном потоке, чтобы не блокировать event loop
    def run_consumer():
        start_kafka_consumer()
    
    # Используем run_in_executor для запуска блокирующего consumer в отдельном потоке
    await loop.run_in_executor(None, run_consumer)


if __name__ == "__main__":
    # Для тестирования
    logging.basicConfig(level=logging.INFO)
    start_kafka_consumer()