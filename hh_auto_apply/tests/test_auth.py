"""
Тесты для модуля аутентификации (AuthModule)
"""
import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.modules.auth_module import AuthModule
from src.core.session_manager import SessionManager


def _make_auth():
    """Создаёт AuthModule с замоканным SessionManager."""
    mock_session = Mock(spec=SessionManager)
    mock_driver = MagicMock()
    mock_session.driver = mock_driver
    return AuthModule(mock_session), mock_session, mock_driver


class TestAuthModuleInit(unittest.TestCase):

    def test_init_sets_session(self):
        auth, session, _ = _make_auth()
        self.assertIs(auth.session, session)

    def test_driver_property_delegates_to_session(self):
        auth, session, driver = _make_auth()
        self.assertIs(auth.driver, driver)


class TestAuthModuleLogin(unittest.TestCase):

    @patch('src.modules.auth_module.time.sleep')
    @patch('src.modules.auth_module.WebDriverWait')
    def test_login_returns_false_on_driver_get_exception(self, mock_wait, mock_sleep):
        """Если driver.get выбрасывает исключение — login возвращает False."""
        auth, _, driver = _make_auth()
        driver.get.side_effect = Exception("Network error")

        result = auth.login({'username': 'u@e.com', 'password': 'p'})
        self.assertFalse(result)

    @patch('src.modules.auth_module.time.sleep')
    @patch('src.modules.auth_module.WebDriverWait')
    def test_login_returns_false_on_missing_credentials(self, mock_wait, mock_sleep):
        """Если не задан username или password — login возвращает False."""
        auth, _, _ = _make_auth()
        self.assertFalse(auth.login({}))
        self.assertFalse(auth.login({'username': '', 'password': 'p'}))
        self.assertFalse(auth.login({'username': 'u@e.com', 'password': ''}))

    @patch('src.modules.auth_module.time.sleep')
    @patch('src.modules.auth_module.WebDriverWait')
    def test_login_calls_driver_get_with_login_url(self, mock_wait, mock_sleep):
        """login() обязан обратиться к странице входа hh.ru."""
        auth, _, driver = _make_auth()

        # Имитируем успешный WebDriverWait (возвращает кликабельный элемент)
        mock_el = MagicMock()
        mock_wait.return_value.until.return_value = mock_el

        # Имитируем успешную проверку авторизации (патчим реальный метод)
        with patch.object(auth, 'check_auth_status', return_value=True):
            auth.login({'username': 'u@e.com', 'password': 'pass'})

        # get должен быть вызван с URL входа
        call_urls = [c[0][0] for c in driver.get.call_args_list]
        self.assertTrue(any("account/login" in url for url in call_urls))


class TestAuthModuleCheckStatus(unittest.TestCase):

    @patch('src.modules.auth_module.time.sleep')
    def test_check_auth_status_returns_true_when_auth_element_found(self, mock_sleep):
        """Авторизован: анонимного заголовка нет, ссылка на резюме — есть."""
        from selenium.common.exceptions import NoSuchElementException
        auth, _, driver = _make_auth()

        # current_url — не страница входа
        type(driver).current_url = unittest.mock.PropertyMock(return_value="https://hh.ru/")

        # Первый find_element (анонимный заголовок) → не найден
        # Последующие вызовы (auth xpaths) → первый успешно возвращает элемент
        driver.find_element.side_effect = [
            NoSuchElementException(),   # анонимный заголовок не найден
            MagicMock(),                # первый auth xpath найден → True
        ]

        self.assertTrue(auth.check_auth_status())

    @patch('src.modules.auth_module.time.sleep')
    def test_check_auth_status_returns_false_when_no_auth_elements(self, mock_sleep):
        """Не авторизован: все auth-элементы отсутствуют."""
        from selenium.common.exceptions import NoSuchElementException
        auth, _, driver = _make_auth()

        type(driver).current_url = unittest.mock.PropertyMock(return_value="https://hh.ru/")

        # Все find_element вызовы не находят элементы
        driver.find_element.side_effect = NoSuchElementException()

        self.assertFalse(auth.check_auth_status())

    @patch('src.modules.auth_module.time.sleep')
    def test_check_auth_status_returns_false_on_login_page(self, mock_sleep):
        """Если URL содержит account/login — пользователь не авторизован."""
        auth, _, driver = _make_auth()

        type(driver).current_url = unittest.mock.PropertyMock(
            return_value="https://hh.ru/account/login"
        )
        # После get — всё ещё на странице входа
        driver.get.return_value = None

        self.assertFalse(auth.check_auth_status())

    def test_check_auth_status_returns_false_on_exception(self):
        """Любое непредвиденное исключение → False."""
        auth, _, driver = _make_auth()
        type(driver).current_url = unittest.mock.PropertyMock(side_effect=Exception("Error"))
        self.assertFalse(auth.check_auth_status())


if __name__ == '__main__':
    unittest.main()
