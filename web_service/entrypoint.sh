#!/bin/sh
set -e

echo "[web] Starting web service..."

# Запускаем миграции
echo "[web] Running Alembic migrations..."
alembic upgrade head
echo "[web] Migrations done."

exec "$@"
