"""
Роутер для управления настройками пользователя.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from db.models import User, Settings
from api.schemas import SettingsBase, SettingsResponse
from api.deps import get_current_user
from core.security import encrypt_password

router = APIRouter()


@router.get("", response_model=SettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить настройки текущего пользователя.
    """
    result = await db.execute(
        select(Settings).where(Settings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        # Создаём настройки по умолчанию, если их нет
        settings = Settings(user_id=current_user.id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    
    return settings


@router.put("", response_model=SettingsResponse)
async def update_settings(
    settings_data: SettingsBase,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить настройки текущего пользователя.
    """
    result = await db.execute(
        select(Settings).where(Settings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = Settings(user_id=current_user.id)
        db.add(settings)
    
    # Обновляем поля
    for field, value in settings_data.dict(exclude_unset=True).items():
        if field == "hh_password" and value is not None:
            # Шифруем пароль перед сохранением
            encrypted = encrypt_password(value)
            setattr(settings, field, encrypted)
        else:
            setattr(settings, field, value)
    
    # Обновляем также поля в таблице users (hh_login, resume_id)
    if settings_data.hh_login is not None:
        current_user.hh_login = settings_data.hh_login
    if settings_data.resume_id is not None:
        current_user.resume_id = settings_data.resume_id
    
    await db.commit()
    await db.refresh(settings)
    
    return settings