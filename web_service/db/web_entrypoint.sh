#!/bin/sh
set -e

echo "[web] Starting web service..."

# Ждём PostgreSQL
echo "[web] Waiting for PostgreSQL..."
until pg_isready -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" 2>/dev/null; do
  echo "[web] PostgreSQL not ready, retrying in 2s..."
  sleep 2
done
echo "[web] PostgreSQL is ready."

# Ждём Kafka
echo "[web] Waiting for Kafka..."
until /opt/kafka-check.sh 2>/dev/null; do
  echo "[web] Kafka not ready, retrying in 3s..."
  sleep 3
done
echo "[web] Kafka is ready."

# Запускаем миграции
echo "[web] Running Alembic migrations..."
alembic upgrade head
echo "[web] Migrations done."

# Запускаем сервер
echo "[web] Starting uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
