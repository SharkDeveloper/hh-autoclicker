"""
Командный интерфейс для HH Auto Apply
"""
import argparse
import logging
import sys
from typing import List, Dict, Any
from src.core.application import HHAutoApply
from src.core.config_manager import ConfigManager
from src.utils.logger import get_application_logger


class CLIInterface:
    """Командный интерфейс для приложения"""
    
    def __init__(self):
        """Инициализация CLI интерфейса"""
        self.parser = self._create_parser()
        self.logger = get_application_logger()
        
    def _create_parser(self) -> argparse.ArgumentParser:
        """
        Создание парсера аргументов
        
        Returns:
            argparse.ArgumentParser: Настроенный парсер аргументов
        """
        parser = argparse.ArgumentParser(
            prog='hh_auto_apply',
            description='Автоотклик на вакансии на hh.ru',
            epilog='Для получения дополнительной информации посетите https://github.com/yourusername/hh-auto-apply'
        )
        
        # Выбор режима
        parser.add_argument(
            '--mode',
            choices=['auto', 'manual', 'recommendations'],
            default='auto',
            help='Режим работы приложения (по умолчанию: auto)'
        )
        
        # Конфигурация
        parser.add_argument(
            '--config',
            default='config/default.json',
            help='Путь к файлу конфигурации (по умолчанию: config/default.json)'
        )
        
        # Параметры поиска
        parser.add_argument(
            '--keywords',
            help='Ключевые слова поиска'
        )
        
        parser.add_argument(
            '--area',
            help='Код региона/области'
        )
        
        parser.add_argument(
            '--salary',
            type=int,
            help='Минимальная зарплата'
        )
        
        parser.add_argument(
            '--experience',
            choices=['noExperience', 'between1And3', 'between3And6', 'moreThan6'],
            help='Уровень опыта'
        )
        
        # Параметры отклика
        parser.add_argument(
            '--vacancy-file',
            help='Файл с ID вакансий (для ручного режима)'
        )
        
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='Ограничение скорости (откликов в минуту, по умолчанию: 20)'
        )
        
        # Параметры резюме
        parser.add_argument(
            '--resume-id',
            help='Конкретный ID резюме для использования'
        )
        
        # Мониторинг
        parser.add_argument(
            '--monitor',
            action='store_true',
            help='Мониторинг статуса откликов'
        )
        
        # Экспорт
        parser.add_argument(
            '--export',
            help='Экспорт результатов в файл'
        )
        
        # Отладка
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Выполнить пробный запуск без реальных откликов'
        )
        
        parser.add_argument(
            '--verbose',
            '-v',
            action='store_true',
            help='Включить подробный вывод'
        )
        
        return parser
        
    def run(self):
        """Запуск CLI интерфейса"""
        try:
            # Парсинг аргументов
            args = self.parser.parse_args()
            
            # Настройка логирования
            if args.verbose:
                logging.getLogger().setLevel(logging.DEBUG)
                
            self.logger.info("Запуск HH Auto Apply CLI")
            self.logger.debug(f"Аргументы: {args}")
            
            # Загрузка конфигурации
            config_manager = ConfigManager(args.config)
            
            # Создание экземпляра приложения
            app = HHAutoApply(args.config)
            
            # Запуск в заданном режиме
            if args.mode == 'auto':
                self._run_auto_mode(app, args)
            elif args.mode == 'manual':
                self._run_manual_mode(app, args)
            elif args.mode == 'recommendations':
                self._run_recommendations_mode(app, args)
                
            # Мониторинг, если запрошен
            if args.monitor:
                self._monitor_status(app)
                
        except Exception as e:
            self.logger.error(f"Ошибка запуска CLI: {e}")
            sys.exit(1)
            
    def _run_auto_mode(self, app: HHAutoApply, args):
        """
        Запуск в автоматическом режиме
        
        Args:
            app (HHAutoApply): Экземпляр приложения
            args (argparse.Namespace): Распарсенные аргументы
        """
        self.logger.info("Запуск в автоматическом режиме")
        
        # Построение критериев поиска
        criteria = {}
        if args.keywords:
            criteria['text'] = args.keywords
        if args.area:
            criteria['area'] = args.area
        if args.salary:
            criteria['salary'] = args.salary
        if args.experience:
            criteria['experience'] = args.experience
            
        # TODO: Реализовать логику поиска и отклика
        self.logger.info(f"Критерии поиска: {criteria}")
        
    def _run_manual_mode(self, app: HHAutoApply, args):
        """
        Запуск в ручном режиме
        
        Args:
            app (HHAutoApply): Экземпляр приложения
            args (argparse.Namespace): Распарсенные аргументы
        """
        self.logger.info("Запуск в ручном режиме")
        
        if not args.vacancy_file:
            self.logger.error("Файл вакансий обязателен для ручного режима")
            return
            
        # TODO: Реализовать логику ручного режима
        self.logger.info(f"Использование файла вакансий: {args.vacancy_file}")
        
    def _run_recommendations_mode(self, app: HHAutoApply, args):
        """
        Запуск в режиме рекомендаций
        
        Args:
            app (HHAutoApply): Экземпляр приложения
            args (argparse.Namespace): Распарсенные аргументы
        """
        self.logger.info("Запуск в режиме рекомендаций")
        app.search_module.get_recommendations()
        # TODO: Реализовать логику режима рекомендаций
        
    def _monitor_status(self, app: HHAutoApply):
        """
        Мониторинг статуса откликов
        
        Args:
            app (HHAutoApply): Экземпляр приложения
        """
        self.logger.info("Мониторинг статуса откликов")
        
        # TODO: Реализовать логику мониторинга


def main():
    """Главная точка входа"""
    cli = CLIInterface()
    cli.run()


if __name__ == "__main__":
    main()