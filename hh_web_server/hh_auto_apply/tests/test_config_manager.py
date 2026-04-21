"""
Тесты для менеджера конфигурации (ConfigManager)
"""
import sys
import os
import json
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.config_manager import ConfigManager


def _write_temp_config(data: dict) -> str:
    """Создаёт временный JSON-файл конфигурации."""
    fd, path = tempfile.mkstemp(suffix='.json')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    return path


class TestConfigManagerLoad(unittest.TestCase):

    def test_loads_valid_config(self):
        path = _write_temp_config({"credentials": {"username": "a@b.com", "password": "p"}})
        try:
            cm = ConfigManager(path)
            self.assertEqual(cm.config['credentials']['username'], 'a@b.com')
        finally:
            os.unlink(path)

    def test_returns_empty_dict_for_missing_file(self):
        cm = ConfigManager('/nonexistent/path/config.json')
        self.assertEqual(cm.config, {})

    def test_returns_empty_dict_for_invalid_json(self):
        fd, path = tempfile.mkstemp(suffix='.json')
        with os.fdopen(fd, 'w') as f:
            f.write("NOT JSON {{{")
        try:
            cm = ConfigManager(path)
            self.assertEqual(cm.config, {})
        finally:
            os.unlink(path)


class TestGetCredentials(unittest.TestCase):

    def setUp(self):
        self.path = _write_temp_config({
            "credentials": {"username": "config@email.com", "password": "config_pass"}
        })
        self.cm = ConfigManager(self.path)

    def tearDown(self):
        os.unlink(self.path)
        # Очищаем env-переменные
        os.environ.pop('HH_USERNAME', None)
        os.environ.pop('HH_PASSWORD', None)

    def test_reads_from_config_file(self):
        creds = self.cm.get_credentials()
        self.assertEqual(creds['username'], 'config@email.com')
        self.assertEqual(creds['password'], 'config_pass')

    def test_env_vars_override_config(self):
        os.environ['HH_USERNAME'] = 'env@email.com'
        os.environ['HH_PASSWORD'] = 'env_pass'
        creds = self.cm.get_credentials()
        self.assertEqual(creds['username'], 'env@email.com')
        self.assertEqual(creds['password'], 'env_pass')

    def test_partial_env_override(self):
        """Если задан только HH_USERNAME — пароль берётся из конфига."""
        os.environ['HH_USERNAME'] = 'env@email.com'
        creds = self.cm.get_credentials()
        self.assertEqual(creds['username'], 'env@email.com')
        self.assertEqual(creds['password'], 'config_pass')


class TestGetSearchFilters(unittest.TestCase):

    def test_returns_search_filters(self):
        path = _write_temp_config({"search_filters": {"text": "Python", "area": "1"}})
        try:
            cm = ConfigManager(path)
            filters = cm.get_search_filters()
            self.assertEqual(filters['text'], 'Python')
            self.assertEqual(filters['area'], '1')
        finally:
            os.unlink(path)

    def test_returns_empty_dict_when_no_filters(self):
        path = _write_temp_config({})
        try:
            cm = ConfigManager(path)
            self.assertEqual(cm.get_search_filters(), {})
        finally:
            os.unlink(path)


class TestGetApplicationSettings(unittest.TestCase):

    def test_returns_application_settings(self):
        path = _write_temp_config({"application": {"headless": True, "rate_limit": 10}})
        try:
            cm = ConfigManager(path)
            settings = cm.get_application_settings()
            self.assertTrue(settings['headless'])
            self.assertEqual(settings['rate_limit'], 10)
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()
