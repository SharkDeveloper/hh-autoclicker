"""
Роутер для аутентификации и регистрации пользователей.
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from db.models import User, Settings
from api.schemas import UserRegister, UserResponse, TokenResponse
from core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from core.config import JWT_EXPIRE_MINUTES

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Регистрация нового пользователя.
    """
    # Проверяем, существует ли пользователь с таким email
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует",
        )
    
    # Создаём пользователя
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_pw=hashed_password,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Создаём настройки по умолчанию
    settings = Settings(user_id=user.id)
    db.add(settings)
    await db.commit()
    
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    Вход пользователя. Возвращает JWT токен в httpOnly cookie.
    """
    # Ищем пользователя по email
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_pw):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Создаём токен
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=JWT_EXPIRE_MINUTES)
    )
    
    # Устанавливаем токен в httpOnly cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=JWT_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False,  # В production установить True
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(response: Response):
    """
    Выход пользователя (очистка cookie).
    """
    response.delete_cookie(key="access_token")
    return {"message": "Успешный выход"}


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: User = Depends(get_current_user),
):
    """
    Получить информацию о текущем пользователе.
    """
    return current_user


# Импорт зависимости после определения функций
from api.deps import get_current_user