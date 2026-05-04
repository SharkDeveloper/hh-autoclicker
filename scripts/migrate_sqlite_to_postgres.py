"""
Однократный скрипт миграции данных.
Читает data/applied_vacancies.db (SQLite) и импортирует историю
откликов в PostgreSQL таблицу applies.

Запуск: python scripts/migrate_sqlite_to_postgres.py
"""
import sqlite3
import psycopg2
import os
import sys
from datetime import datetime
from typing import List, Dict, Any

# Конфигурация PostgreSQL из переменных окружения
POSTGRES_URL = os.environ.get("DATABASE_URL", "postgresql://hh_user:secret@localhost:5432/hh_autoapply")
# Если URL начинается с postgresql://, заменим на postgres:// для psycopg2
if POSTGRES_URL.startswith("postgresql://"):
    POSTGRES_URL = POSTGRES_URL.replace("postgresql://", "postgres://", 1)

# Путь к SQLite базе
SQLITE_DB_PATH = "data/applied_vacancies.db"

def connect_sqlite():
    """Подключиться к SQLite базе."""
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"Файл SQLite базы не найден: {SQLITE_DB_PATH}")
        return None
    return sqlite3.connect(SQLITE_DB_PATH)


def connect_postgres():
    """Подключиться к PostgreSQL."""
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        return conn
    except Exception as e:
        print(f"Ошибка подключения к PostgreSQL: {e}")
        return None


def get_sqlite_schema(conn):
    """Получить схему таблиц SQLite."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Таблицы в SQLite:")
    for table in tables:
        print(f"  - {table[0]}")
    return tables


def migrate_applied_vacancies(sqlite_conn, pg_conn):
    """
    Мигрировать данные из таблицы applied_vacancies.
    
    Предполагаемая структура SQLite таблицы:
        applied_vacancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vacancy_id TEXT NOT NULL,
            account TEXT NOT NULL DEFAULT '',
            vacancy_url TEXT,
            applied_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'applied'
        )
    """
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    # Получаем все записи
    sqlite_cursor.execute("""
        SELECT vacancy_id, account, vacancy_url, applied_date, status
        FROM applied_vacancies
        ORDER BY applied_date
    """)
    
    records = sqlite_cursor.fetchall()
    print(f"Найдено {len(records)} записей в applied_vacancies")
    
    # Для миграции нужен user_id (системный пользователь-заглушка)
    # В реальном сценарии нужно сопоставить account с пользователем
    # Здесь создаём или находим системного пользователя
    system_user_id = "00000000-0000-0000-0000-000000000000"  # UUID заглушка
    system_job_id = "00000000-0000-0000-0000-000000000001"
    
    migrated = 0
    skipped = 0
    
    for record in records:
        vacancy_id, account, vacancy_url, applied_date, status = record
        
        # Преобразуем статус
        if status == "applied":
            new_status = "sent"
        else:
            new_status = "skipped"
        
        # Проверяем, есть ли уже такая запись в PostgreSQL (дедупликация)
        pg_cursor.execute(
            "SELECT 1 FROM applies WHERE vacancy_id = %s AND user_id = %s",
            (vacancy_id, system_user_id)
        )
        if pg_cursor.fetchone():
            skipped += 1
            continue
        
        # Вставляем запись
        try:
            pg_cursor.execute("""
                INSERT INTO applies 
                (id, job_id, user_id, vacancy_id, vacancy_url, vacancy_title, company, status, applied_at)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                system_job_id,
                system_user_id,
                vacancy_id,
                vacancy_url or f"https://hh.ru/vacancy/{vacancy_id}",
                "Unknown",  # vacancy_title
                "Unknown",  # company
                new_status,
                applied_date or datetime.utcnow()
            ))
            migrated += 1
        except Exception as e:
            print(f"Ошибка при вставке записи {vacancy_id}: {e}")
            pg_conn.rollback()
            return False
    
    pg_conn.commit()
    print(f"Мигрировано записей: {migrated}, пропущено (дубликаты): {skipped}")
    return True


def main():
    """Основная функция миграции."""
    print("=== Миграция данных из SQLite в PostgreSQL ===")
    
    # Подключаемся к SQLite
    sqlite_conn = connect_sqlite()
    if not sqlite_conn:
        sys.exit(1)
    
    # Подключаемся к PostgreSQL
    pg_conn = connect_postgres()
    if not pg_conn:
        sqlite_conn.close()
        sys.exit(1)
    
    try:
        # Показываем схему SQLite
        tables = get_sqlite_schema(sqlite_conn)
        
        # Мигрируем applied_vacancies
        if any("applied_vacancies" in table[0] for table in tables):
            print("\nМиграция таблицы applied_vacancies...")
            success = migrate_applied_vacancies(sqlite_conn, pg_conn)
            if not success:
                print("Миграция applied_vacancies не удалась")
        else:
            print("Таблица applied_vacancies не найдена в SQLite")
        
        # Другие таблицы можно добавить по аналогии
        
        print("\nМиграция завершена.")
        
    except Exception as e:
        print(f"Критическая ошибка при миграции: {e}")
        pg_conn.rollback()
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main()