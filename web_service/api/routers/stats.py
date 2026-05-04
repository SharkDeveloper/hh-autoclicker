"""
Роутер для получения статистики откликов.
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from db.session import get_db
from db.models import User, Job, Apply
from api.schemas import StatsSummary, StatsHistoryRequest, StatsHistoryResponse, ApplyResponse
from api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=StatsSummary)
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить сводную статистику откликов текущего пользователя.
    """
    # Общее количество откликов
    total_result = await db.execute(
        select(func.count(Apply.id)).where(Apply.user_id == current_user.id)
    )
    total_applies = total_result.scalar() or 0
    
    # Отклики за сегодня
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        select(func.count(Apply.id)).where(
            and_(
                Apply.user_id == current_user.id,
                Apply.applied_at >= today_start
            )
        )
    )
    today_applies = today_result.scalar() or 0
    
    # Количество по статусам
    status_result = await db.execute(
        select(Apply.status, func.count(Apply.id))
        .where(Apply.user_id == current_user.id)
        .group_by(Apply.status)
    )
    status_counts = dict(status_result.all())
    
    sent_count = status_counts.get("sent", 0)
    skipped_count = status_counts.get("skipped", 0)
    error_count = status_counts.get("error", 0)
    
    # Активные задачи (running)
    active_jobs_result = await db.execute(
        select(func.count(Job.id)).where(
            and_(
                Job.user_id == current_user.id,
                Job.status == "running"
            )
        )
    )
    active_jobs = active_jobs_result.scalar() or 0
    
    return StatsSummary(
        total_applies=total_applies,
        today_applies=today_applies,
        sent_count=sent_count,
        skipped_count=skipped_count,
        error_count=error_count,
        active_jobs=active_jobs
    )


@router.get("/history", response_model=StatsHistoryResponse)
async def get_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    start_date: Optional[datetime] = Query(None, description="Начальная дата (UTC)"),
    end_date: Optional[datetime] = Query(None, description="Конечная дата (UTC)"),
    status: Optional[str] = Query(None, description="Фильтр по статусу (sent, skipped, error)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Получить историю откликов с фильтрами по дате и статусу.
    """
    # Базовый запрос
    query = select(Apply).where(Apply.user_id == current_user.id)
    
    # Применяем фильтры
    if start_date:
        query = query.where(Apply.applied_at >= start_date)
    if end_date:
        query = query.where(Apply.applied_at <= end_date)
    if status:
        query = query.where(Apply.status == status)
    
    # Общее количество (для пагинации)
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Получаем записи с сортировкой по дате (новые сначала)
    query = query.order_by(Apply.applied_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    applies = result.scalars().all()
    
    return StatsHistoryResponse(
        applies=applies,
        total=total
    )