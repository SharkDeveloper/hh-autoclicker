"""
Тесты для модуля поиска (SearchModule)
"""
import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.modules.search_module import SearchModule
from src.core.session_manager import SessionManager


def _make_search():
    mock_session = Mock(spec=SessionManager)
    mock_driver = MagicMock()
    mock_session.driver = mock_driver
    return SearchModule(mock_session), mock_session, mock_driver


def _mock_element(href: str) -> MagicMock:
    el = MagicMock()
    el.get_attribute.return_value = href
    return el


class TestSearchModuleInit(unittest.TestCase):

    def test_init_sets_session(self):
        search, session, _ = _make_search()
        self.assertIs(search.session, session)

    def test_driver_property_delegates_to_session(self):
        search, _, driver = _make_search()
        self.assertIs(search.driver, driver)


class TestSearchVacancies(unittest.TestCase):

    @patch('src.modules.search_module.time.sleep')
    @patch('src.modules.search_module.WebDriverWait')
    def test_returns_empty_list_on_driver_exception(self, mock_wait, mock_sleep):
        search, _, driver = _make_search()
        driver.get.side_effect = Exception("Network error")
        result = search.search_vacancies({'text': 'Python', 'area': '1'})
        self.assertEqual(result, [])

    @patch('src.modules.search_module.time.sleep')
    @patch('src.modules.search_module.WebDriverWait')
    def test_builds_correct_search_url(self, mock_wait, mock_sleep):
        """search_vacancies должен строить URL с text и area."""
        search, _, driver = _make_search()
        mock_wait.return_value.until.return_value = None
        driver.find_elements.return_value = []

        search.search_vacancies({'text': 'Python', 'area': '1'})

        call_args = driver.get.call_args[0][0]
        self.assertIn('text=Python', call_args)
        self.assertIn('area=1', call_args)
        self.assertIn('hh.ru/search/vacancy', call_args)


class TestExtractVacancyUrls(unittest.TestCase):

    @patch('src.modules.search_module.time.sleep')
    def test_filters_out_non_vacancy_urls(self, mock_sleep):
        """URL без числового ID после /vacancy/ должны отбрасываться."""
        search, _, driver = _make_search()
        driver.find_elements.return_value = [
            _mock_element("https://hh.ru/search/vacancy/advanced"),  # должен быть отброшен
            _mock_element("https://hh.ru/vacancy/123456"),            # OK
            _mock_element("https://hh.ru/vacancy/999"),               # OK
        ]
        result = search._extract_vacancy_urls()
        self.assertEqual(len(result), 2)
        self.assertIn("https://hh.ru/vacancy/123456", result)
        self.assertIn("https://hh.ru/vacancy/999", result)

    @patch('src.modules.search_module.time.sleep')
    def test_deduplicates_urls(self, mock_sleep):
        """Один и тот же URL не должен появляться дважды."""
        search, _, driver = _make_search()
        driver.find_elements.return_value = [
            _mock_element("https://hh.ru/vacancy/111"),
            _mock_element("https://hh.ru/vacancy/111"),
            _mock_element("https://hh.ru/vacancy/222"),
        ]
        result = search._extract_vacancy_urls()
        self.assertEqual(len(result), 2)

    @patch('src.modules.search_module.time.sleep')
    def test_strips_query_params_from_url(self, mock_sleep):
        """URL должен быть без query-параметров."""
        search, _, driver = _make_search()
        driver.find_elements.return_value = [
            _mock_element("https://hh.ru/vacancy/123456?from=search&hhtmFrom=main"),
        ]
        result = search._extract_vacancy_urls()
        self.assertEqual(result, ["https://hh.ru/vacancy/123456"])

    @patch('src.modules.search_module.time.sleep')
    def test_returns_empty_on_driver_exception(self, mock_sleep):
        search, _, driver = _make_search()
        driver.find_elements.side_effect = Exception("Driver error")
        result = search._extract_vacancy_urls()
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
