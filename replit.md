# HH Auto Apply

Автоматизированный инструмент для отклика на вакансии на платформе HeadHunter (hh.ru).

## Обзор

Инструмент автоматизирует процесс поиска работы:
- Авторизация на hh.ru (3-шаговый поток: тип аккаунта → EMAIL → пароль)
- Поиск вакансий по ключевым словам и фильтрам
- Отклик на вакансии с сопроводительным письмом
- Имитация поведения человека (случайные задержки, User-Agent)
- Хранение истории откликов в SQLite (без повторов)

## Технологии

- **Язык**: Python 3.12
- **Браузер**: Chromium + ChromeDriver (системный, через Nix)
- **Автоматизация**: Selenium WebDriver
- **Парсинг**: BeautifulSoup4, lxml
- **HTTP**: requests
- **База данных**: SQLite (через data_utils.py)
- **Другое**: python-dotenv, python-dateutil, fake-useragent

## Структура проекта

```
hh_auto_apply/
  main.py                    # Точка входа (настройка логирования + запуск CLI)
  src/
    core/
      application.py         # Главный класс (запуск полного цикла)
      config_manager.py      # Загрузка конфигурации из JSON
      session_manager.py     # Управление браузером (Chromium + chromedriver)
    modules/
      auth_module.py         # Авторизация (3-шаговый поток hh.ru)
      search_module.py       # Поиск вакансий по URL
      apply_module.py        # Отклики на вакансии
      resume_module.py       # Управление резюме
      monitor_module.py      # Мониторинг статуса откликов
    ui/
      cli_interface.py       # CLI интерфейс (argparse)
    utils/
      logger.py              # Настройка логирования
      data_utils.py          # SQLite база откликов
      browser_utils.py       # Вспомогательные функции браузера
  config/
    default.json             # Конфигурация (логин, фильтры, настройки)
  data/                      # Шаблоны писем, списки вакансий
  logs/                      # Файлы логов (создаются автоматически)
hh_auto_apply.py             # Монолитная версия (legacy)
requirements.txt             # Зависимости
config.example.json          # Пример конфигурации
```

## Конфигурация

Файл `hh_auto_apply/config/default.json`:
```json
{
  "credentials": {
    "username": "ваш_email@example.com",
    "password": "ваш_пароль"
  },
  "application": {
    "headless": true,
    "rate_limit": 20,
    "delay_range": [1, 3],
    "dry_run": false,
    "cover_letter": "Текст сопроводительного письма"
  },
  "search_filters": {
    "text": "Python разработчик",
    "area": "1",
    "salary": 100000,
    "experience": "between1And3"
  }
}
```

## Использование

```bash
cd hh_auto_apply

# Пробный запуск (без реальных откликов)
python3 main.py --dry-run --keywords "Python разработчик" --area 1

# Реальный запуск
python3 main.py --mode auto --keywords "Backend разработчик" --area 1

# Ручной режим (список URL из файла)
python3 main.py --mode manual --vacancy-file data/vacancies.txt

# Рекомендации hh.ru
python3 main.py --mode recommendations --dry-run

# Справка
python3 main.py --help
```

## Исправленные ошибки

1. **Chrome не установлен** → установлен Chromium через Nix (`chromium`, `chromedriver`)
2. **`self.driver = None` в модулях** → заменено на `@property` для динамического доступа
3. **`WebDriverWait(None, 10)` в `__init__`** → перенесено в методы
4. **Неправильный поток входа hh.ru** → исправлен 3-шаговый процесс:
   - Шаг 1: «Войти» (тип аккаунта)
   - Шаг 2: JS-клик по EMAIL → поле `applicant-login-input-email`
   - Шаг 3: ввод email → «Войти с паролем» → поле `applicant-login-input-password`
5. **ChromeDriverManager не использовался** → подключены системные бинарники Chromium/chromedriver
6. **Логи модулей не видны** → настроен root-логгер в `main.py`
7. **Дублирование логов** → устранено через проверку наличия хендлеров
8. **Лишние URL в поиске** → фильтрация только реальных вакансий (числовой ID)
9. **Задержки в dry-run** → в режиме симуляции задержки убраны

## Workflow

- **Start application**: запускает `python3 main.py --help` для демонстрации CLI
