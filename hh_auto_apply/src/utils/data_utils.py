"""
Утилиты данных для HH Auto Apply
"""
import logging
import sqlite3
import json
import os
from typing import List, Dict, Any
from datetime import datetime


class AppliedVacanciesDB:
    """База данных для отслеживания отвеченных вакансий"""
    
    def __init__(self, db_path: str = "data/applied_vacancies.db"):
        """
        Инициализация базы данных
        
        Args:
            db_path (str): Путь к файлу базы данных SQLite
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._init_db()
        
    def _init_db(self):
        """Инициализация базы данных и создание таблиц"""
        try:
            # Создание директории данных, если она не существует
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Создание таблицы отвеченных вакансий
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS applied_vacancies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vacancy_id TEXT UNIQUE NOT NULL,
                    vacancy_url TEXT,
                    applied_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'applied'
                )
            ''')
            
            # Создание таблицы поисковых запросов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_name TEXT UNIQUE NOT NULL,
                    query_params TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            self.logger.info("База данных успешно инициализирована")
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации базы данных: {e}")
            
    def is_applied(self, vacancy_id: str) -> bool:
        """
        Проверка, откликались ли на вакансию
        
        Args:
            vacancy_id (str): ID вакансии для проверки
            
        Returns:
            bool: True если уже откликались, False в противном случае
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT 1 FROM applied_vacancies WHERE vacancy_id = ?", 
                (vacancy_id,)
            )
            
            result = cursor.fetchone() is not None
            conn.close()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка проверки отклика на вакансию: {e}")
            return False
            
    def add_applied(self, vacancy_id: str, vacancy_url: str = ""):
        """
        Добавление вакансии в список отвеченных
        
        Args:
            vacancy_id (str): ID вакансии
            vacancy_url (str): URL вакансии (опционально)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT OR IGNORE INTO applied_vacancies (vacancy_id, vacancy_url) VALUES (?, ?)",
                (vacancy_id, vacancy_url)
            )
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Вакансия {vacancy_id} добавлена в список отвеченных")
            
        except Exception as e:
            self.logger.error(f"Ошибка добавления отвеченной вакансии: {e}")
            
    def get_applied_vacancies(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Получение списка отвеченных вакансий
        
        Args:
            limit (int): Максимальное количество записей для возврата
            
        Returns:
            list: Список словарей с отвеченными вакансиями
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT vacancy_id, vacancy_url, applied_date, status FROM applied_vacancies ORDER BY applied_date DESC LIMIT ?",
                (limit,)
            )
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'vacancy_id': row[0],
                    'vacancy_url': row[1],
                    'applied_date': row[2],
                    'status': row[3]
                }
                for row in rows
            ]
            
        except Exception as e:
            self.logger.error(f"Ошибка получения отвеченных вакансий: {e}")
            return []


class SearchQueriesDB:
    """База данных для хранения поисковых запросов"""
    
    def __init__(self, db_path: str = "data/search_queries.db"):
        """
        Инициализация базы данных поисковых запросов
        
        Args:
            db_path (str): Путь к файлу базы данных SQLite
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._init_db()
        
    def _init_db(self):
        """Инициализация базы данных поисковых запросов"""
        try:
            # Создание директории данных, если она не существует
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Создание таблицы поисковых запросов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_name TEXT UNIQUE NOT NULL,
                    query_params TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            self.logger.info("База данных поисковых запросов успешно инициализирована")
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации базы данных поисковых запросов: {e}")
            
    def save_query(self, query_name: str, query_params: Dict[str, Any]) -> bool:
        """
        Сохранение поискового запроса
        
        Args:
            query_name (str): Название запроса
            query_params (dict): Параметры запроса
            
        Returns:
            bool: True если сохранение успешно, False в противном случае
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT OR REPLACE INTO search_queries (query_name, query_params) VALUES (?, ?)",
                (query_name, json.dumps(query_params))
            )
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Сохранен поисковый запрос: {query_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения поискового запроса: {e}")
            return False
            
    def load_query(self, query_name: str) -> Dict[str, Any]:
        """
        Загрузка поискового запроса
        
        Args:
            query_name (str): Название запроса для загрузки
            
        Returns:
            dict: Параметры запроса, пустой словарь если не найден
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT query_params FROM search_queries WHERE query_name = ?",
                (query_name,)
            )
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return json.loads(row[0])
            else:
                return {}
                
        except Exception as e:
            self.logger.error(f"Ошибка загрузки поискового запроса: {e}")
            return {}