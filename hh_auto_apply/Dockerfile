FROM python:3.10-slim-bullseye

# Копирование файла зависимостей
COPY requirements.txt ./
# Установка зависимостей Python
RUN pip install -r requirements.txt

# Копирование всех файлов приложения
COPY . .

# Команда запуска приложения
CMD ["python", "main.py"]