#!/bin/sh
set -e

echo "[worker] Starting worker service..."

# Ждём PostgreSQL
echo "[worker] Waiting for PostgreSQL..."
until pg_isready -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" 2>/dev/null; do
  echo "[worker] PostgreSQL not ready, retrying in 2s..."
  sleep 2
done
echo "[worker] PostgreSQL is ready."

# Ждём Kafka
echo "[worker] Waiting for Kafka..."
KAFKA_HOST=$(echo "$KAFKA_BOOTSTRAP_SERVERS" | cut -d: -f1)
KAFKA_PORT=$(echo "$KAFKA_BOOTSTRAP_SERVERS" | cut -d: -f2)
until nc -z "$KAFKA_HOST" "$KAFKA_PORT" 2>/dev/null; do
  echo "[worker] Kafka not ready, retrying in 3s..."
  sleep 3
done
echo "[worker] Kafka is ready."

# Проверяем Chromium
echo "[worker] Checking Chromium..."
if [ ! -f "$CHROMIUM_BINARY" ]; then
  echo "[worker] ERROR: Chromium not found at $CHROMIUM_BINARY"
  exit 1
fi
echo "[worker] Chromium OK: $CHROMIUM_BINARY"

# Запускаем воркер
echo "[worker] Starting autoclicker..."
exec python main.py
