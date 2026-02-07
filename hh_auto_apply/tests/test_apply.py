"""
Тесты для модуля откликов
"""
import unittest
from unittest.mock import Mock, patch
from src.modules.apply_module import ApplyModule
from src.core.session_manager import SessionManager


class TestApplyModule(unittest.TestCase):
    """Тестовые случаи для ApplyModule"""
    
    def setUp(self):
        """Настройка тестовых фикстур"""
        self.mock_session = Mock(spec=SessionManager)
        self.mock_driver = Mock()
        self.mock_session.driver = self.mock_driver
        self.apply_module = ApplyModule(self.mock_session)
        
    def test_init(self):
        """Тест инициализации"""
        self.assertIsInstance(self.apply_module, ApplyModule)
        self.assertEqual(self.apply_module.session, self.mock_session)
        self.assertEqual(self.apply_module.driver, self.mock_driver)
        
    @patch('src.modules.apply_module.time.sleep')
    def test_apply_to_vacancy_success(self, mock_sleep):
        """Тест успешного отклика на вакансию"""
        # Настройка моков
        mock_apply_button = Mock()
        mock_submit_button = Mock()
        
        self.mock_driver.find_element.side_effect = [
            mock_apply_button,
            mock_submit_button
        ]
        
        # Мок базы данных отвеченных
        self.apply_module.applied_db = Mock()
        self.apply_module.applied_db.is_applied.return_value = False
        self.apply_module.applied_db.add_applied.return_value = None
        
        # Тест отклика
        result = self.apply_module.apply_to_vacancy("https://hh.ru/vacancy/12345678")
        
        # Проверки
        self.assertTrue(result)
        mock_apply_button.click.assert_called()
        mock_submit_button.click.assert_called()
        
    @patch('src.modules.apply_module.time.sleep')
    def test_apply_to_vacancy_already_applied(self, mock_sleep):
        """Тест отклика на уже отвеченную вакансию"""
        # Мок базы данных отвеченных
        self.apply_module.applied_db = Mock()
        self.apply_module.applied_db.is_applied.return_value = True
        
        # Тест отклика
        result = self.apply_module.apply_to_vacancy("https://hh.ru/vacancy/12345678")
        
        # Проверки
        self.assertTrue(result)  # Должен возвращать True для уже отвеченной
        
    @patch('src.modules.apply_module.time.sleep')
    def test_apply_to_vacancy_failure(self, mock_sleep):
        """Тест неудачного отклика на вакансию"""
        # Настройка моков для вызова исключения
        self.mock_driver.get.side_effect = Exception("Ошибка сети")
        
        # Мок базы данных отвеченных
        self.apply_module.applied_db = Mock()
        self.apply_module.applied_db.is_applied.return_value = False
        
        # Тест отклика
        result = self.apply_module.apply_to_vacancy("https://hh.ru/vacancy/12345678")
        
        # Проверки
        self.assertFalse(result)
        
    def test_extract_vacancy_id(self):
        """Тест извлечения ID вакансии"""
        # Тест с полным URL
        url = "https://hh.ru/vacancy/12345678"
        result = self.apply_module._extract_vacancy_id(url)
        self.assertEqual(result, "12345678")
        
        # Тест с URL с параметрами
        url = "https://hh.ru/vacancy/87654321?query=test"
        result = self.apply_module._extract_vacancy_id(url)
        self.assertEqual(result, "87654321")
        
    @patch('src.modules.apply_module.time.sleep')
    def test_apply_batch(self, mock_sleep):
        """Тест пакетного отклика"""
        # Мок метода apply_to_vacancy
        self.apply_module.apply_to_vacancy = Mock()
        self.apply_module.apply_to_vacancy.return_value = True
        
        # Тест пакетного отклика
        vacancy_urls = [
            "https://hh.ru/vacancy/12345678",
            "https://hh.ru/vacancy/87654321"
        ]
        
        result = self.apply_module.apply_batch(vacancy_urls, rate_limit=10)
        
        # Проверки
        self.assertEqual(result['success'], 2)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(result['skipped'], 0)
        self.assertEqual(len(result['errors']), 0)


if __name__ == '__main__':
    unittest.main()