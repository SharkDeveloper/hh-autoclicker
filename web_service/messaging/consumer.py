"""Kafka consumer для web-сервиса."""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any

from kafka import KafkaConsumer
from sqlalchemy import select

from db.session import AsyncSessionLocal
from db.models import Job, Apply
from core.config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC_RESULTS

logger = logging.getLogger(__name__)


async def process_result_message(message: Dict[str, Any]):
    job_id_raw = message.get("job_id")
    user_id_raw = message.get("user_id")
    status = message.get("status")
    applies = message.get("applies", [])
    finished_at = message.get("finished_at")

    if not job_id_raw:
        logger.error("Получено сообщение без job_id")
        return

    try:
        job_uuid = uuid.UUID(str(job_id_raw))
        user_uuid = uuid.UUID(str(user_id_raw)) if user_id_raw else None
    except (ValueError, TypeError) as e:
        logger.error(f"Некорректный UUID в сообщении: {e}")
        return

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(Job).where(Job.id == job_uuid))
            job = result.scalar_one_or_none()
            if not job:
                logger.error(f"Задача {job_uuid} не найдена в БД")
                return
            job.status = status or "done"
            if finished_at:
                try:
                    job.finished_at = datetime.fromisoformat(str(finished_at).replace("Z", "+00:00"))
                except ValueError:
                    job.finished_at = datetime.utcnow()
            for ad in applies:
                session.add(Apply(
                    job_id=job_uuid,
                    user_id=user_uuid or job.user_id,
                    vacancy_id=str(ad.get("vacancy_id", "")),
                    vacancy_url=ad.get("vacancy_url", "") or "",
                    vacancy_title=ad.get("vacancy_title", "") or "",
                    company=ad.get("company", "") or "",
                    status=ad.get("status", "error"),
                    error_msg=ad.get("error_msg"),
                ))
            await session.commit()
            logger.info(f"Результаты задачи {job_uuid} сохранены в БД")
        except Exception as e:
            logger.error(f"Ошибка при обработке результатов задачи {job_uuid}: {e}")
            await session.rollback()


def start_kafka_consumer(loop: asyncio.AbstractEventLoop):
    consumer = KafkaConsumer(
        KAFKA_TOPIC_RESULTS,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id="web-group",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    logger.info(f"Kafka consumer запущен, слушает топик {KAFKA_TOPIC_RESULTS}")
    try:
        for message in consumer:
            try:
                asyncio.run_coroutine_threadsafe(process_result_message(message.value), loop)
            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения Kafka: {e}")
    except KeyboardInterrupt:
        logger.info("Kafka consumer остановлен")
    finally:
        consumer.close()


async def start_kafka_consumer_background():
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, start_kafka_consumer, loop)
