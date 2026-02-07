"""
Главная точка входа для приложения HH Auto Apply
"""
import sys
import os

# Добавление директории src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.ui.cli_interface import main as cli_main


if __name__ == "__main__":
    cli_main()