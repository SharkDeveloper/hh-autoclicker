"""
Утилиты для работы с PostgreSQL в worker-сервисе.
Содержит функции для проверки откликов, сохранения результатов и обновления статусов задач.
"""
import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def get_db_connection():
    """
    Получить соединение с PostgreSQL из DATABASE_URL env.
    
    Returns:
        psycopg2.connection: Соединение с базой данных.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Если URL начинается с postgresql://, заменим на postgres:// для psycopg2
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgres://", 1)
    
    conn = psycopg2.connect(database_url)
    return conn


def is_already_applied(conn, user_id: str, vacancy_id: str) -> bool:
    """
    Проверить, был ли уже отклик на вакансию.
    
    Args:
        conn: соединение с PostgreSQL
        user_id: UUID пользователя
        vacancy_id: строковый ID вакансии hh.ru
    
    Returns:
        True если отклик уже был, иначе False.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM applies WHERE user_id = %s AND vacancy_id = %s LIMIT 1",
                (user_id, vacancy_id)
            )
            return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка при проверке отклика: {e}")
        # В случае ошибки считаем, что отклика не было, чтобы не пропустить вакансию
        return False


def save_apply_result(conn, job_id: str, user_id: str, vacancy_data: dict) -> None:
    """
    Записать результат отклика в таблицу applies.
    
    Args:
        conn: соединение с PostgreSQL
        job_id: UUID задачи
        user_id: UUID пользователя
        vacancy_data: словарь с данными вакансии:
            - vacancy_id (str)
            - vacancy_url (str)
            - vacancy_title (str)
            - company (str)
            - status (str): 'sent', 'skipped', 'error'
            - error_msg (str, optional)
    """
    required = ['vacancy_id', 'vacancy_url', 'vacancy_title', 'company', 'status']
    for field in required:
        if field not in vacancy_data:
            raise ValueError(f"Missing required field '{field}' in vacancy_data")
    
    vacancy_id = vacancy_data['vacancy_id']
    vacancy_url = vacancy_data['vacancy_url']
    vacancy_title = vacancy_data['vacancy_title']
    company = vacancy_data['company']
    status = vacancy_data['status']
    error_msg = vacancy_data.get('error_msg')
    applied_at = datetime.utcnow()
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO applies 
                (job_id, user_id, vacancy_id, vacancy_url, vacancy_title, company, status, error_msg, applied_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, vacancy_id) DO NOTHING
            """, (job_id, user_id, vacancy_id, vacancy_url, vacancy_title, company, status, error_msg, applied_at))
        conn.commit()
        logger.debug(f"Сохранён результат отклика: {vacancy_id} статус {status}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении результата отклика: {e}")
        conn.rollback()
        raise


def update_job_status(conn, job_id: str, status: str, finished_at=None) -> None:
    """
    Обновить статус задачи в таблице jobs.
    
    Args:
        conn: соединение с PostgreSQL
        job_id: UUID задачи
        status: новый статус ('pending', 'running', 'done', 'failed')
        finished_at: datetime завершения (опционально, для статусов done/failed)
    """
    valid_statuses = {'pending', 'running', 'done', 'failed'}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of {valid_statuses}")
    
    try:
        with conn.cursor() as cur:
            if status == 'running':
                cur.execute("""
                    UPDATE jobs 
                    SET status = %s, started_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                """, (status, job_id))
            elif status in ('done', 'failed'):
                if finished_at is None:
                    finished_at = datetime.utcnow()
                cur.execute("""
                    UPDATE jobs 
                    SET status = %s, finished_at = %s 
                    WHERE id = %s
                """, (status, finished_at, job_id))
            else:
                cur.execute("""
                    UPDATE jobs SET status = %s WHERE id = %s
                """, (status, job_id))
        conn.commit()
        logger.info(f"Обновлён статус задачи {job_id} на '{status}'")
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса задачи: {e}")
        conn.rollback()
        raise