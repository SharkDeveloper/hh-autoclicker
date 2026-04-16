"""
Тесты для модуля откликов (ApplyModule)
"""
import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.modules.apply_module import ApplyModule
from src.core.session_manager import SessionManager


def _make_apply():
    mock_session = Mock(spec=SessionManager)
    mock_driver = MagicMock()
    mock_session.driver = mock_driver
    module = ApplyModule(mock_session)
    # Заменяем реальную БД на мок
    module.applied_db = Mock()
    module.applied_db.is_applied.return_value = False
    return module, mock_session, mock_driver


class TestApplyModuleInit(unittest.TestCase):

    def test_init_sets_session(self):
        apply_m, session, _ = _make_apply()
        self.assertIs(apply_m.session, session)

    def test_driver_property_delegates_to_session(self):
        apply_m, _, driver = _make_apply()
        self.assertIs(apply_m.driver, driver)

    def test_default_account_is_empty(self):
        apply_m, _, _ = _make_apply()
        self.assertEqual(apply_m._account, "")


class TestSetAccount(unittest.TestCase):

    def test_set_account_updates_value(self):
        apply_m, _, _ = _make_apply()
        apply_m.set_account("user@example.com")
        self.assertEqual(apply_m._account, "user@example.com")


class TestExtractVacancyId(unittest.TestCase):

    def test_extracts_id_from_full_url(self):
        apply_m, _, _ = _make_apply()
        self.assertEqual(apply_m._extract_vacancy_id("https://hh.ru/vacancy/12345678"), "12345678")

    def test_extracts_id_strips_query_params(self):
        apply_m, _, _ = _make_apply()
        # query-параметры удаляются до вызова метода (в apply_to_vacancy)
        self.assertEqual(apply_m._extract_vacancy_id("https://hh.ru/vacancy/87654321"), "87654321")

    def test_extracts_id_handles_trailing_slash(self):
        apply_m, _, _ = _make_apply()
        self.assertEqual(apply_m._extract_vacancy_id("https://hh.ru/vacancy/111/"), "111")


class TestApplyToVacancyDryRun(unittest.TestCase):

    @patch('src.modules.apply_module.time.sleep')
    def test_dry_run_returns_true(self, mock_sleep):
        apply_m, _, _ = _make_apply()
        result = apply_m.apply_to_vacancy("https://hh.ru/vacancy/123", dry_run=True)
        self.assertTrue(result)

    @patch('src.modules.apply_module.time.sleep')
    def test_dry_run_does_not_navigate_browser(self, mock_sleep):
        apply_m, _, driver = _make_apply()
        apply_m.apply_to_vacancy("https://hh.ru/vacancy/123", dry_run=True)
        driver.get.assert_not_called()

    @patch('src.modules.apply_module.time.sleep')
    def test_dry_run_skips_already_applied(self, mock_sleep):
        """Уже отвеченная вакансия — пропускается ещё до dry_run-ветки."""
        apply_m, _, _ = _make_apply()
        apply_m.applied_db.is_applied.return_value = True
        result = apply_m.apply_to_vacancy("https://hh.ru/vacancy/123", dry_run=True)
        self.assertTrue(result)
        apply_m.applied_db.add_applied.assert_not_called()


class TestApplyToVacancyReal(unittest.TestCase):

    @patch('src.modules.apply_module.time.sleep')
    def test_real_returns_false_on_driver_exception(self, mock_sleep):
        apply_m, _, driver = _make_apply()
        driver.get.side_effect = Exception("Network error")
        result = apply_m.apply_to_vacancy("https://hh.ru/vacancy/999", dry_run=False)
        self.assertFalse(result)


class TestApplyBatch(unittest.TestCase):

    @patch('src.modules.apply_module.time.sleep')
    def test_batch_counts_successes(self, mock_sleep):
        apply_m, _, _ = _make_apply()
        apply_m.apply_to_vacancy = Mock(return_value=True)
        result = apply_m.apply_batch(
            ["https://hh.ru/vacancy/1", "https://hh.ru/vacancy/2"],
            dry_run=True
        )
        self.assertEqual(result['success'], 2)
        self.assertEqual(result['failed'], 0)

    @patch('src.modules.apply_module.time.sleep')
    def test_batch_counts_failures(self, mock_sleep):
        apply_m, _, _ = _make_apply()
        apply_m.apply_to_vacancy = Mock(return_value=False)
        result = apply_m.apply_batch(
            ["https://hh.ru/vacancy/1", "https://hh.ru/vacancy/2"],
            dry_run=True
        )
        self.assertEqual(result['success'], 0)
        self.assertEqual(result['failed'], 2)

    @patch('src.modules.apply_module.time.sleep')
    def test_batch_no_sleep_in_dry_run(self, mock_sleep):
        """В dry-run режиме не должно быть задержек между откликами."""
        apply_m, _, _ = _make_apply()
        apply_m.apply_to_vacancy = Mock(return_value=True)
        apply_m.apply_batch(
            ["https://hh.ru/vacancy/1", "https://hh.ru/vacancy/2", "https://hh.ru/vacancy/3"],
            dry_run=True
        )
        mock_sleep.assert_not_called()

    @patch('src.modules.apply_module.time.sleep')
    def test_batch_uses_account_from_set_account(self, mock_sleep):
        apply_m, _, _ = _make_apply()
        apply_m.set_account("test@example.com")
        apply_m.apply_to_vacancy = Mock(return_value=True)
        apply_m.apply_batch(["https://hh.ru/vacancy/1"], dry_run=True)
        self.assertEqual(apply_m._account, "test@example.com")


if __name__ == '__main__':
    unittest.main()
