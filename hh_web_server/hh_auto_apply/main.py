"""
Главная точка входа для приложения HH Auto Apply
"""
import sys
import os
import logging

# Добавление директории src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def _setup_root_logging():
    """
    Настройка корневого логгера так, чтобы все логи (включая src.*) 
    попадали на консоль и в файл hh_auto_apply.log.
    """
    os.makedirs("logs", exist_ok=True)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Консольный вывод
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.setLevel(logging.INFO)

    # Файловый вывод
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        "logs/hh_auto_apply.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Добавляем только если хендлеры ещё не настроены
    if not root.handlers:
        root.addHandler(console)
        root.addHandler(file_handler)


_setup_root_logging()

from src.ui.cli_interface import main as cli_main


if __name__ == "__main__":
    cli_main()
