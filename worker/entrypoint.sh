#!/bin/sh
set -e

# Проверяем Chromium
echo "[worker] Checking Chromium..."
if [ ! -f "$CHROMIUM_BINARY" ]; then
  echo "[worker] ERROR: Chromium not found at $CHROMIUM_BINARY"
  exit 1
fi
echo "[worker] Chromium OK: $CHROMIUM_BINARY"

exec "$@"