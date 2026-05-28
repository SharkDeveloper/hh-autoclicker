# AGENTS.md — HH AutoApply MVP

Этот файл — инструкция для AI-агента. Читай его **полностью** перед любым изменением кода.

---

## Что это за проект

Инструмент автоматической подачи откликов на вакансии hh.ru.
Состоит из **двух независимых сервисов**, общающихся через Kafka:

- **web** — FastAPI + Vue (статика) + PostgreSQL. Авторизация пользователей, дашборд, управление настройками, запуск задач.
- **worker** — Python + Selenium + Chromium. Kafka-консьюмер, выполняет реальные отклики на hh.ru.

Общая БД — PostgreSQL. Оба сервиса обращаются к ней напрямую (разные схемы).

---

## Запуск (локально)

```bash
cp .env.example .env          # заполнить переменные
docker compose up --build     # поднять все сервисы
# Web доступен на http://localhost:8000
# Kafka UI доступен на http://localhost:8080
```

---

## Стек

| Слой | Технология | Версия |
|---|---|---|
| Web-фреймворк | FastAPI | ≥0.111 |
| Фронтенд | Vue 3 (Vite, статика) | ≥3.4 |
| Брокер | Apache Kafka | ≥3.7 |
| БД | PostgreSQL | ≥16 |
| Миграции | Alembic | latest |
| ORM | SQLAlchemy 2.x (async) | ≥2.0 |
| Автоматизация | Selenium WebDriver | ≥4.x |
| Браузер | Chromium + chromedriver (системный, Nix) | — |
| Контейнеризация | Docker Compose | v2 |
| Авторизация | JWT (python-jose) + httpOnly cookie | — |

---

## Структура проекта

```
hh_auto_apply/               # LEGACY — не трогать, не удалять
AGENTS.md                    # этот файл
docker-compose.yml           # оркестрация всех сервисов
.env.example                 # шаблон переменных окружения

web/                         # Сервис 1: Web + API
  Dockerfile
  main.py                    # точка входа FastAPI (uvicorn)
  api/
    routers/
      auth.py                # /api/auth/* — регистрация, вход, выход
      jobs.py                # /api/jobs/* — управление задачами
      stats.py               # /api/stats/* — статистика откликов
      settings.py            # /api/settings/* — конфиг пользователя
    deps.py                  # get_current_user, get_db (зависимости FastAPI)
    schemas.py               # Pydantic-модели запросов/ответов
  db/
    models.py                # SQLAlchemy ORM-модели (User, Job, Apply, Settings)
    session.py               # async engine + get_db
    migrations/              # Alembic-миграции
  kafka/
    producer.py              # отправка задач в topic apply-jobs
    consumer.py              # приём результатов из topic apply-results
  static/                    # Vue build (dist/) — раздаётся FastAPI как StaticFiles
  requirements.txt

worker/                      # Сервис 2: Autoclicker
  Dockerfile
  main.py                    # точка входа — запускает Kafka consumer loop
  consumer.py                # читает apply-jobs, вызывает core
  producer.py                # пишет результаты в apply-results
  core/
    session_manager.py       # управление браузером (один Chromium на воркер)
    auth_module.py           # авторизация hh.ru (3-шаговый поток)
    search_module.py         # поиск вакансий по фильтрам (URL-парсинг)
    recommendations_module.py # вакансии по рекомендациям hh.ru (resume_id URL)
    apply_module.py          # подача отклика + сопроводительное письмо
    resume_module.py         # выбор резюме пользователя
  utils/
    browser_utils.py         # хелперы Selenium (wait, scroll, delay)
    logger.py                # настройка логирования (не использовать print)
  requirements.txt
```

---

## Docker Compose — сервисы

```yaml
# Обязательные сервисы в docker-compose.yml:
services:
  postgres:       # PostgreSQL 16, volume: pgdata
  kafka:          # Apache Kafka 3.7 (KRaft mode, без Zookeeper)
  kafka-ui:       # Kafbat UI на порту 8080 (для разработки)
  web:            # сборка из web/, порт 8000
  worker:         # сборка из worker/, нет внешних портов
```

Переменные окружения передаются через `.env`. Kafka в KRaft-режиме — без Zookeeper.

---

## База данных — схема

### Таблица `users`
```
id          UUID PK
email       TEXT UNIQUE NOT NULL
hashed_pw   TEXT NOT NULL
hh_login    TEXT           -- логин от hh.ru
hh_password TEXT           -- пароль от hh.ru (шифровать Fernet)
resume_id   TEXT           -- ID резюме на hh.ru
created_at  TIMESTAMP
```

### Таблица `settings`
```
id            UUID PK
user_id       UUID FK → users.id
cover_letter  TEXT
delay_min     INT DEFAULT 1
delay_max     INT DEFAULT 3
rate_limit    INT DEFAULT 20   -- максимум откликов за сессию
headless      BOOL DEFAULT true
```

### Таблица `jobs` (задачи на отклик)
```
id          UUID PK
user_id     UUID FK → users.id
mode        TEXT  -- 'auto' | 'manual' | 'recommendations'
status      TEXT  -- 'pending' | 'running' | 'done' | 'failed'
filters     JSONB -- {text, area, salary, experience}
created_at  TIMESTAMP
started_at  TIMESTAMP NULL
finished_at TIMESTAMP NULL
```

### Таблица `applies`
```
id           UUID PK
job_id       UUID FK → jobs.id
user_id      UUID FK → users.id
vacancy_id   TEXT    -- числовой ID вакансии hh.ru
vacancy_url  TEXT
vacancy_title TEXT
company      TEXT
status       TEXT    -- 'sent' | 'skipped' | 'error'
error_msg    TEXT NULL
applied_at   TIMESTAMP
```

**Правила:**
- Не менять структуру таблиц без создания Alembic-миграции.
- `hh_password` шифровать через `cryptography.fernet` — не хранить открытым текстом.
- Индекс по `(user_id, vacancy_id)` в `applies` — для дедупликации откликов.

---

## Kafka — топики и формат сообщений

### `apply-jobs` (Web → Worker)

```json
{
  "job_id": "uuid",
  "user_id": "uuid",
  "mode": "auto | manual | recommendations",
  "hh_login": "user@example.com",
  "hh_password_enc": "...",
  "resume_id": "d5113943ff09ef02170039ed1f597879424a41",
  "cover_letter": "Текст письма",
  "filters": {
    "text": "Python разработчик",
    "area": "1",
    "salary": 100000,
    "experience": "between1And3"
  },
  "rate_limit": 20,
  "delay_range": [1, 3],
  "vacancy_urls": []
}
```

- `mode: "recommendations"` — Worker игнорирует `filters`, использует `resume_id`.
- `mode: "manual"` — Worker использует `vacancy_urls`, игнорирует `filters`.
- `mode: "auto"` — Worker использует `filters` для поиска.

### `apply-results` (Worker → Web)

```json
{
  "job_id": "uuid",
  "user_id": "uuid",
  "status": "done | failed",
  "applies": [
    {
      "vacancy_id": "123456",
      "vacancy_url": "https://hh.ru/vacancy/123456",
      "vacancy_title": "Python Developer",
      "company": "Yandex",
      "status": "sent | skipped | error",
      "error_msg": null
    }
  ],
  "total_sent": 15,
  "total_skipped": 3,
  "total_errors": 0,
  "finished_at": "2024-01-01T12:00:00Z"
}
```

---

## Web Service — API эндпоинты

### Auth
```
POST /api/auth/register     — регистрация (email, password)
POST /api/auth/login        — вход → JWT в httpOnly cookie
POST /api/auth/logout       — выход (очистка cookie)
GET  /api/auth/me           — текущий пользователь
```

### Настройки hh.ru
```
GET  /api/settings          — получить настройки пользователя
PUT  /api/settings          — сохранить (hh_login, hh_password, resume_id, cover_letter, filters)
```

### Задачи
```
POST /api/jobs              — создать задачу → publish в Kafka → вернуть job_id
GET  /api/jobs              — список задач пользователя (с пагинацией)
GET  /api/jobs/{job_id}     — статус и детали задачи
DELETE /api/jobs/{job_id}   — отменить задачу (если pending)
```

### Статистика
```
GET /api/stats              — сводка: всего откликов, сегодня, по статусам
GET /api/stats/history      — история откликов (с фильтрами по дате/статусу)
```

### Фронтенд
```
GET /*                      — отдавать web/static/index.html (Vue SPA)
```

---

## Worker Service — логика

### Инициализация
1. Поднять один экземпляр Chromium через `session_manager.py`.
2. Авторизоваться на hh.ru через `auth_module.py`.
3. Начать слушать топик `apply-jobs`.

### Получение задачи из Kafka
1. Десериализовать JSON-сообщение.
2. Обновить статус `jobs.status = 'running'` в PostgreSQL.
3. Передать задачу в нужный модуль по `mode`.

### Режим `auto` (поиск по фильтрам)
```
search_module.py:
  URL: https://hh.ru/search/vacancy?text={text}&area={area}&salary={salary}&experience={experience}&order_by=relevance
  Парсить вакансии постранично.
  Фильтровать: только числовой ID в URL (/vacancy/NNNNNN), не агрегаторы.
  Пропускать уже отклонённые (проверка по applies в PostgreSQL).
```

### Режим `recommendations` (по рекомендациям hh.ru)
```
recommendations_module.py:
  URL: https://hh.ru/search/vacancy?resume={resume_id}
  Логика парсинга аналогична search_module.py.
  resume_id берётся из Kafka-сообщения.
  Не использовать фильтры из settings.
```

### Режим `manual` (список URL)
```
apply_module.py:
  Итерировать по vacancy_urls из сообщения.
  Для каждой — открыть страницу и откликнуться.
```

### Отклик на вакансию (`apply_module.py`)
1. Открыть страницу вакансии.
2. Нажать кнопку «Откликнуться».
3. Выбрать нужное резюме (по `resume_id`).
4. Вставить сопроводительное письмо.
5. Подтвердить отклик.
6. Записать результат в список для `apply-results`.
7. Человекоподобная задержка: `random.uniform(delay_min, delay_max)`.

### Завершение задачи
1. Опубликовать итог в топик `apply-results`.
2. Web-сервис слушает `apply-results` и записывает `applies` в PostgreSQL.
3. Обновить `jobs.status = 'done'` и `jobs.finished_at`.

---

## Авторизация hh.ru (3-шаговый поток)

**Не менять эту логику без проверки через DevTools на hh.ru.**

```
Шаг 1: Нажать «Войти» на главной → выбрать тип аккаунта «Соискатель»
Шаг 2: JS-клик по кнопке EMAIL → дождаться поля applicant-login-input-email → ввести email
Шаг 3: Нажать «Войти с паролем» → дождаться поля applicant-login-input-password → ввести пароль → Submit
```

Селекторы:
- Email input: `[data-qa="applicant-login-input-email"]`
- Password input: `[data-qa="applicant-login-input-password"]`
- Кнопка EMAIL: `[data-qa="login-with-email"]`
- Кнопка «Войти с паролем»: `[data-qa="login-form-submit"]`

---

## Правила для агента

### Что нельзя делать
- **Не трогать** директорию `hh_auto_apply/` — это legacy, оставлена для совместимости.
- **Не создавать** новые экземпляры WebDriver вне `session_manager.py`.
- **Не использовать** `print()` — только `utils/logger.py`.
- **Не хардкодить** `time.sleep()` — использовать `browser_utils.human_delay(min, max)`.
- **Не хранить** пароль hh.ru в открытом виде — только через Fernet.
- **Не менять** схему таблиц без Alembic-миграции.
- **Не подключаться** из worker к Kafka-топику `apply-jobs` напрямую — только через `consumer.py`.

### Что делать при изменениях
- Kafka-схема (поля сообщений) изменилась → обновить **оба** сервиса одновременно.
- Новый API-эндпоинт → добавить роутер в `web/api/routers/`, зарегистрировать в `main.py`.
- Новый режим отклика → новый модуль в `worker/core/`, добавить ветку в `consumer.py`.
- Изменения в авторизации hh.ru → только `auth_module.py`, проверить селекторы в DevTools.

### Human-delay обязателен
Все действия браузера с вакансиями должны идти через:
```python
from utils.browser_utils import human_delay
human_delay(delay_min, delay_max)  # из настроек задачи
```

### Дедупликация откликов
Перед отправкой отклика всегда проверять:
```sql
SELECT 1 FROM applies WHERE user_id = $1 AND vacancy_id = $2
```
Если запись есть — пропустить вакансию (`status = 'skipped'`).

---

## Vue фронтенд (web/static/)

Vue собирается через Vite и деплоится как статика. FastAPI отдаёт `index.html` на все `/*` маршруты (SPA fallback).

### Страницы (роуты Vue Router)
```
/login          — форма входа / регистрации
/dashboard      — список задач, кнопка «Запустить»
/settings       — настройки hh.ru (логин, пароль, resume_id, письмо, фильтры)
/stats          — статистика откликов (таблица + графики)
/jobs/:id       — детали задачи (прогресс, список вакансий)
```

### Требования к UI
- Все запросы к API идут с cookie (credentials: 'include').
- Статус задачи обновляется через polling `/api/jobs/{id}` каждые 5 секунд (пока `status === 'running'`).
- На странице `/settings` поле пароля hh.ru — всегда type="password", не показывать в явном виде.
- Добавить выбор режима запуска: `auto` / `recommendations` / `manual`.
- В режиме `recommendations` показывать поле `resume_id` (если не заполнено в настройках).
- В режиме `manual` — textarea для списка URL (по одному на строку).

---

## Переменные окружения (.env)

```env
# PostgreSQL
POSTGRES_USER=hh_user
POSTGRES_PASSWORD=secret
POSTGRES_DB=hh_autoapply
DATABASE_URL=postgresql+asyncpg://hh_user:secret@postgres:5432/hh_autoapply

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_TOPIC_JOBS=apply-jobs
KAFKA_TOPIC_RESULTS=apply-results

# Security
JWT_SECRET=changeme_generate_with_openssl_rand
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080
FERNET_KEY=changeme_generate_with_fernet_keygen

# Worker
CHROMIUM_BINARY=/usr/bin/chromium
CHROMEDRIVER_PATH=/usr/bin/chromedriver
WORKER_HEADLESS=true
```

---

## Что НЕ входит в MVP

- Email-уведомления об откликах
- Мониторинг статусов откликов на hh.ru (просмотры, приглашения)
- Несколько worker'ов параллельно (архитектура готова, но одного достаточно)
- OAuth через hh.ru API (используем Selenium-вход)
- Платёжная система / тарифы

---

## Запуск в prod

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

В prod-конфиге:
- `kafka-ui` отключён
- `WORKER_HEADLESS=true` принудительно
- Nginx перед web-сервисом (reverse proxy + SSL)
- Volumes для PostgreSQL и логов
