"""
Роутер для получения статистики откликов.
"""
import uuid as uuid_mod
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, cast, Date, Integer, join

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
    job_id: Optional[uuid_mod.UUID] = Query(None, description="Фильтр по ID задачи"),
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
    if job_id:
        query = query.where(Apply.job_id == job_id)
    
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

# ---------------------------------------------------------------------------
# Дополнительные эндпоинты для графиков страницы #/stats
# ---------------------------------------------------------------------------

@router.get("/timeseries")
async def get_timeseries(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Отклики по дням: [{ date, sent, skipped, error }] за последние N дней.
    Пропущенные дни заполняются нулями.
    """
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

    result = await db.execute(
        select(
            func.date(Apply.applied_at).label("d"),
            Apply.status,
            func.count(Apply.id),
        )
        .where(Apply.user_id == current_user.id, Apply.applied_at >= start)
        .group_by("d", Apply.status)
    )

    by_day: Dict[Any, Dict[str, int]] = {}
    for d, st, cnt in result.all():
        day = d if isinstance(d, str) else d.isoformat()
        by_day.setdefault(day, {"sent": 0, "skipped": 0, "error": 0})[st] = cnt

    series = []
    for i in range(days):
        day = (start + timedelta(days=i)).date().isoformat()
        counts = by_day.get(day, {"sent": 0, "skipped": 0, "error": 0})
        series.append({"date": day, **counts})

    return series


@router.get("/by-mode")
async def get_by_mode(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Количество откликов по режимам задач: [{ mode, count }].
    """
    result = await db.execute(
        select(Job.mode, func.count(Apply.id))
        .select_from(join(Apply, Job, Apply.job_id == Job.id))
        .where(Apply.user_id == current_user.id)
        .group_by(Job.mode)
    )
    return [{"mode": m, "count": c} for m, c in result.all()]


@router.get("/top-companies")
async def get_top_companies(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Топ компаний по количеству успешно отправленных откликов: [{ company, count }].
    """
    result = await db.execute(
        select(Apply.company, func.count(Apply.id))
        .where(Apply.user_id == current_user.id, Apply.status == "sent")
        .group_by(Apply.company)
        .order_by(func.count(Apply.id).desc())
        .limit(limit)
    )
    return [{"company": c, "count": n} for c, n in result.all()]


@router.get("/heatmap")
async def get_heatmap(
    days: int = Query(90, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Тепловая карта активности по дням недели и часам (последние N дней).
    weekday: 0=Пн ... 6=Вс, hour: 0..23. Пустые ячейки заполняются нулями.
    """
    start = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            Apply.applied_at,
            func.count(Apply.id),
        )
        .where(Apply.user_id == current_user.id, Apply.applied_at >= start)
        .group_by(Apply.applied_at)
    )

    grid = {(w, h): 0 for w in range(7) for h in range(24)}
    for applied_at, cnt in result.all():
        if applied_at is None:
            continue
        weekday = (applied_at.weekday()) % 7  # 0=Пн..6=Вс
        hour = applied_at.hour
        grid[(weekday, hour)] = grid.get((weekday, hour), 0) + cnt

    return [
        {"weekday": w, "hour": h, "count": c}
        for (w, h), c in sorted(grid.items())
    ]
