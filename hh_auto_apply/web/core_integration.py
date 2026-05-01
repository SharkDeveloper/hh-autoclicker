"""
Модуль интеграции веб-интерфейса с ядром автоотклика
Обеспечивает запуск существующего ядра HHAutoApply из веб-интерфейса
"""
import os
import sys
import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future

# Добавляем путь к родительскому каталогу для импорта модулей ядра
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.application import HHAutoApply
from src.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class CoreIntegration:
    """
    Класс для интеграции веб-интерфейса с ядром автоотклика
    
    Обеспечивает:
    1. Запуск ядра с различными параметрами
    2. Отслеживание статуса выполнения
    3. Сохранение результатов
    4. Управление параллельными задачами
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Инициализация интеграции
        
        Args:
            config_path: Путь к файлу конфигурации (по умолчанию config/default.json)
        """
        self.base_dir = Path(__file__).parent.parent
        self.config_path = config_path or str(self.base_dir / "config" / "default.json")
        self.accounts_path = self.base_dir / "config" / "accounts.json"
        self.data_dir = self.base_dir / "data"
        self.history_file = self.data_dir / "application_history.json"
        
        # Пул потоков для выполнения задач
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.active_tasks: Dict[str, Future] = {}
        
        # Инициализация истории
        self._init_history()
        
        logger.info(f"CoreIntegration инициализирован с конфигом: {self.config_path}")
    
    def _init_history(self):
        """Инициализация файла истории откликов"""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            if not self.history_file.exists():
                with open(self.history_file, 'w', encoding='utf-8') as f:
                    json.dump({"history": [], "statistics": {}}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка инициализации истории: {e}")
    
    def load_accounts(self) -> List[Dict[str, Any]]:
        """Загрузка списка аккаунтов из JSON файла"""
        try:
            with open(self.accounts_path, 'r', encoding='utf-8') as f:
                accounts = json.load(f)
            return accounts
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Ошибка загрузки аккаунтов: {e}")
            return []
    
    def get_account_by_id(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Получение аккаунта по индексу"""
        accounts = self.load_accounts()
        if 0 <= account_id < len(accounts):
            return accounts[account_id]
        return None
    
    def run_application(self, 
                       account_ids: Optional[List[int]] = None,
                       mode: str = "auto",
                       dry_run: bool = False,
                       search_filters: Optional[Dict[str, Any]] = None,
                       callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Запуск ядра автоотклика для указанных аккаунтов
        
        Args:
            account_ids: Список ID аккаунтов (индексы в accounts.json). Если None - все аккаунты
            mode: Режим работы ('auto', 'recommendations', 'manual')
            dry_run: Тестовый режим без реальных откликов
            search_filters: Дополнительные фильтры поиска
            callback: Функция обратного вызова для получения результатов
        
        Returns:
            Словарь с результатами выполнения
        """
        accounts = self.load_accounts()
        
        # Фильтрация аккаунтов
        if account_ids is not None:
            filtered_accounts = []
            for acc_id in account_ids:
                if 0 <= acc_id < len(accounts):
                    filtered_accounts.append(accounts[acc_id])
                else:
                    logger.warning(f"Аккаунт с ID {acc_id} не найден")
        else:
            filtered_accounts = [acc for acc in accounts if acc.get("enabled", True)]
        
        if not filtered_accounts:
            return {
                "success": False,
                "message": "Нет доступных аккаунтов для запуска",
                "results": []
            }
        
        logger.info(f"Запуск ядра для {len(filtered_accounts)} аккаунтов, режим: {mode}")
        
        results = []
        total_success = 0
        total_failed = 0
        
        for i, account in enumerate(filtered_accounts):
            account_name = account.get("name", account.get("username", f"Аккаунт {i}"))
            logger.info(f"Обработка аккаунта {i+1}/{len(filtered_accounts)}: {account_name}")
            
            try:
                # Создание экземпляра приложения
                app = HHAutoApply(self.config_path)
                
                # Запуск ядра
                start_time = time.time()
                result = app.run(
                    mode=mode,
                    search_criteria=search_filters or account.get("search_filters"),
                    dry_run=dry_run,
                    account_override=account
                )
                elapsed_time = time.time() - start_time
                
                # Формирование результата
                account_result = {
                    "account_name": account_name,
                    "username": account.get("username"),
                    "success": result.get("success", 0),
                    "failed": result.get("failed", 0),
                    "errors": result.get("errors", []),
                    "elapsed_time": round(elapsed_time, 2),
                    "timestamp": datetime.now().isoformat(),
                    "dry_run": dry_run,
                    "mode": mode
                }
                
                results.append(account_result)
                total_success += result.get("success", 0)
                total_failed += result.get("failed", 0)
                
                # Сохранение в историю
                self._save_to_history(account_result)
                
                # Вызов callback если предоставлен
                if callback:
                    callback(account_result)
                
                logger.info(f"Аккаунт {account_name} завершен: {result.get('success', 0)} успешно, {result.get('failed', 0)} ошибок")
                
                # Пауза между аккаунтами (если не последний)
                if i < len(filtered_accounts) - 1:
                    time.sleep(30)  # 30 секунд паузы между аккаунтами
                    
            except Exception as e:
                logger.error(f"Критическая ошибка при обработке аккаунта {account_name}: {e}")
                error_result = {
                    "account_name": account_name,
                    "username": account.get("username"),
                    "success": 0,
                    "failed": 0,
                    "errors": [str(e)],
                    "elapsed_time": 0,
                    "timestamp": datetime.now().isoformat(),
                    "dry_run": dry_run,
                    "mode": mode
                }
                results.append(error_result)
                total_failed += 1
        
        final_result = {
            "success": True,
            "message": f"Обработано {len(filtered_accounts)} аккаунтов",
            "total_success": total_success,
            "total_failed": total_failed,
            "total_accounts": len(filtered_accounts),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
        return final_result
    
    def run_application_async(self, 
                             account_ids: Optional[List[int]] = None,
                             mode: str = "auto",
                             dry_run: bool = False,
                             search_filters: Optional[Dict[str, Any]] = None,
                             callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> str:
        """
        Асинхронный запуск ядра автоотклика
        
        Returns:
            ID задачи для отслеживания статуса
        """
        task_id = f"task_{int(time.time())}_{len(self.active_tasks)}"
        
        def task_wrapper():
            try:
                result = self.run_application(
                    account_ids=account_ids,
                    mode=mode,
                    dry_run=dry_run,
                    search_filters=search_filters,
                    callback=callback
                )
                return result
            except Exception as e:
                logger.error(f"Ошибка в асинхронной задаче {task_id}: {e}")
                return {
                    "success": False,
                    "message": str(e),
                    "results": []
                }
        
        # Запуск задачи в пуле потоков
        future = self.executor.submit(task_wrapper)
        self.active_tasks[task_id] = future
        
        # Очистка завершенных задач
        self._cleanup_completed_tasks()
        
        logger.info(f"Запущена асинхронная задача {task_id}")
        return task_id
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Получение статуса задачи
        
        Returns:
            Словарь со статусом задачи
        """
        if task_id not in self.active_tasks:
            return {
                "task_id": task_id,
                "status": "not_found",
                "message": "Задача не найдена"
            }
        
        future = self.active_tasks[task_id]
        
        if future.done():
            try:
                result = future.result(timeout=1)
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "result": result
                }
            except Exception as e:
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e)
                }
        else:
            return {
                "task_id": task_id,
                "status": "running",
                "message": "Задача выполняется"
            }
    
    def cancel_task(self, task_id: str) -> bool:
        """Отмена задачи"""
        if task_id in self.active_tasks:
            future = self.active_tasks[task_id]
            if not future.done():
                future.cancel()
                logger.info(f"Задача {task_id} отменена")
                return True
        return False
    
    def _cleanup_completed_tasks(self):
        """Очистка завершенных задач из словаря active_tasks"""
        completed = []
        for task_id, future in self.active_tasks.items():
            if future.done():
                completed.append(task_id)
        
        for task_id in completed:
            del self.active_tasks[task_id]
        
        if completed:
            logger.debug(f"Очищено завершенных задач: {len(completed)}")
    
    def _save_to_history(self, result: Dict[str, Any]):
        """Сохранение результата в историю"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            history_data["history"].append(result)
            
            # Обновление статистики
            stats = history_data.get("statistics", {})
            date_today = datetime.now().strftime("%Y-%m-%d")
            if date_today not in stats:
                stats[date_today] = {"success": 0, "failed": 0, "accounts": 0}
            
            stats[date_today]["success"] += result.get("success", 0)
            stats[date_today]["failed"] += result.get("failed", 0)
            stats[date_today]["accounts"] += 1
            
            history_data["statistics"] = stats
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Ошибка сохранения в историю: {e}")
    
    def get_history(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Получение истории откликов"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            history = history_data.get("history", [])
            statistics = history_data.get("statistics", {})
            
            # Применение пагинации
            start = offset
            end = offset + limit
            paginated_history = history[start:end] if start < len(history) else []
            
            return {
                "total": len(history),
                "limit": limit,
                "offset": offset,
                "history": paginated_history,
                "statistics": statistics
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки истории: {e}")
            return {"total": 0, "history": [], "statistics": {}}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики откликов"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            statistics = history_data.get("statistics", {})
            
            # Расчет общей статистики
            total_success = 0
            total_failed = 0
            total_accounts = 0
            
            for day_stats in statistics.values():
                total_success += day_stats.get("success", 0)
                total_failed += day_stats.get("failed", 0)
                total_accounts += day_stats.get("accounts", 0)
            
            return {
                "daily": statistics,
                "total": {
                    "success": total_success,
                    "failed": total_failed,
                    "accounts": total_accounts,
                    "success_rate": total_success / (total_success + total_failed) if (total_success + total_failed) > 0 else 0
                }
            }
        except Exception as e:
            logger.error(f"Ошибка загрузки статистики: {e}")
            return {"daily": {}, "total": {}}
    
    def cleanup(self):
        """Очистка ресурсов"""
        self.executor.shutdown(wait=False)
        logger.info("CoreIntegration очищен")

# Глобальный экземпляр для использования в веб-интерфейсе
core_integration = CoreIntegration()