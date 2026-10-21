FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей (для psycopg2 и других)
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1ёё

ENTRYPOINT ["/entrypoint.sh"]

# Запуск приложения с миграциями
CMD ["uvicorn main:app --host 0.0.0.0 --port 8000"]