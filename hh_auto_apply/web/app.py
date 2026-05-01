"""
Веб-интерфейс для управления ядром автоотклика HH Auto Apply
Основное FastAPI приложение
"""
import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, Request, Form, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
import uvicorn

# Добавляем путь к родительскому каталогу для импорта модулей ядра
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.application import HHAutoApply
from src.core.config_manager import ConfigManager

# Импорт модулей веб-интерфейса
from core_integration import CoreIntegration, core_integration
from job_manager import JobManager, JobStatus, job_manager

# Инициализация логгера
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/web_interface.log", encoding="utf-8"),
    ]
)

# Создание FastAPI приложения
app = FastAPI(
    title="HH Auto Apply Web Interface",
    description="Веб-интерфейс для управления автоматическим откликом на вакансии hh.ru",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Монтирование статических файлов
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Инициализация Jinja2 шаблонов
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Конфигурационные пути
BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config" / "default.json"
ACCOUNTS_PATH = BASE_DIR / "config" / "accounts.json"
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = DATA_DIR / "templates"

# Инициализация менеджеров
core_integration = CoreIntegration()
job_manager = JobManager(core_integration)

# Модели данных Pydantic
class AccountCreate(BaseModel):
    name: str = Field(..., description="Название аккаунта")
    username: str = Field(..., description="Email/логин для входа на hh.ru")
    password: str = Field(..., description="Пароль")
    resume_id: Optional[str] = Field(None, description="ID резюме на hh.ru")
    cover_letter: Optional[str] = Field(None, description="Текст сопроводительного письма")
    search_filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Фильтры поиска")
    enabled: bool = Field(True, description="Аккаунт активен")

class JobRequest(BaseModel):
    name: str = Field(..., description="Название задачи")
    account_ids: Optional[List[int]] = Field(None, description="ID аккаунтов для запуска (пусто = все)")
    mode: str = Field("auto", description="Режим работы: auto, recommendations, manual")
    dry_run: bool = Field(False, description="Тестовый режим без реальных откликов")
    search_filters: Optional[Dict[str, Any]] = Field(None, description="Дополнительные фильтры поиска")

class CoverLetterTemplate(BaseModel):
    name: str = Field(..., description="Название шаблона")
    content: str = Field(..., description="Текст шаблона")
    variables: Optional[List[str]] = Field(default_factory=list, description="Доступные переменные")

# Вспомогательные функции
def load_accounts() -> List[Dict[str, Any]]:
    """Загрузка списка аккаунтов из JSON файла"""
    try:
        with open(ACCOUNTS_PATH, 'r', encoding='utf-8') as f:
            accounts = json.load(f)
        return accounts
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Ошибка загрузки аккаунтов: {e}")
        return []

def save_accounts(accounts: List[Dict[str, Any]]) -> bool:
    """Сохранение списка аккаунтов в JSON файл"""
    try:
        with open(ACCOUNTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения аккаунтов: {e}")
        return False

def load_cover_letter_templates() -> List[Dict[str, Any]]:
    """Загрузка шаблонов сопроводительных писем"""
    templates_list = []
    if TEMPLATES_DIR.exists():
        for file in TEMPLATES_DIR.glob("*.txt"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                templates_list.append({
                    "name": file.stem,
                    "filename": file.name,
                    "content": content,
                    "variables": extract_variables(content)
                })
            except Exception as e:
                logger.error(f"Ошибка чтения шаблона {file}: {e}")
    return templates_list

def extract_variables(text: str) -> List[str]:
    """Извлечение переменных из текста шаблона (формат {variable})"""
    import re
    return re.findall(r'\{(\w+)\}', text)

# WebSocket менеджер для real-time обновлений
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_message(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                self.disconnect(connection)

manager = ConnectionManager()

# Тестовый маршрут для проверки работы сервера
@app.get("/test")
async def test_route():
    """Тестовый маршрут для проверки работы сервера"""
    return {"message": "Сервер работает", "status": "ok"}

# Маршруты веб-интерфейса
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница веб-интерфейса"""
    accounts = load_accounts()
    templates_list = load_cover_letter_templates()
    
    # Загрузка конфигурации
    config = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except:
            pass
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "accounts": accounts,
            "letter_templates": templates_list,
            "config": json.dumps(config) if config else "{}",
            "total_accounts": len(accounts),
            "active_accounts": len([a for a in accounts if a.get("enabled", True)])
        }
    )

@app.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request):
    """Страница управления аккаунтами"""
    accounts = load_accounts()
    return templates.TemplateResponse(
        "accounts.html",
        {"request": request, "accounts": accounts}
    )

@app.get("/jobs", response_class=HTMLResponse)
async def jobs_page(request: Request):
    """Страница управления задачами"""
    return templates.TemplateResponse(
        "jobs.html",
        {"request": request}
    )

@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """Страница истории откликов"""
    history = core_integration.get_history(limit=50)
    return templates.TemplateResponse(
        "history.html",
        {"request": request, "history": history.get("history", [])}
    )

@app.get("/templates", response_class=HTMLResponse)
async def templates_page(request: Request):
    """Страница управления шаблонами сопроводительных писем"""
    templates_list = load_cover_letter_templates()
    return templates.TemplateResponse(
        "templates.html",
        {"request": request, "letter_templates": templates_list}
    )

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Страница настроек"""
    config = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except:
            pass
    
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "config": config}
    )

# API эндпоинты
@app.get("/api/status")
async def get_status():
    """Получение статуса системы"""
    return {
        "status": "active",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "web_interface": "active",
            "core_integration": "active",
            "job_manager": "active"
        }
    }

@app.get("/api/accounts")
async def get_accounts():
    """Получение списка всех аккаунтов"""
    return {"accounts": load_accounts()}

@app.get("/api/accounts/{account_id}")
async def get_account(account_id: int):
    """Получение конкретного аккаунта по ID"""
    accounts = load_accounts()
    if account_id < 0 or account_id >= len(accounts):
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    return accounts[account_id]

@app.post("/api/accounts")
async def create_account(account: AccountCreate):
    """Создание нового аккаунта"""
    accounts = load_accounts()
    
    # Проверка на дубликат username
    if any(a.get("username") == account.username for a in accounts):
        raise HTTPException(status_code=400, detail="Аккаунт с таким username уже существует")
    
    new_account = account.dict()
    accounts.append(new_account)
    
    if save_accounts(accounts):
        return {"message": "Аккаунт успешно создан", "account": new_account}
    else:
        raise HTTPException(status_code=500, detail="Ошибка сохранения аккаунта")

@app.put("/api/accounts/{account_id}")
async def update_account(account_id: int, account: AccountCreate):
    """Обновление существующего аккаунта"""
    accounts = load_accounts()
    
    if account_id < 0 or account_id >= len(accounts):
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    
    accounts[account_id] = account.dict()
    
    if save_accounts(accounts):
        return {"message": "Аккаунт успешно обновлен", "account": accounts[account_id]}
    else:
        raise HTTPException(status_code=500, detail="Ошибка сохранения аккаунта")

@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: int):
    """Удаление аккаунта"""
    accounts = load_accounts()
    
    if account_id < 0 or account_id >= len(accounts):
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    
    deleted_account = accounts.pop(account_id)
    
    if save_accounts(accounts):
        return {"message": "Аккаунт успешно удален", "account": deleted_account}
    else:
        raise HTTPException(status_code=500, detail="Ошибка сохранения аккаунта")

# API для задач
@app.get("/api/jobs")
async def get_jobs(limit: int = 50, offset: int = 0):
    """Получение списка всех задач"""
    return job_manager.get_all_jobs(limit=limit, offset=offset)

@app.get("/api/jobs/active")
async def get_active_jobs():
    """Получение активных задач"""
    return job_manager.get_active_jobs()

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Получение конкретной задачи по ID"""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return job.to_dict()

@app.post("/api/jobs")
async def create_job(job_request: JobRequest):
    """Создание и запуск новой задачи откликов"""
    try:
        job = job_manager.create_job(
            name=job_request.name,
            account_ids=job_request.account_ids,
            mode=job_request.mode,
            dry_run=job_request.dry_run,
            search_filters=job_request.search_filters
        )
        
        return {
            "message": "Задача успешно создана и запущена",
            "job_id": job.job_id,
            "job": job.to_dict()
        }
    except Exception as e:
        logger.error(f"Ошибка создания задачи: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания задачи: {str(e)}")

@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Отмена выполняемой задачи"""
    success = job_manager.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Задача не найдена или не может быть отменена")
    return {"message": f"Задача {job_id} отменена"}

@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Удаление задачи"""
    success = job_manager.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return {"message": f"Задача {job_id} удалена"}

# API для истории
@app.get("/api/history")
async def get_history(limit: int = 100, offset: int = 0):
    """Получение истории откликов"""
    return core_integration.get_history(limit=limit, offset=offset)

@app.get("/api/history/statistics")
async def get_history_statistics():
    """Получение статистики откликов"""
    return core_integration.get_statistics()

# API для шаблонов
@app.get("/api/templates")
async def get_templates():
    """Получение списка шаблонов сопроводительных писем"""
    return {"templates": load_cover_letter_templates()}

@app.post("/api/templates")
async def create_template(template: CoverLetterTemplate):
    """Создание нового шаблона сопроводительного письма"""
    filename = f"{template.name}.txt"
    filepath = TEMPLATES_DIR / filename
    
    try:
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(template.content)
        return {"message": "Шаблон успешно создан", "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания шаблона: {e}")

@app.delete("/api/templates/{template_name}")
async def delete_template(template_name: str):
    """Удаление шаблона сопроводительного письма"""
    filepath = TEMPLATES_DIR / f"{template_name}.txt"
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    try:
        filepath.unlink()
        return {"message": f"Шаблон {template_name} удален"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления шаблона: {e}")

# WebSocket для real-time обновлений
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Эхо-ответ
            await websocket.send_text(f"Message received: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# WebSocket для обновлений задачи
@app.websocket("/ws/jobs/{job_id}")
async def job_websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    
    job = job_manager.get_job(job_id)
    if not job:
        await websocket.send_text(json.dumps({"error": "Задача не найдена"}))
        await websocket.close()
        return
    
    # Отправляем текущее состояние
    await websocket.send_text(json.dumps(job.to_dict()))
    
    # Callback для обновлений
    def on_job_update(updated_job):
        if updated_job.job_id == job_id:
            websocket.send_text(json.dumps(updated_job.to_dict()))
    
    job_manager.register_callback(on_job_update)
    
    try:
        while True:
            # Ждем сообщения от клиента (можно использовать для управления)
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "cancel":
                    job_manager.cancel_job(job_id)
            except:
                pass
    except WebSocketDisconnect:
        job_manager.unregister_callback(on_job_update)

# Запуск приложения
if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )