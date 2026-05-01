"""
Менеджер задач для веб-интерфейса HH Auto Apply
Управляет асинхронным выполнением задач откликов и предоставляет API для отслеживания статуса
"""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from core_integration import CoreIntegration

logger = logging.getLogger(__name__)

class JobStatus(str, Enum):
    """Статусы задачи"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Job:
    """Класс задачи"""
    job_id: str
    name: str
    account_ids: Optional[List[int]]
    mode: str
    dry_run: bool
    search_filters: Optional[Dict[str, Any]]
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    logs: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование задачи в словарь"""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "account_ids": self.account_ids,
            "mode": self.mode,
            "dry_run": self.dry_run,
            "search_filters": self.search_filters,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "logs": self.logs[-50:],  # Последние 50 логов
            "duration": self._calculate_duration()
        }
    
    def _calculate_duration(self) -> Optional[float]:
        """Расчет продолжительности выполнения задачи"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return None
    
    def add_log(self, message: str):
        """Добавление лога в задачу"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        logger.info(f"Job {self.job_id}: {message}")

class JobManager:
    """
    Менеджер задач для управления асинхронным выполнением откликов
    
    Обеспечивает:
    1. Создание и запуск задач
    2. Отслеживание статуса задач
    3. Управление задачами (пауза, отмена)
    4. Хранение истории задач
    5. Real-time обновления через WebSocket
    """
    
    def __init__(self, core_integration: Optional[CoreIntegration] = None):
        """
        Инициализация менеджера задач
        
        Args:
            core_integration: Экземпляр CoreIntegration для запуска ядра
        """
        self.core_integration = core_integration or CoreIntegration()
        self.jobs: Dict[str, Job] = {}
        self.executor = ThreadPoolExecutor(max_workers=3)
        self._callbacks: List[Callable[[Job], None]] = []
        
        logger.info("JobManager инициализирован")
    
    def create_job(self,
                  name: str,
                  account_ids: Optional[List[int]] = None,
                  mode: str = "auto",
                  dry_run: bool = False,
                  search_filters: Optional[Dict[str, Any]] = None) -> Job:
        """
        Создание новой задачи
        
        Args:
            name: Название задачи
            account_ids: Список ID аккаунтов
            mode: Режим работы
            dry_run: Тестовый режим
            search_filters: Фильтры поиска
        
        Returns:
            Созданная задача
        """
        job_id = str(uuid.uuid4())[:8]
        
        job = Job(
            job_id=job_id,
            name=name,
            account_ids=account_ids,
            mode=mode,
            dry_run=dry_run,
            search_filters=search_filters
        )
        
        self.jobs[job_id] = job
        job.add_log(f"Задача создана: {name}")
        
        logger.info(f"Создана задача {job_id}: {name}")
        
        # Запуск задачи асинхронно
        asyncio.create_task(self._run_job_async(job))
        
        return job
    
    async def _run_job_async(self, job: Job):
        """Асинхронный запуск задачи"""
        try:
            # Обновление статуса
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            job.progress = 10.0
            job.add_log("Задача запущена")
            
            # Вызов callback
            self._notify_callbacks(job)
            
            # Запуск ядра в отдельном потоке
            loop = asyncio.get_event_loop()
            
            def run_core_integration():
                """Функция для запуска в потоке"""
                try:
                    # Callback для обновления прогресса
                    def progress_callback(result: Dict[str, Any]):
                        job.add_log(f"Аккаунт {result.get('account_name')} завершен: {result.get('success')} успешно")
                        job.progress = min(90.0, job.progress + 30.0)  # Увеличиваем прогресс
                        self._notify_callbacks(job)
                    
                    # Запуск ядра
                    return self.core_integration.run_application(
                        account_ids=job.account_ids,
                        mode=job.mode,
                        dry_run=job.dry_run,
                        search_filters=job.search_filters,
                        callback=progress_callback
                    )
                except Exception as e:
                    logger.error(f"Ошибка в задаче {job.job_id}: {e}")
                    raise
            
            # Выполнение в потоке
            result = await loop.run_in_executor(self.executor, run_core_integration)
            
            # Обновление результата
            job.result = result
            job.progress = 100.0
            job.status = JobStatus.COMPLETED if result.get("success", False) else JobStatus.FAILED
            job.completed_at = datetime.now()
            
            if result.get("success", False):
                job.add_log(f"Задача успешно завершена: {result.get('total_success', 0)} успешных откликов")
            else:
                job.add_log(f"Задача завершена с ошибками: {result.get('message', 'Неизвестная ошибка')}")
            
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            job.add_log("Задача отменена")
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now()
            job.add_log(f"Ошибка выполнения задачи: {e}")
            logger.error(f"Ошибка выполнения задачи {job.job_id}: {e}", exc_info=True)
        finally:
            # Вызов callback
            self._notify_callbacks(job)
            
            # Очистка старых задач (сохраняем последние 100)
            self._cleanup_old_jobs()
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Получение задачи по ID"""
        return self.jobs.get(job_id)
    
    def get_all_jobs(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Получение всех задач с пагинацией"""
        jobs_list = list(self.jobs.values())
        jobs_list.sort(key=lambda j: j.created_at, reverse=True)
        
        total = len(jobs_list)
        start = offset
        end = offset + limit
        paginated_jobs = jobs_list[start:end] if start < total else []
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "jobs": [job.to_dict() for job in paginated_jobs]
        }
    
    def get_active_jobs(self) -> List[Dict[str, Any]]:
        """Получение активных задач (выполняющихся)"""
        active = []
        for job in self.jobs.values():
            if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
                active.append(job.to_dict())
        return active
    
    def cancel_job(self, job_id: str) -> bool:
        """Отмена задачи"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
            # TODO: Реализовать фактическую отмену выполнения
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            job.add_log("Задача отменена пользователем")
            self._notify_callbacks(job)
            return True
        
        return False
    
    def delete_job(self, job_id: str) -> bool:
        """Удаление задачи"""
        if job_id in self.jobs:
            del self.jobs[job_id]
            logger.info(f"Задача {job_id} удалена")
            return True
        return False
    
    def register_callback(self, callback: Callable[[Job], None]):
        """Регистрация callback для обновлений задач"""
        self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable[[Job], None]):
        """Удаление callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_callbacks(self, job: Job):
        """Уведомление всех зарегистрированных callback"""
        for callback in self._callbacks:
            try:
                callback(job)
            except Exception as e:
                logger.error(f"Ошибка в callback: {e}")
    
    def _cleanup_old_jobs(self):
        """Очистка старых задач (оставляем последние 100)"""
        if len(self.jobs) > 100:
            # Сортируем по дате создания и оставляем последние 100
            sorted_jobs = sorted(self.jobs.items(), key=lambda x: x[1].created_at)
            jobs_to_remove = sorted_jobs[:-100]
            
            for job_id, _ in jobs_to_remove:
                del self.jobs[job_id]
            
            logger.info(f"Очищено {len(jobs_to_remove)} старых задач")
    
    async def stream_job_updates(self, job_id: str) -> AsyncGenerator[str, None]:
        """
        Потоковая передача обновлений задачи
        
        Args:
            job_id: ID задачи
        
        Yields:
            JSON строки с обновлениями задачи
        """
        job = self.get_job(job_id)
        if not job:
            yield json.dumps({"error": "Задача не найдена"})
            return
        
        # Отправляем текущее состояние
        yield json.dumps(job.to_dict())
        
        # Создаем callback для получения обновлений
        update_queue = asyncio.Queue()
        
        def on_job_update(updated_job: Job):
            if updated_job.job_id == job_id:
                asyncio.create_task(update_queue.put(updated_job.to_dict()))
        
        self.register_callback(on_job_update)
        
        try:
            # Отправляем обновления пока задача активна
            while job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
                try:
                    # Ждем обновления с таймаутом
                    update = await asyncio.wait_for(update_queue.get(), timeout=30.0)
                    yield json.dumps(update)
                    
                    # Обновляем локальную ссылку на задачу
                    job = self.get_job(job_id)
                    if not job or job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
                        break
                        
                except asyncio.TimeoutError:
                    # Отправляем heartbeat для поддержания соединения
                    yield json.dumps({"heartbeat": datetime.now().isoformat()})
        finally:
            self.unregister_callback(on_job_update)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики по задачам"""
        total = len(self.jobs)
        completed = sum(1 for j in self.jobs.values() if j.status == JobStatus.COMPLETED)
        failed = sum(1 for j in self.jobs.values() if j.status == JobStatus.FAILED)
        running = sum(1 for j in self.jobs.values() if j.status == JobStatus.RUNNING)
        cancelled = sum(1 for j in self.jobs.values() if j.status == JobStatus.CANCELLED)
        
        # Статистика по успешным откликам
        total_success = 0
        total_failed = 0
        
        for job in self.jobs.values():
            if job.result and isinstance(job.result, dict):
                total_success += job.result.get("total_success", 0)
                total_failed += job.result.get("total_failed", 0)
        
        return {
            "jobs": {
                "total": total,
                "completed": completed,
                "failed": failed,
                "running": running,
                "cancelled": cancelled,
                "success_rate": completed / total if total > 0 else 0
            },
            "applications": {
                "total_success": total_success,
                "total_failed": total_failed,
                "success_rate": total_success / (total_success + total_failed) if (total_success + total_failed) > 0 else 0
            }
        }
    
    def cleanup(self):
        """Очистка ресурсов"""
        self.executor.shutdown(wait=False)
        logger.info("JobManager очищен")

# Глобальный экземпляр для использования в веб-интерфейсе
job_manager = JobManager()