"""
Настройка асинхронного подключения к PostgreSQL через SQLAlchemy.
"""
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Получение URL БД из переменных окружения
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    # Значение по умолчанию для разработки
    DATABASE_URL = "postgresql+asyncpg://hh_user:secret@postgres:5432/hh_autoapply"


# Создание асинхронного движка
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Включить для отладки SQL-запросов
    pool_pre_ping=True,
    pool_recycle=300,
)

# Фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """
    Dependency для FastAPI, предоставляет асинхронную сессию БД.
    
    Использование:
        @app.get("/items")
        async def read_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Инициализация БД (создание таблиц)."""
    from .models import Base
    async with engine.begin() as conn:
        # В продакшене используем Alembic миграции
        await conn.run_sync(Base.metadata.create_all)
        pass