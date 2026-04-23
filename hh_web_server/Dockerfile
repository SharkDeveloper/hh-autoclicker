FROM python:3.11-slim-bookworm

WORKDIR /app

# Установка системных зависимостей для Selenium и PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    curl \
    ca-certificates \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    libxext6 \
    libxrender1 \
    libxtst6 \
    libx11-xcb1 \
    libxcb1 \
    libasound2 \
    xvfb \
    fonts-liberation \
    xdg-utils \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Установка Google Chrome для Debian Bookworm
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Установка ChromeDriver через пакет chromium-driver (совместим с версией Chrome в репозитории)
RUN apt-get update && apt-get install -y chromium-driver && \
    rm -rf /var/lib/apt/lists/* && \
    ln -sf /usr/bin/chromedriver /usr/local/bin/chromedriver

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Сборка статических файлов
RUN python manage.py collectstatic --noinput

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "hh_web.wsgi:application"]
