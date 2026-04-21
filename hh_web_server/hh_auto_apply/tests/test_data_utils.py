"""
Тесты для утилит базы данных (AppliedVacanciesDB)
"""
import sys
import os
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.data_utils import AppliedVacanciesDB


class TestAppliedVacanciesDB(unittest.TestCase):

    def setUp(self):
        """Создаём временную БД в памяти для каждого теста."""
        fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self.db = AppliedVacanciesDB(db_path=self.db_path)

    def tearDown(self):
        os.unlink(self.db_path)

    # ── is_applied ────────────────────────────────────────

    def test_new_vacancy_is_not_applied(self):
        self.assertFalse(self.db.is_applied("111"))

    def test_is_applied_returns_true_after_add(self):
        self.db.add_applied("222", "https://hh.ru/vacancy/222")
        self.assertTrue(self.db.is_applied("222"))

    def test_is_applied_respects_account(self):
        """Одна вакансия — разные аккаунты — независимая история."""
        self.db.add_applied("333", "https://hh.ru/vacancy/333", account="user1@e.com")
        self.assertTrue(self.db.is_applied("333", account="user1@e.com"))
        self.assertFalse(self.db.is_applied("333", account="user2@e.com"))

    def test_is_applied_without_account_finds_any(self):
        """Без account=... ищем без фильтра по аккаунту."""
        self.db.add_applied("444", "https://hh.ru/vacancy/444", account="user1@e.com")
        self.assertTrue(self.db.is_applied("444"))

    # ── add_applied ───────────────────────────────────────

    def test_add_applied_is_idempotent(self):
        """Повторный add_applied не должен вызывать ошибку."""
        self.db.add_applied("555", "https://hh.ru/vacancy/555")
        self.db.add_applied("555", "https://hh.ru/vacancy/555")  # второй раз — OK
        self.assertTrue(self.db.is_applied("555"))

    def test_add_applied_stores_url(self):
        self.db.add_applied("666", "https://hh.ru/vacancy/666", account="u@e.com")
        rows = self.db.get_applied_vacancies()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['vacancy_url'], "https://hh.ru/vacancy/666")

    # ── get_applied_vacancies ─────────────────────────────

    def test_get_applied_vacancies_empty(self):
        self.assertEqual(self.db.get_applied_vacancies(), [])

    def test_get_applied_vacancies_returns_added_entries(self):
        self.db.add_applied("777", "https://hh.ru/vacancy/777", account="a@b.com")
        self.db.add_applied("888", "https://hh.ru/vacancy/888", account="c@d.com")
        rows = self.db.get_applied_vacancies(limit=10)
        ids = {r['vacancy_id'] for r in rows}
        self.assertIn("777", ids)
        self.assertIn("888", ids)

    def test_get_applied_vacancies_respects_limit(self):
        for i in range(10):
            self.db.add_applied(str(i), f"https://hh.ru/vacancy/{i}")
        rows = self.db.get_applied_vacancies(limit=3)
        self.assertEqual(len(rows), 3)


if __name__ == '__main__':
    unittest.main()
