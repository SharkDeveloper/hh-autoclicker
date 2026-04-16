"""
Планировщик задач для HH Auto Apply
Запускает отклики по всем аккаунтам из accounts.json по расписанию.

Использование:
    python3 scheduler.py                        # Каждые 6 часов
    python3 scheduler.py --interval 120         # Каждые 120 минут
    python3 scheduler.py --dry-run              # Симуляция
    python3 scheduler.py --once                 # Один раз и выйти
"""
import sys
import os
import json
import time
import logging
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Настройка логирования до импорта модулей
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/scheduler.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("scheduler")


def load_accounts(accounts_path: str) -> list:
    """Загрузка списка аккаунтов из JSON-файла"""
    try:
        with open(accounts_path, encoding="utf-8") as f:
            accounts = json.load(f)
        enabled = [a for a in accounts if a.get("enabled", True)]
        logger.info(f"Загружено аккаунтов: {len(enabled)} из {len(accounts)}")
        return enabled
    except FileNotFoundError:
        logger.error(f"Файл аккаунтов не найден: {accounts_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка разбора {accounts_path}: {e}")
        return []


def run_account(account: dict, config_path: str, mode: str, dry_run: bool) -> dict:
    """Запуск цикла откликов для одного аккаунта"""
    from src.core.application import HHAutoApply

    name = account.get("name") or account.get("username", "?")
    logger.info(f"▶ Запуск аккаунта: {name} ({account.get('username', '')})")

    try:
        app = HHAutoApply(config_path)
        results = app.run(
            mode=mode,
            search_criteria=account.get("search_filters") or None,
            dry_run=dry_run,
            account_override=account,
        )
        logger.info(
            f"✓ {name}: успешно — {results['success']}, "
            f"пропущено — {results.get('skipped', 0)}, "
            f"ошибок — {results['failed']}"
        )
        return results
    except Exception as e:
        logger.error(f"✗ {name}: критическая ошибка — {e}")
        return {"success": 0, "failed": 0, "errors": [str(e)]}


def run_all_accounts(accounts: list, config_path: str, mode: str, dry_run: bool):
    """Последовательный обход всех аккаунтов"""
    total = {"success": 0, "failed": 0}
    for i, account in enumerate(accounts, 1):
        logger.info(f"═══ Аккаунт {i}/{len(accounts)} ═══")
        result = run_account(account, config_path, mode, dry_run)
        total["success"] += result.get("success", 0)
        total["failed"] += result.get("failed", 0)
        # Небольшая пауза между аккаунтами
        if i < len(accounts):
            logger.info("Пауза 30 сек перед следующим аккаунтом...")
            time.sleep(30)
    logger.info(f"═══ Итог всех аккаунтов: успешно — {total['success']}, ошибок — {total['failed']} ═══")
    return total


def main():
    parser = argparse.ArgumentParser(description="Планировщик HH Auto Apply")
    parser.add_argument("--accounts", default="config/accounts.json",
                        help="Путь к файлу аккаунтов (по умолчанию: config/accounts.json)")
    parser.add_argument("--config", default="config/default.json",
                        help="Путь к основному конфигу (по умолчанию: config/default.json)")
    parser.add_argument("--mode", choices=["auto", "recommendations"], default="auto",
                        help="Режим работы (по умолчанию: auto)")
    parser.add_argument("--interval", type=int, default=360,
                        help="Интервал запуска в минутах (по умолчанию: 360 = 6 часов)")
    parser.add_argument("--once", action="store_true",
                        help="Запустить один раз и выйти")
    parser.add_argument("--dry-run", action="store_true",
                        help="Режим симуляции без реальных откликов")
    args = parser.parse_args()

    accounts = load_accounts(args.accounts)
    if not accounts:
        logger.error("Нет активных аккаунтов. Выход.")
        sys.exit(1)

    logger.info(
        f"Планировщик запущен | аккаунтов: {len(accounts)} | "
        f"интервал: {args.interval} мин | dry_run: {args.dry_run}"
    )

    if args.once:
        run_all_accounts(accounts, args.config, args.mode, args.dry_run)
        return

    # Цикл по расписанию
    while True:
        logger.info("═══ Новый цикл откликов ═══")
        run_all_accounts(accounts, args.config, args.mode, args.dry_run)
        wait_sec = args.interval * 60
        logger.info(f"Следующий запуск через {args.interval} мин. Ожидание...")
        try:
            time.sleep(wait_sec)
        except KeyboardInterrupt:
            logger.info("Планировщик остановлен пользователем (Ctrl+C)")
            break


if __name__ == "__main__":
    main()
