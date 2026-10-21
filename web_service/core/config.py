"""
Конфигурация приложения.
"""
import os
from typing import Optional

# Настройки Kafka
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC_JOBS = os.environ.get("KAFKA_TOPIC_JOBS", "apply-jobs")
KAFKA_TOPIC_RESULTS = os.environ.get("KAFKA_TOPIC_RESULTS", "apply-results")

# Настройки JWT
JWT_SECRET = os.environ.get("JWT_SECRET", "changeme_generate_with_openssl_rand")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", 10080))

# Настройки шифрования
FERNET_KEY = os.environ.get("FERNET_KEY", "changeme_generate_with_fernet_keygen")

# Настройки приложения
APP_NAME = "HH AutoApply Web"
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

# CORS origins
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8080",
]

# Настройки базы данных
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://hh_user:secret@postgres:5432/hh_autoapply")