"""
Точка входа FastAPI-приложения для веб-сервиса HH AutoApply.
"""
import os
import logging
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from api.routers import auth, settings, jobs, stats
from db.session import engine
from db.models import Base
from messaging.consumer import start_kafka_consumer_background

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HH AutoApply API",
    description="API для автоматической подачи откликов на hh.ru",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/assets", StaticFiles(directory=static_dir), name="assets")
    logger.info(f"Статические файлы смонтированы в /assets из {static_dir}")
else:
    logger.warning(f"Директория static не найдена: {static_dir}")


# ВАЖНО: все /api/* маршруты должны быть объявлены ВЫШЕ catch-all
# @app.get("/{full_path:path}") — иначе health и прочие API-ручки вернут 404.
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "hh-autoapply-web",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/{full_path:path}")
async def serve_spa(full_path: str, request: Request):
    if full_path.startswith("api/"):
        return JSONResponse(
            status_code=404,
            content={"detail": f"API endpoint {full_path} not found"},
        )

    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse(
        status_code=404,
        content={"detail": "SPA index.html not found"},
    )


@app.on_event("startup")
async def startup_event():
    logger.info("Запуск HH AutoApply Web Service")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Страховка для существующих БД (созданных до появления колонок):
        await conn.exec_driver_sql(
            "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS error TEXT"
        )

    # Запускаем блокирующий Kafka consumer в executor, не блокируя startup
    await start_kafka_consumer_background()
    logger.info("Kafka consumer запущен в фоновом режиме")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Остановка HH AutoApply Web Service")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
