"""
Роутер для управления задачами на отклик.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, case
from sqlalchemy.orm.attributes import flag_modified

from db.session import get_db
from db.models import User, Job, Settings
from api.schemas import JobCreate, JobResponse, JobListResponse
from api.deps import get_current_user
from messaging.producer import publish_job

logger = logging.getLogger(__name__)

router = APIRouter()

# Задачи «зависли» в running дольше этого времени (worker упал/пересобран) —
# автоматически помечаются failed, чтобы UI не «вечно грузил».
STALE_RUNNING_MINUTES = int(os.environ.get("STALE_RUNNING_MINUTES", "15"))


def _parse_filters(raw) -> dict:
    """Нормализовать поле filters (JSONB/JSON/dict/строка) в словарь."""
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


async def _reap_stale_jobs(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Пометить failed зависшие running-задачи пользователя."""
    cutoff = datetime.utcnow() - timedelta(minutes=STALE_RUNNING_MINUTES)
    result = await db.execute(
        select(Job).where(
            Job.user_id == user_id,
            Job.status == "running",
            (Job.started_at.is_(None)) | (Job.started_at < cutoff),
        )
    )
    stale = result.scalars().all()
    for job in stale:
        logger.warning(f"Задача {job.id} зависла в running — помечаем failed")
        job.status = "failed"
        job.error = (
            "Задача не была завершена воркером (воркер перезапущен или задача "
            "была остановлена вручную). Создайте новую задачу."
        )
        job.finished_at = datetime.utcnow()
    if stale:
        await db.commit()


@router.post("", response_model=JobResponse)
async def create_job(
    job_data: JobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Создать новую задачу на отклик.
    """
    result = await db.execute(
        select(Settings).where(Settings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Настройки пользователя не найдены",
        )

    if not current_user.hh_login:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не указан логин hh.ru. Заполните настройки.",
        )

    if not current_user.hh_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не указан пароль hh.ru. Заполните настройки.",
        )

    if job_data.mode == "recommendations":
        resume_id = job_data.resume_id or current_user.resume_id
        if not resume_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для режима рекомендаций требуется resume_id",
            )
    else:
        resume_id = current_user.resume_id

    # Проверка создания задачи: валидные URL + лимит параллельных задач
    vacancy_urls = [u.strip() for u in (job_data.vacancy_urls or []) if u.strip()]
    if job_data.mode == "manual":
        valid_urls = [u for u in vacancy_urls if "/vacancy/" in u]
        if not valid_urls:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не указано ни одной корректной ссылки на вакансию hh.ru "
                       "(формат: https://hh.ru/vacancy/123456782)",
            )
        vacancy_urls = valid_urls

    await _reap_stale_jobs(db, current_user.id)

    active_result = await db.execute(
        select(func.count(Job.id)).where(
            Job.user_id == current_user.id,
            Job.status.in_(["pending", "running"]),
        )
    )
    active_count = active_result.scalar() or 0
    max_parallel = int(os.environ.get("MAX_PARALLEL_JOBS", "2"))
    if active_count >= max_parallel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Нельзя запустить новую задачу: уже выполняется {active_count} "
                f"(максимум {max_parallel} одновременно). Дождитесь завершения "
                "или остановите одну из задач."
            ),
        )

    filters_dict = job_data.filters.dict() if job_data.filters else None

    job = Job(
        user_id=current_user.id,
        mode=job_data.mode,
        status="pending",
        filters=filters_dict,
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    kafka_message = {
        "job_id": str(job.id),
        "user_id": str(current_user.id),
        "mode": job_data.mode,
        "hh_login": current_user.hh_login,
        "hh_password_enc": current_user.hh_password,
        "resume_id": resume_id,
        "cover_letter": settings.cover_letter or "",
        "filters": filters_dict or {},
        "rate_limit": settings.rate_limit,
        "delay_range": [settings.delay_min, settings.delay_max],
        "vacancy_urls": vacancy_urls,
    }

    # Для manual-режима сохраняем валидированные URL в filters задачи —
    # они нужны для отображения на странице деталей.
    if job_data.mode == "manual":
        merged_filters = dict(filters_dict or {})
        merged_filters["vacancy_urls"] = vacancy_urls
        job.filters = merged_filters
        flag_modified(job, "filters")
        await db.commit()
        await db.refresh(job)

    try:
        await publish_job(kafka_message)
    except Exception as e:
        job.status = "failed"
        job.error = f"Ошибка публикации задачи в очередь: {e}"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при публикации задачи в Kafka: {str(e)}",
        )

    return job


@router.get("", response_model=JobListResponse)
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    await _reap_stale_jobs(db, current_user.id)
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count(Job.id)).where(Job.user_id == current_user.id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Job)
        .where(Job.user_id == current_user.id)
        .order_by(desc(Job.created_at))
        .offset(offset)
        .limit(page_size)
    )
    jobs = result.scalars().all()

    return JobListResponse(
        jobs=jobs,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _reap_stale_jobs(db, current_user.id)

    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена",
        )

    return job


@router.post("/{job_id}/stop")
async def stop_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Остановить задачу.

    - pending → cancelled (worker пропустит её при получении из Kafka);
    - running → статус остаётся running, но worker проверит флаг перед каждым
      откликом и корректно завершит задачу со статусом cancelled.
    """
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена",
        )

    if job.status == "pending":
        job.status = "cancelled"
        job.finished_at = datetime.utcnow()
        await db.commit()
        return {"message": "Задача отменена"}

    if job.status == "running":
        filters = _parse_filters(job.filters)
        filters["_cancel_requested"] = True
        job.filters = filters
        flag_modified(job, "filters")
        await db.commit()
        # Если задача зависла (started_at слишком старая) — закрываем сразу,
        # иначе пользователь будет ждать «вечной остановки».
        started = job.started_at
        if started is not None:
            age_min = (datetime.utcnow() - started).total_seconds() / 60.0
            if age_min >= STALE_RUNNING_MINUTES:
                job.status = "cancelled"
                job.finished_at = datetime.utcnow()
                await db.commit()
                return {"message": "Задача остановлена (воркер не отвечал)"}
        return {
            "message": "Остановка запрошена — задача завершится "
                       "после текущего отклика",
        }

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Остановить можно только запущенную или ожидающую задачу",
    )


@router.delete("/{job_id}")
async def delete_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Удалить задачу вместе с её откликами (ON DELETE CASCADE).

    Pending-задача удаляется сразу. Запущенную задачу сначала останавливаем
    (флаг _cancel_requested + статус cancelled), затем удаляем — worker
    заметит отсутствующую строку в БД и прервёт выполнение на следующей
    проверке.
    """
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена",
        )

    if job.status == "running":
        # Останавливаем и удаляем: worker увидит удалённую задачу
        # (_is_cancel_requested вернёт True) и прервёт цикл откликов.
        filters = _parse_filters(job.filters)
        filters["_cancel_requested"] = True
        job.filters = filters
        flag_modified(job, "filters")
        await db.commit()

    await db.delete(job)
    await db.commit()

    return {"message": "Задача удалена"}
