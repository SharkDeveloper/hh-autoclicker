"""
Командный интерфейс для HH Auto Apply
"""
import argparse
import logging
import sys
from typing import Dict, Any
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
            epilog='https://github.com/yourusername/hh-auto-apply'
        )

        parser.add_argument(
            '--mode',
            choices=['auto', 'manual', 'recommendations'],
            default='auto',
            help='Режим работы приложения (по умолчанию: auto)'
        )

        parser.add_argument(
            '--config',
            default='config/default.json',
            help='Путь к файлу конфигурации (по умолчанию: config/default.json)'
        )

        parser.add_argument(
            '--keywords',
            help='Ключевые слова поиска (например: "Python разработчик")'
        )

        parser.add_argument(
            '--area',
            help='Код региона (например: 1 — Москва, 2 — Санкт-Петербург)'
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

        parser.add_argument(
            '--vacancy-file',
            help='Файл с URL вакансий (для ручного режима, по одному URL на строку)'
        )

        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='Ограничение скорости (откликов в минуту, по умолчанию: 20)'
        )

        parser.add_argument(
            '--resume-id',
            help='Конкретный ID резюме для использования'
        )

        parser.add_argument(
            '--monitor',
            action='store_true',
            help='Мониторинг статуса откликов после завершения'
        )

        parser.add_argument(
            '--export',
            help='Экспорт результатов в файл (например: report.txt)'
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Выполнить пробный запуск без реальных откликов'
        )

        parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Включить подробный вывод'
        )

        return parser

    def run(self):
        """Запуск CLI интерфейса"""
        args = self.parser.parse_args()

        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        self.logger.info("Запуск HH Auto Apply CLI")
        self.logger.debug(f"Аргументы: {args}")

        if args.dry_run:
            self.logger.info("=== РЕЖИМ ПРОБНОГО ЗАПУСКА (DRY RUN) — реальных откликов не будет ===")

        try:
            if args.mode == 'auto':
                self._run_auto_mode(args)
            elif args.mode == 'manual':
                self._run_manual_mode(args)
            elif args.mode == 'recommendations':
                self._run_recommendations_mode(args)

        except KeyboardInterrupt:
            self.logger.info("Работа прервана пользователем (Ctrl+C)")
            sys.exit(0)
        except Exception as e:
            self.logger.error(f"Критическая ошибка: {e}")
            sys.exit(1)

    def _build_criteria(self, args) -> Dict[str, Any]:
        """
        Построение критериев поиска из аргументов командной строки

        Args:
            args: Разобранные аргументы

        Returns:
            dict: Критерии поиска
        """
        criteria = {}
        if args.keywords:
            criteria['text'] = args.keywords
        if args.area:
            criteria['area'] = args.area
        if args.salary:
            criteria['salary'] = args.salary
        if args.experience:
            criteria['experience'] = args.experience
        return criteria

    def _run_auto_mode(self, args):
        """
        Запуск в автоматическом режиме:
        браузер → вход → поиск → отклики

        Args:
            args: Разобранные аргументы
        """
        self.logger.info("Запуск в автоматическом режиме")

        # Критерии поиска из аргументов (переопределяют конфиг)
        criteria = self._build_criteria(args)
        self.logger.info(f"Критерии поиска: {criteria if criteria else '(из конфига)'}")

        app = HHAutoApply(args.config)

        # Если критерии переданы через CLI — используем их, иначе из конфига
        results = app.run(
            mode='auto',
            search_criteria=criteria if criteria else None,
            dry_run=args.dry_run
        )

        self.logger.info(
            f"Результаты: успешно — {results.get('success', 0)}, "
            f"ошибок — {results.get('failed', 0)}"
        )

        if args.monitor:
            self._monitor_status(app)

        if args.export:
            self._export_results(results, args.export)

    def _run_manual_mode(self, args):
        """
        Запуск в ручном режиме: читаем URL из файла и откликаемся

        Args:
            args: Разобранные аргументы
        """
        self.logger.info("Запуск в ручном режиме")

        if not args.vacancy_file:
            self.logger.error("Для ручного режима необходимо указать --vacancy-file")
            sys.exit(1)

        try:
            with open(args.vacancy_file, 'r', encoding='utf-8') as f:
                vacancy_urls = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.logger.error(f"Файл вакансий не найден: {args.vacancy_file}")
            sys.exit(1)

        self.logger.info(f"Загружено {len(vacancy_urls)} URL из {args.vacancy_file}")

        app = HHAutoApply(args.config)

        # В ручном режиме создаём драйвер, авторизуемся и подаём отклики
        try:
            app.session.create_driver()
            credentials = app.config.get_credentials()

            if not app.auth_module.login(credentials):
                self.logger.error("Не удалось войти. Завершение.")
                return

            app_settings = app.config.get_application_settings()
            results = app.apply_module.apply_batch(
                vacancy_urls,
                rate_limit=args.limit,
                cover_letter=app_settings.get('cover_letter', ''),
                dry_run=args.dry_run
            )

            self.logger.info(
                f"Результаты: успешно — {results['success']}, "
                f"ошибок — {results['failed']}"
            )

            if args.export:
                self._export_results(results, args.export)

        finally:
            app.session.close()

    def _run_recommendations_mode(self, args):
        """
        Запуск в режиме рекомендаций

        Args:
            args: Разобранные аргументы
        """
        self.logger.info("Запуск в режиме рекомендаций")

        app = HHAutoApply(args.config)
        results = app.run(
            mode='recommendations',
            dry_run=args.dry_run
        )

        self.logger.info(
            f"Результаты: успешно — {results.get('success', 0)}, "
            f"ошибок — {results.get('failed', 0)}"
        )

        if args.export:
            self._export_results(results, args.export)

    def _monitor_status(self, app: HHAutoApply):
        """
        Мониторинг статуса откликов

        Args:
            app (HHAutoApply): Экземпляр приложения
        """
        self.logger.info("Мониторинг статуса откликов")
        status = app.monitor_module.check_application_status(app.session)
        self.logger.info(f"Статус откликов: {status}")

    def _export_results(self, results: Dict, filename: str):
        """
        Экспорт результатов в файл

        Args:
            results (dict): Результаты для экспорта
            filename (str): Имя файла
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Отчёт HH Auto Apply\n")
                f.write("=" * 30 + "\n\n")
                f.write(f"Успешных откликов: {results.get('success', 0)}\n")
                f.write(f"Ошибок: {results.get('failed', 0)}\n")
                if results.get('errors'):
                    f.write("\nВакансии с ошибками:\n")
                    for url in results['errors']:
                        f.write(f"  - {url}\n")
            self.logger.info(f"Результаты экспортированы в {filename}")
        except Exception as e:
            self.logger.error(f"Ошибка экспорта: {e}")


def main():
    """Главная точка входа"""
    cli = CLIInterface()
    cli.run()


if __name__ == "__main__":
    main()
