"""
Kafka consumer для web-сервиса.
Считывает результаты выполнения задач из топика apply-results и записывает их в БД.
"""
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

    logger.info(f"Обработка результатов задачи {job_uuid}, статус {status}")

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
                    job.finished_at = datetime.fromisoformat(
                        str(finished_at).replace("Z", "+00:00")
                    )
                except ValueError:
                    job.finished_at = datetime.utcnow()

            for apply_data in applies:
                apply = Apply(
                    job_id=job_uuid,
                    user_id=user_uuid or job.user_id,
                    vacancy_id=str(apply_data.get("vacancy_id", "")),
                    vacancy_url=apply_data.get("vacancy_url", "") or "",
                    vacancy_title=apply_data.get("vacancy_title", "") or "",
                    company=apply_data.get("company", "") or "",
                    status=apply_data.get("status", "error"),
                    error_msg=apply_data.get("error_msg"),
                )
                session.add(apply)

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
                asyncio.run_coroutine_threadsafe(
                    process_result_message(message.value), loop
                )
            except Exception as e:
                logger.error(f"Ошибка при обработке сообщения Kafka: {e}")
    except KeyboardInterrupt:
        logger.info("Kafka consumer остановлен по сигналу")
    except Exception as e:
        logger.error(f"Критическая ошибка в Kafka consumer: {e}")
    finally:
        consumer.close()


async def start_kafka_consumer_background():
    """Запустить блокирующий Kafka consumer в отдельном потоке, не блокируя event loop."""
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, start_kafka_consumer, loop)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _loop = asyncio.new_event_loop()
    try:
        start_kafka_consumer(_loop)
    finally:
        _loop.close()
