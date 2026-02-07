"""
Тесты для модуля аутентификации
"""
import unittest
from unittest.mock import Mock, patch
from src.modules.auth_module import AuthModule
from src.core.session_manager import SessionManager


class TestAuthModule(unittest.TestCase):
    """Тестовые случаи для AuthModule"""
    
    def setUp(self):
        """Настройка тестовых фикстур"""
        self.mock_session = Mock(spec=SessionManager)
        self.mock_driver = Mock()
        self.mock_session.driver = self.mock_driver
        self.auth_module = AuthModule(self.mock_session)
        
    def test_init(self):
        """Тест инициализации"""
        self.assertIsInstance(self.auth_module, AuthModule)
        self.assertEqual(self.auth_module.session, self.mock_session)
        self.assertEqual(self.auth_module.driver, self.mock_driver)
        
    @patch('src.modules.auth_module.time.sleep')
    def test_login_success(self, mock_sleep):
        """Тест успешного входа"""
        # Настройка моков
        mock_username_field = Mock()
        mock_password_field = Mock()
        mock_login_button = Mock()
        
        self.mock_driver.find_element.side_effect = [
            mock_username_field,
            mock_password_field,
            mock_login_button
        ]
        
        self.mock_driver.get.return_value = None
        
        # Тест входа
        credentials = {'username': 'test@example.com', 'password': 'password123'}
        result = self.auth_module.login(credentials)
        
        # Проверки
        self.mock_driver.get.assert_called_with("https://hh.ru/account/login")
        mock_username_field.clear.assert_called()
        mock_username_field.send_keys.assert_called_with('test@example.com')
        mock_password_field.clear.assert_called()
        mock_password_field.send_keys.assert_called_with('password123')
        mock_login_button.click.assert_called()
        
    @patch('src.modules.auth_module.time.sleep')
    def test_login_failure(self, mock_sleep):
        """Тест неудачного входа"""
        # Настройка моков для вызова исключения
        self.mock_driver.get.side_effect = Exception("Ошибка сети")
        
        # Тест входа
        credentials = {'username': 'test@example.com', 'password': 'password123'}
        result = self.auth_module.login(credentials)
        
        # Проверки
        self.assertFalse(result)
        
    def test_check_auth_status_authenticated(self):
        """Тест проверки статуса аутентификации при аутентификации"""
        # Настройка моков
        self.mock_driver.get.return_value = None
        self.mock_driver.find_element.return_value = Mock()
        
        # Тест статуса аутентификации
        result = self.auth_module.check_auth_status()
        
        # Проверки
        self.assertTrue(result)
        self.mock_driver.get.assert_called_with("https://hh.ru/")
        
    def test_check_auth_status_not_authenticated(self):
        """Тест проверки статуса аутентификации при отсутствии аутентификации"""
        # Настройка моков для вызова исключения
        self.mock_driver.get.return_value = None
        self.mock_driver.find_element.side_effect = Exception("Не найдено")
        
        # Тест статуса аутентификации
        result = self.auth_module.check_auth_status()
        
        # Проверки
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()