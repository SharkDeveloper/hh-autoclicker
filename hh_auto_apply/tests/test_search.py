"""
Тесты для модуля поиска
"""
import unittest
from unittest.mock import Mock, patch
from src.modules.search_module import SearchModule
from src.core.session_manager import SessionManager


class TestSearchModule(unittest.TestCase):
    """Тестовые случаи для SearchModule"""
    
    def setUp(self):
        """Настройка тестовых фикстур"""
        self.mock_session = Mock(spec=SessionManager)
        self.mock_driver = Mock()
        self.mock_session.driver = self.mock_driver
        self.search_module = SearchModule(self.mock_session)
        
    def test_init(self):
        """Тест инициализации"""
        self.assertIsInstance(self.search_module, SearchModule)
        self.assertEqual(self.search_module.session, self.mock_session)
        self.assertEqual(self.search_module.driver, self.mock_driver)
        
    @patch('src.modules.search_module.time.sleep')
    def test_search_vacancies_success(self, mock_sleep):
        """Тест успешного поиска вакансий"""
        # Настройка моков
        mock_vacancy_element = Mock()
        mock_vacancy_element.get_attribute.return_value = "https://hh.ru/vacancy/12345678"
        
        self.mock_driver.find_elements.return_value = [mock_vacancy_element]
        
        # Тест поиска
        query = {'text': 'python разработчик', 'area': '1'}
        result = self.search_module.search_vacancies(query)
        
        # Проверки
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "https://hh.ru/vacancy/12345678")
        
    @patch('src.modules.search_module.time.sleep')
    def test_search_vacancies_failure(self, mock_sleep):
        """Тест неудачного поиска вакансий"""
        # Настройка моков для вызова исключения
        self.mock_driver.get.side_effect = Exception("Ошибка сети")
        
        # Тест поиска
        query = {'text': 'python разработчик'}
        result = self.search_module.search_vacancies(query)
        
        # Проверки
        self.assertEqual(result, [])
        
    @patch('src.modules.search_module.time.sleep')
    def test_get_recommendations_success(self, mock_sleep):
        """Тест успешного получения рекомендаций"""
        # Настройка моков
        mock_vacancy_element = Mock()
        mock_vacancy_element.get_attribute.return_value = "https://hh.ru/vacancy/87654321"
        
        self.mock_driver.find_elements.return_value = [mock_vacancy_element]
        
        # Тест рекомендаций
        result = self.search_module.get_recommendations()
        
        # Проверки
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "https://hh.ru/vacancy/87654321")
        
    def test_extract_vacancy_urls(self):
        """Тест извлечения URL вакансий"""
        # Настройка моков
        mock_element1 = Mock()
        mock_element1.get_attribute.return_value = "https://hh.ru/vacancy/12345678"
        
        mock_element2 = Mock()
        mock_element2.get_attribute.return_value = "https://hh.ru/vacancy/87654321"
        
        self.mock_driver.find_elements.return_value = [mock_element1, mock_element2]
        
        # Тест извлечения
        result = self.search_module._extract_vacancy_urls()
        
        # Проверки
        self.assertEqual(len(result), 2)
        self.assertIn("https://hh.ru/vacancy/12345678", result)
        self.assertIn("https://hh.ru/vacancy/87654321", result)


if __name__ == '__main__':
    unittest.main()