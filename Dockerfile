# ============================================================
# HH Auto Apply — Multi-stage Dockerfile
# Стадии:
#   base  — Python + Chromium + зависимости
#   test  — unit-тесты + dry-run проверка (CI/CD)
#   prod  — планировщик откликов (продакшн)
#   web   — веб-интерфейс управления (FastAPI + Jinja2)
# ============================================================

# ── BASE ────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS base

LABEL maintainer="hh-auto-apply"
LABEL description="HH.ru automated job application tool"

# Системные пакеты: Chromium + зависимости для headless-браузера
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    xdg-utils \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Пути к браузеру (используются session_manager.py)
ENV CHROMIUM_BINARY=/usr/bin/chromium \
    CHROMEDRIVER_BINARY=/usr/bin/chromedriver \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Устанавливаем Python-зависимости отдельным слоем (кешируется)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаём папки для данных и логов
RUN mkdir -p logs data


# ── TEST ────────────────────────────────────────────────────
FROM base AS test

LABEL stage="test"

# Устанавливаем pytest для запуска тестов
RUN pip install --no-cache-dir pytest pytest-cov

# Копируем тестовый энтрипоинт
COPY docker/test-entrypoint.sh /test-entrypoint.sh
RUN chmod +x /test-entrypoint.sh

# Переменные для интеграционного теста (dry-run)
# Задаются через docker-compose.yml → environment или .env
ENV HH_TEST_KEYWORDS="Python" \
    HH_TEST_AREA="1"

ENTRYPOINT ["/test-entrypoint.sh"]


# ── PROD ────────────────────────────────────────────────────
FROM base AS prod

LABEL stage="prod"

# Запускаем планировщик
ENTRYPOINT ["python3", "scheduler.py"]
CMD ["--interval", "36s"]


# ── WEB ────────────────────────────────────────────────────
FROM base AS web

LABEL stage="web"

# Устанавливаем зависимости веб-интерфейса
COPY web/requirements.txt /app/web/requirements.txt
RUN pip install --no-cache-dir -r /app/web/requirements.txt

# Копируем веб-файлы
COPY web /app/web

WORKDIR /app/web

# Порт для веб-сервера
EXPOSE 8000

# Запуск веб-сервера
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
