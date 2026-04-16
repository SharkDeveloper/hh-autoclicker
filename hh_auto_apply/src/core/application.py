"""
Главный класс приложения для HH Auto Apply
"""
import logging
from typing import Dict, Any
from src.core.config_manager import ConfigManager
from src.core.session_manager import SessionManager
from src.modules.auth_module import AuthModule
from src.modules.search_module import SearchModule
from src.modules.apply_module import ApplyModule
from src.modules.monitor_module import MonitorModule


class HHAutoApply:
    """Главный класс приложения"""

    def __init__(self, config_path: str):
        """
        Инициализация приложения

        Args:
            config_path (str): Путь к файлу конфигурации
        """
        self.config = ConfigManager(config_path)
        self.session = SessionManager(self.config)

        # Модули инициализируются здесь — но драйвер получают через свойство
        self.auth_module = AuthModule(self.session)
        self.search_module = SearchModule(self.session)
        self.apply_module = ApplyModule(self.session)
        self.monitor_module = MonitorModule()

        self.logger = logging.getLogger(__name__)
        self.logger.info("Приложение HH Auto Apply инициализировано")

    def run(self, mode: str = "auto", search_criteria: Dict[str, Any] = None,
            dry_run: bool = False) -> Dict[str, Any]:
        """
        Запуск приложения в заданном режиме

        Args:
            mode (str): Режим работы ('auto', 'manual', 'recommendations')
            search_criteria (dict): Параметры поиска вакансий
            dry_run (bool): Если True — симуляция без реальных откликов

        Returns:
            dict: Результаты работы
        """
        results = {'success': 0, 'failed': 0, 'errors': []}

        try:
            # 1. Создаём браузер
            self.logger.info("Запуск браузера...")
            self.session.create_driver()

            # 2. Вход в аккаунт
            credentials = self.config.get_credentials()
            if not credentials.get('username') or not credentials.get('password'):
                self.logger.error("Логин и пароль не заданы в конфигурации!")
                return results

            self.logger.info(f"Вход в аккаунт: {credentials.get('username')}")
            if not self.auth_module.login(credentials):
                self.logger.error("Не удалось войти в аккаунт. Завершение работы.")
                return results

            # 3. Получение параметров из конфига, если не переданы явно
            if search_criteria is None:
                search_criteria = self.config.get_search_filters()

            app_settings = self.config.get_application_settings()
            rate_limit = app_settings.get('rate_limit', 20)
            cover_letter = app_settings.get('cover_letter', '')

            # 4. Поиск вакансий
            if mode == 'recommendations':
                self.logger.info("Режим рекомендаций: получаем рекомендованные вакансии")
                vacancy_urls = self.search_module.get_recommendations()
            else:
                self.logger.info(f"Режим '{mode}': поиск вакансий с параметрами {search_criteria}")
                vacancy_urls = self.search_module.search_vacancies(search_criteria)

            if not vacancy_urls:
                self.logger.warning("Вакансии не найдены по заданным критериям")
                return results

            self.logger.info(f"Найдено {len(vacancy_urls)} вакансий, начинаем отклики...")

            # 5. Отклики на вакансии
            results = self.apply_module.apply_batch(
                vacancy_urls,
                rate_limit=rate_limit,
                cover_letter=cover_letter,
                dry_run=dry_run
            )

            self.logger.info(
                f"Итог: успешно — {results['success']}, "
                f"ошибок — {results['failed']}"
            )

        except Exception as e:
            self.logger.error(f"Критическая ошибка при запуске приложения: {e}")
            results['errors'].append(str(e))

        finally:
            # Закрываем браузер в любом случае
            self.session.close()

        return results
