# HH Auto Apply

Инструмент для автоматической рассылки откликов на вакансии на [hh.ru](https://hh.ru). Работает через управление браузером Chromium — выполняет те же действия, что и живой пользователь: открывает вакансию, нажимает «Откликнуться», вводит сопроводительное письмо.

---

## Возможности

- Авторизация на hh.ru по email и паролю
- Поиск вакансий по ключевым словам, региону, зарплате, опыту
- Автоматическая рассылка откликов с сопроводительным письмом
- Поддержка нескольких аккаунтов и разных резюме
- История откликов в SQLite — повторно на одну вакансию не откликается
- Планировщик для регулярного запуска (раз в N часов)
- Режим симуляции `--dry-run` — всё работает, но реальных откликов нет
- Подробные логи в консоль и файл `logs/`

---

## Структура проекта

```
hh_auto_apply/
│
├── main.py                    # Точка входа CLI
├── scheduler.py               # Планировщик для запуска на сервере
├── requirements.txt           # Python-зависимости
│
├── config/
│   ├── default.json           # Основной конфиг (одиночный аккаунт)
│   └── accounts.json          # Список аккаунтов (мульти-режим)
│
├── src/
│   ├── core/
│   │   ├── application.py     # Главный класс: запуск полного цикла
│   │   ├── config_manager.py  # Загрузка и валидация конфигурации
│   │   └── session_manager.py # Управление браузером Chromium
│   │
│   ├── modules/
│   │   ├── auth_module.py     # Авторизация (5-шаговый поток hh.ru)
│   │   ├── search_module.py   # Поиск вакансий
│   │   ├── apply_module.py    # Отклики на вакансии
│   │   ├── resume_module.py   # Управление резюме
│   │   └── monitor_module.py  # Проверка статуса откликов
│   │
│   ├── ui/
│   │   └── cli_interface.py   # CLI: argparse, режимы запуска
│   │
│   └── utils/
│       ├── logger.py          # Настройка логирования
│       ├── data_utils.py      # SQLite: история откликов
│       └── browser_utils.py   # Вспомогательные функции для браузера
│
├── data/                      # Данные и шаблоны
└── logs/                      # Файлы логов (создаются автоматически)
```

---

## Установка на ПК

### Требования

| Что          | Версия           |
|--------------|------------------|
| Python       | 3.10+            |
| Chromium     | любая свежая     |
| chromedriver | = версии Chromium |
| ОС           | Linux / macOS / Windows |

---

### Linux / macOS

```bash
# 1. Скачиваем репозиторий из Replit
#    (либо используем Git, если подключён)
#    На странице Replit: кнопка ⋮ → Download as zip

# 2. Распаковываем архив и переходим в папку
cd hh-auto-apply/hh_auto_apply

# 3. Создаём виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 4. Устанавливаем Python-зависимости
pip install -r requirements.txt

# 5. Устанавливаем Chromium и chromedriver

# Ubuntu / Debian:
sudo apt update && sudo apt install -y chromium-browser chromium-chromedriver

# macOS (через Homebrew):
brew install --cask chromium
brew install chromedriver
# Разрешить запуск: System Settings → Privacy & Security → Allow chromedriver
```

### Windows

1. Установить [Python 3.10+](https://www.python.org/downloads/) — при установке отметить «Add to PATH»
2. Установить [Google Chrome](https://www.google.com/chrome/)
3. Скачать [chromedriver](https://googlechromelabs.github.io/chrome-for-testing/) **той же версии**, что и Chrome. Положить `chromedriver.exe` в папку `hh_auto_apply/` или добавить в PATH
4. В командной строке (`cmd` или PowerShell):

```cmd
cd hh-auto-apply\hh_auto_apply
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## Настройка

### Одиночный аккаунт — `config/default.json`

```json
{
  "credentials": {
    "username": "your_email@gmail.com",
    "password": "your_password"
  },
  "application": {
    "headless": true,
    "rate_limit": 20,
    "delay_range": [1, 3],
    "dry_run": false,
    "cover_letter": "Ваше сопроводительное письмо"
  },
  "search_filters": {
    "text": "Python разработчик",
    "area": "1",
    "salary": 150000,
    "experience": "between1And3"
  },
  "resume": {
    "default_id": "",
    "auto_update": true
  }
}
```

**Коды регионов (`area`):**

| Регион            | Код |
|-------------------|-----|
| Москва            | 1   |
| Санкт-Петербург   | 2   |
| Екатеринбург      | 3   |
| Новосибирск       | 4   |
| Россия (везде)    | 113 |

**Коды опыта (`experience`):**

| Значение        | Описание       |
|-----------------|----------------|
| `noExperience`  | Без опыта      |
| `between1And3`  | От 1 до 3 лет  |
| `between3And6`  | От 3 до 6 лет  |
| `moreThan6`     | Более 6 лет    |

---

### Несколько аккаунтов — `config/accounts.json`

```json
[
  {
    "name": "Аккаунт Иван",
    "username": "ivan@gmail.com",
    "password": "пароль1",
    "resume_id": "",
    "cover_letter": "Здравствуйте! Меня зовут Иван...",
    "search_filters": {
      "text": "Python разработчик",
      "area": "1"
    },
    "enabled": true
  },
  {
    "name": "Аккаунт Мария",
    "username": "maria@gmail.com",
    "password": "пароль2",
    "cover_letter": "Здравствуйте! Меня зовут Мария...",
    "search_filters": {
      "text": "Data Analyst",
      "area": "2"
    },
    "enabled": true
  }
]
```

> Поставьте `"enabled": false` чтобы временно отключить аккаунт, не удаляя его.

---

## Тестирование на ПК (первый запуск)

```bash
# Находимся в hh_auto_apply/ и активировано venv

# Шаг 1: пробный запуск — без реальных откликов
python3 main.py --dry-run --keywords "Python разработчик" --area 1

# Если всё прошло успешно (найдены вакансии, вход выполнен) —
# Шаг 2: реальный отклик (начнёт откликаться!)
python3 main.py --keywords "Python разработчик" --area 1
```

Убедитесь, что в логах появятся строки:
```
✓ Вход выполнен успешно
Найдено XX вакансий
Пакетный отклик завершён: {'success': XX, ...}
```

---

## Все команды

```bash
# Базовый запуск
python3 main.py --mode auto --keywords "Ключевые слова" --area 1

# С минимальной зарплатой и уровнем опыта
python3 main.py --keywords "Backend" --area 1 --salary 150000 --experience between1And3

# Несколько аккаунтов из файла
python3 main.py --accounts config/accounts.json

# Ручной режим (список URL из файла)
python3 main.py --mode manual --vacancy-file data/vacancies.txt

# Рекомендации hh.ru
python3 main.py --mode recommendations

# Сохранить отчёт в файл
python3 main.py --keywords "Python" --area 1 --export report.txt

# Подробный вывод (DEBUG)
python3 main.py --dry-run -v
```

### Все параметры

```
--mode            auto | manual | recommendations   (по умолчанию: auto)
--keywords        Ключевые слова поиска
--area            Код региона (1 = Москва, 2 = СПб, 113 = Россия)
--salary          Минимальная зарплата (руб.)
--experience      noExperience | between1And3 | between3And6 | moreThan6
--vacancy-file    Файл с URL вакансий, по одному на строку
--limit           Откликов в минуту (по умолчанию: 20)
--resume-id       ID конкретного резюме
--accounts        Файл со списком аккаунтов
--config          Путь к конфигу (по умолчанию: config/default.json)
--export          Сохранить отчёт в файл
--monitor         Проверить статус откликов после завершения
--dry-run         Симуляция без реальных откликов
--verbose, -v     Подробный вывод (DEBUG)
```

---

## Docker (рекомендуемый способ развёртывания)

Проект поставляется с многостадийным образом и двумя профилями: **test** (проверки) и **prod** (продакшн).

### Подготовка

```bash
# Копируем шаблон переменных окружения
cp config/.env.example config/.env
# Открываем и заполняем email / пароль
nano config/.env
```

Содержимое `config/.env`:
```env
HH_USERNAME=your_email@gmail.com
HH_PASSWORD=your_password
SCHEDULER_INTERVAL=360    # каждые 6 часов
SCHEDULER_MODE=auto
```

---

### Стадия TEST — запуск проверок

Выполняется автоматически при каждом деплое или вручную:

```bash
docker compose --profile test up --build
```

**Что происходит внутри:**
1. Проверяет наличие и совместимость Chromium + chromedriver
2. Запускает **50 юнит-тестов** (без браузера, без учётных данных)
3. Если заданы `HH_USERNAME` / `HH_PASSWORD` — запускает **интеграционный dry-run** (реальный вход + поиск вакансий, без откликов)

Если все проверки прошли — в консоли появится:
```
✓ Все проверки пройдены — образ готов к продакшену
```

---

### Стадия PROD — запуск планировщика

```bash
# Фоновый запуск с автоперезапуском
docker compose --profile prod up -d --build

# Следить за логами
docker compose logs -f prod

# Остановить
docker compose --profile prod down
```

**Планировщик** автоматически:
- Загружает аккаунты из `config/accounts.json`
- Запускает цикл откликов по каждому аккаунту
- Ждёт `SCHEDULER_INTERVAL` минут (по умолчанию 360 = 6 часов)
- Повторяет бесконечно, перезапускается при падении

---

### Полный цикл: сначала тест, потом прод

```bash
# 1. Сборка и тестирование
docker compose --profile test up --build

# 2. Если тесты прошли — деплой в продакшн
docker compose --profile prod up -d --build
```

---

### Полезные команды Docker

```bash
# Статус контейнеров
docker compose ps

# Логи планировщика (последние 50 строк)
docker compose logs --tail=50 prod

# Войти в контейнер (отладка)
docker compose exec prod bash

# Просмотреть историю откликов в контейнере
docker compose exec prod sqlite3 data/applied_vacancies.db \
  "SELECT account, vacancy_url, applied_date FROM applied_vacancies ORDER BY applied_date DESC LIMIT 20;"

# Удалить контейнеры и образы (полная очистка)
docker compose down --rmi all
```

---

## Планировщик (запуск на сервере)

`scheduler.py` запускает все аккаунты из `accounts.json` по расписанию:

```bash
# Один раз (для cron)
python3 scheduler.py --once

# Непрерывно каждые 6 часов
python3 scheduler.py --interval 360

# Каждые 2 часа, симуляция
python3 scheduler.py --interval 120 --dry-run

# Рекомендации вместо поиска
python3 scheduler.py --mode recommendations --interval 480
```

---

## Развёртывание на сервере

### Вариант 1: VPS / выделенный сервер (Ubuntu)

```bash
# 1. Подключаемся по SSH
ssh user@your-server-ip

# 2. Устанавливаем системные зависимости
sudo apt update
sudo apt install -y python3 python3-venv python3-pip chromium-browser chromium-chromedriver git

# 3. Загружаем проект
git clone https://github.com/yourusername/hh-auto-apply.git
cd hh-auto-apply/hh_auto_apply

# 4. Настраиваем окружение
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Настраиваем аккаунты
nano config/accounts.json

# 6. Тестируем
python3 main.py --dry-run --accounts config/accounts.json
```

#### Запуск через cron (например, в 9:00, 15:00 и 21:00)

```bash
crontab -e
```

Добавить строку (замените путь на свой):
```
0 9,15,21 * * * cd /home/user/hh-auto-apply/hh_auto_apply && /home/user/hh-auto-apply/hh_auto_apply/venv/bin/python3 scheduler.py --once >> logs/cron.log 2>&1
```

#### Запуск как постоянный фоновый сервис

Создать файл `/etc/systemd/system/hh-auto-apply.service`:

```ini
[Unit]
Description=HH Auto Apply Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/hh-auto-apply/hh_auto_apply
ExecStart=/home/your_username/hh-auto-apply/hh_auto_apply/venv/bin/python3 scheduler.py --interval 360
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Активировать:
```bash
sudo systemctl daemon-reload
sudo systemctl enable hh-auto-apply
sudo systemctl start hh-auto-apply

# Следить за логами сервиса
sudo journalctl -u hh-auto-apply -f
```

---

### Вариант 2: screen / tmux (простой способ без настройки systemd)

```bash
screen -S hh-bot

cd hh-auto-apply/hh_auto_apply
source venv/bin/activate
python3 scheduler.py --interval 360

# Отключиться (бот продолжает работать): Ctrl+A, затем D
# Вернуться к сеансу: screen -r hh-bot
```

---

## Логи

```
logs/
├── hh_auto_apply.log    — все события приложения
└── scheduler.log        — события планировщика
```

```bash
# Следить в реальном времени
tail -f logs/hh_auto_apply.log
```

---

## История откликов (SQLite)

Все отклики хранятся в `data/applied_vacancies.db`. Посмотреть:

```bash
sqlite3 data/applied_vacancies.db \
  "SELECT account, vacancy_url, applied_date FROM applied_vacancies ORDER BY applied_date DESC LIMIT 20;"
```

---

## Возможные проблемы

| Проблема | Решение |
|---|---|
| `chromedriver not found` | Установите chromedriver и убедитесь, что он есть в PATH |
| `version mismatch` | Скачайте chromedriver той же версии, что и Chrome |
| `Не удалось войти` | Проверьте логин/пароль; при первом входе hh.ru может попросить подтвердить по SMS |
| `Вакансии не найдены` | Попробуйте другие ключевые слова или более широкий регион (area=113) |
| На сервере браузер не запускается | Убедитесь что `"headless": true` в конфиге и установлен `chromium-browser` |

---

## Безопасность

- Логины и пароли хранятся **только локально** в `config/` — никуда не передаются
- Приложение имитирует поведение человека: случайные задержки между откликами
- При блокировке аккаунта hh.ru — уменьшите `rate_limit` в конфиге (попробуйте 5–10)

---

## Лицензия

MIT — используйте на свой страх и риск. Убедитесь, что соблюдаете [правила использования hh.ru](https://hh.ru/article/1918).
