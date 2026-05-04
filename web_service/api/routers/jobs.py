"""
Роутер для управления задачами на отклик.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from db.session import get_db
from db.models import User, Job, Settings
from api.schemas import JobCreate, JobResponse, JobListResponse
from api.deps import get_current_user
from kafka.producer import publish_job
from core.security import decrypt_password

router = APIRouter()


@router.post("", response_model=JobResponse)
async def create_job(
    job_data: JobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Создать новую задачу на отклик.
    
    При создании задачи:
    1. Сохраняем запись в таблице jobs
    2. Публикуем сообщение в Kafka топик apply-jobs
    3. Возвращаем созданную задачу
    """
    # Получаем настройки пользователя
    result = await db.execute(
        select(Settings).where(Settings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Настройки пользователя не найдены"
        )
    
    # Проверяем, что у пользователя заполнены необходимые данные
    if not current_user.hh_login:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не указан логин hh.ru. Заполните настройки."
        )
    
    if not current_user.hh_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не указан пароль hh.ru. Заполните настройки."
        )
    
    # Для режима recommendations нужен resume_id
    if job_data.mode == "recommendations":
        resume_id = job_data.resume_id or current_user.resume_id
        if not resume_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для режима recommendations требуется resume_id"
            )
    else:
        resume_id = current_user.resume_id
    
    # Создаём запись задачи в БД
    job = Job(
        user_id=current_user.id,
        mode=job_data.mode,
        status="pending",
        filters=job_data.filters.dict() if job_data.filters else None,
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Подготавливаем данные для Kafka сообщения
    # Расшифровываем пароль (он будет зашифрован заново в worker)
    hh_password_enc = current_user.hh_password  # Уже зашифрован
    
    kafka_message = {
        "job_id": str(job.id),
        "user_id": str(current_user.id),
        "mode": job_data.mode,
        "hh_login": current_user.hh_login,
        "hh_password_enc": hh_password_enc,
        "resume_id": resume_id,
        "cover_letter": settings.cover_letter or "",
        "filters": job_data.filters.dict() if job_data.filters else {},
        "rate_limit": settings.rate_limit,
        "delay_range": [settings.delay_min, settings.delay_max],
        "vacancy_urls": job_data.vacancy_urls or [],
    }
    
    # Публикуем задачу в Kafka
    try:
        await publish_job(kafka_message)
    except Exception as e:
        # Если не удалось опубликовать, помечаем задачу как failed
        job.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при публикации задачи в Kafka: {str(e)}"
        )
    
    return job


@router.get("", response_model=JobListResponse)
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """
    Получить список задач текущего пользователя с пагинацией.
    """
    offset = (page - 1) * page_size
    
    # Общее количество задач
    count_result = await db.execute(
        select(func.count(Job.id)).where(Job.user_id == current_user.id)
    )
    total = count_result.scalar()
    
    # Задачи с пагинацией
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
        page_size=page_size
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить детали задачи по ID.
    """
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена"
        )
    
    return job


@router.delete("/{job_id}")
async def cancel_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Отменить задачу (только если она в статусе pending).
    """
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена"
        )
    
    if job.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Можно отменять только задачи в статусе pending"
        )
    
    job.status = "cancelled"
    await db.commit()
    
    return {"message": "Задача отменена"}