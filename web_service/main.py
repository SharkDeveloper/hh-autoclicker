"""
Точка входа FastAPI приложения для HH AutoApply Web Service.
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import logging

from api.routers import auth, settings, jobs, stats
from db.session import engine, Base
from kafka.consumer import start_kafka_consumer_background

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание приложения FastAPI
app = FastAPI(
    title="HH AutoApply API",
    description="API для автоматической подачи откликов на hh.ru",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware (для разработки)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])

# Монтирование статических файлов (Vue SPA)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/assets", StaticFiles(directory=static_dir), name="assets")
    logger.info(f"Статические файлы смонтированы на /assets из {static_dir}")
else:
    logger.warning(f"Директория static не найдена: {static_dir}")

# Catch-all маршрут для SPA (отдаёт index.html)
@app.get("/{full_path:path}")
async def serve_spa(full_path: str, request: Request):
    """
    Отдаёт index.html для всех путей, кроме /api/*.
    Это позволяет Vue Router обрабатывать клиентские маршруты.
    """
    if full_path.startswith("api/"):
        # API маршруты должны быть обработаны ранее
        return JSONResponse(
            status_code=404,
            content={"detail": f"API endpoint {full_path} not found"}
        )
    
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return JSONResponse(
            status_code=404,
            content={"detail": "SPA index.html not found"}
        )


@app.on_event("startup")
async def startup_event():
    """Действия при запуске приложения."""
    logger.info("Запуск HH AutoApply Web Service")
    
    # Создание таблиц БД (если не существуют)
    async with engine.begin() as conn:
        # В продакшене используем Alembic миграции, но для разработки можно создать таблицы
        await conn.run_sync(Base.metadata.create_all)
        pass
    
    # Запуск фоновой задачи Kafka consumer для приёма результатов
    await start_kafka_consumer_background()
    logger.info("Kafka consumer запущен в фоне")


@app.on_event("shutdown")
async def shutdown_event():
    """Действия при остановке приложения."""
    logger.info("Остановка HH AutoApply Web Service")


@app.get("/api/health")
async def health_check():
    """Эндпоинт для проверки здоровья сервиса."""
    return {
        "status": "healthy",
        "service": "hh-autoapply-web",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )