#!/usr/bin/env bash
# ============================================================
# Тестовый энтрипоинт для стадии test
# Шаги:
#   1. Юнит-тесты (без браузера, без учётных данных)
#   2. Интеграционный dry-run (с браузером, только если заданы HH_USERNAME / HH_PASSWORD)
# Любой упавший шаг прекращает выполнение (exit != 0)
# ============================================================
set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

banner() { echo -e "\n${CYAN}══════════════════════════════${NC}"; echo -e "${CYAN} $1${NC}"; echo -e "${CYAN}══════════════════════════════${NC}\n"; }
ok()     { echo -e "${GREEN}✓ $1${NC}"; }
warn()   { echo -e "${YELLOW}⚠ $1${NC}"; }
fail()   { echo -e "${RED}✗ $1${NC}"; exit 1; }

# ── Шаг 1: Проверка окружения ────────────────────────────
banner "Шаг 1: Проверка окружения"

python3 --version       && ok "Python доступен"
chromium --version 2>/dev/null && ok "Chromium доступен" || fail "Chromium не найден"
chromedriver --version 2>/dev/null && ok "ChromeDriver доступен" || fail "ChromeDriver не найден"

# Проверяем, что версии Chromium и chromedriver совпадают
CHROME_VER=$(chromium --version 2>/dev/null | grep -oP '\d+' | head -1)
DRIVER_VER=$(chromedriver --version 2>/dev/null | grep -oP '\d+' | head -1)
if [ "$CHROME_VER" != "$DRIVER_VER" ]; then
    fail "Версии Chromium ($CHROME_VER) и ChromeDriver ($DRIVER_VER) не совпадают"
fi
ok "Версии браузера и драйвера совпадают: $CHROME_VER"

# ── Шаг 2: Юнит-тесты ────────────────────────────────────
banner "Шаг 2: Юнит-тесты (pytest)"

pytest tests/ \
    --tb=short \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=xml:/app/coverage.xml \
    -q \
    && ok "Все юнит-тесты прошли" \
    || fail "Юнит-тесты завершились с ошибками"

# ── Шаг 3: Интеграционный dry-run ────────────────────────
banner "Шаг 3: Интеграционный dry-run"

if [ -z "${HH_USERNAME:-}" ] || [ -z "${HH_PASSWORD:-}" ]; then
    warn "HH_USERNAME / HH_PASSWORD не заданы — интеграционный тест пропущен"
    warn "Установите переменные среды для полной проверки:"
    warn "  HH_USERNAME=your@email.com HH_PASSWORD=your_pass docker compose --profile test up"
else
    KEYWORDS="${HH_TEST_KEYWORDS:-Python}"
    AREA="${HH_TEST_AREA:-1}"
    echo "Запуск dry-run: keywords='${KEYWORDS}', area=${AREA}"

    python3 main.py \
        --dry-run \
        --keywords "${KEYWORDS}" \
        --area "${AREA}" \
        && ok "Интеграционный dry-run прошёл успешно" \
        || fail "Интеграционный dry-run завершился с ошибкой"
fi

# ── Итог ─────────────────────────────────────────────────
banner "Результат"
ok "Все проверки пройдены — образ готов к продакшену"
