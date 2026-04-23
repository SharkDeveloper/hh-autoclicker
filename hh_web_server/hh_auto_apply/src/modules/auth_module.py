"""
Модуль аутентификации для HH Auto Apply
"""
import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from src.core.session_manager import SessionManager


class AuthModule:
    """Обработка аутентификации на hh.ru"""

    def __init__(self, session_manager: SessionManager):
        """
        Инициализация модуля аутентификации

        Args:
            session_manager (SessionManager): Экземпляр менеджера сессий
        """
        self.session = session_manager
        self.logger = logging.getLogger(__name__)

    @property
    def driver(self):
        """Динамическое получение актуального драйвера"""
        return self.session.driver

    def login(self, credentials: dict) -> bool:
        """
        Вход на hh.ru по email и паролю.

        Точный поток (подтверждён эмпирически):
          1. Открыть страницу → нажать «Войти» (выбор типа аккаунта)
          2. Нажать «EMAIL» (JS-клик) → появляется поле email
          3. Ввести email → нажать «Войти с паролем»
          4. Появляется поле пароля → ввести пароль → нажать «Дальше»

        Args:
            credentials (dict): {'username': '...', 'password': '...'}

        Returns:
            bool: True если вход успешен, False в противном случае
        """
        username = credentials.get('username', '')
        password = credentials.get('password', '')

        if not username or not password:
            self.logger.error("Логин или пароль не заданы в конфигурации!")
            return False

        try:
            wait = WebDriverWait(self.driver, 15)

            # ── Шаг 1: страница выбора типа аккаунта ─────────────────────────
            self.driver.get("https://hh.ru/account/login?backurl=%2F")
            self.logger.info("Открыта страница входа hh.ru")
            time.sleep(3)

            # Кнопка «Войти» — переход к форме ввода данных
            submit_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-qa='submit-button']"))
            )
            submit_btn.click()
            self.logger.info("Шаг 1: выбран тип аккаунта «Соискатель»")
            time.sleep(2)

            # ── Шаг 2: выбор EMAIL как способа входа ─────────────────────────
            # Радиокнопка перекрыта div-лейблом, используем JS-клик
            try:
                email_radio = wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//input[@data-qa='credential-type-EMAIL']")
                    )
                )
                self.driver.execute_script("arguments[0].click();", email_radio)
                self.logger.info("Шаг 2: выбран способ входа «EMAIL»")
                time.sleep(1)
            except TimeoutException:
                self.logger.warning("Переключатель EMAIL не найден, продолжаем")

            # ── Шаг 3: ввод email ─────────────────────────────────────────────
            try:
                email_field = wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//input[@data-qa='applicant-login-input-email']")
                    )
                )
            except TimeoutException:
                self.logger.error("Поле email не найдено")
                self._save_debug_html("login_step3_debug.html")
                return False

            email_field.clear()
            email_field.send_keys(username)
            self.logger.info(f"Шаг 3: email введён — {username}")
            time.sleep(1)

            # ── Шаг 4: переключение на режим «с паролем» ─────────────────────
            try:
                password_mode_btn = wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//button[@data-qa='expand-login-by-password']")
                    )
                )
                password_mode_btn.click()
                self.logger.info("Шаг 4: нажата «Войти с паролем»")
                time.sleep(2)
            except TimeoutException:
                self.logger.warning("Кнопка «Войти с паролем» не найдена, продолжаем")

            # ── Шаг 5: ввод пароля ────────────────────────────────────────────
            try:
                password_field = wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH,
                         "//input[@data-qa='applicant-login-input-password' "
                         "or @type='password']")
                    )
                )
            except TimeoutException:
                self.logger.error("Поле пароля не появилось")
                self._save_debug_html("login_step5_debug.html")
                return False

            password_field.clear()
            password_field.send_keys(password)
            self.logger.info("Шаг 5: пароль введён")
            time.sleep(1)

            # ── Шаг 6: отправка формы ─────────────────────────────────────────
            try:
                final_btn = wait.until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//button[@data-qa='submit-button' or @type='submit']")
                    )
                )
            except TimeoutException:
                final_btn = self.driver.find_element(By.XPATH, "//button[@type='submit']")

            final_btn.click()
            self.logger.info("Шаг 6: форма входа отправлена")
            time.sleep(5)

            # ── Проверка результата ───────────────────────────────────────────
            if self.check_auth_status():
                self.logger.info("✓ Вход выполнен успешно")
                return True
            else:
                self.logger.error("✗ Вход не выполнен — неверный логин/пароль или CAPTCHA")
                self._save_debug_html("login_failed_debug.html")
                return False

        except Exception as e:
            self.logger.error(f"Ошибка при входе: {e}")
            return False

    def check_auth_status(self) -> bool:
        """
        Проверка статуса аутентификации.

        Returns:
            bool: True если аутентифицирован, False в противном случае
        """
        try:
            # Если уже не на странице входа — проверяем текущую страницу
            if "account/login" in self.driver.current_url:
                self.driver.get("https://hh.ru/")
                time.sleep(3)

            # Страница входа → не авторизован
            if "account/login" in self.driver.current_url:
                self.logger.info("Не авторизован — перенаправлен на страницу входа")
                return False

            # Наличие анонимного заголовка → не авторизован
            try:
                self.driver.find_element(By.XPATH, "//*[@data-qa='main-page-anonymous-header']")
                self.logger.info("Не авторизован — обнаружен анонимный заголовок")
                return False
            except NoSuchElementException:
                pass

            # Элементы авторизованного пользователя
            auth_xpaths = [
                "//a[contains(@href, '/applicant/resumes')]",
                "//a[contains(@href, '/applicant/responses')]",
                "//*[@data-qa='header-user-menu-toggle']",
                "//*[@data-qa='user-menu-button']",
                "//*[contains(@data-qa, 'myProfile')]",
                "//*[@data-qa='mainmenu_myresumes']",
            ]

            for xpath in auth_xpaths:
                try:
                    self.driver.find_element(By.XPATH, xpath)
                    self.logger.info(f"Авторизован — найден элемент: {xpath}")
                    return True
                except NoSuchElementException:
                    continue

            self.logger.info("Элементы авторизованного пользователя не найдены")
            return False

        except Exception as e:
            self.logger.error(f"Ошибка проверки статуса аутентификации: {e}")
            return False

    def logout(self):
        """Выполнение выхода из hh.ru"""
        try:
            self.driver.get("https://hh.ru/account/logout")
            self.logger.info("Выход выполнен успешно")
        except Exception as e:
            self.logger.error(f"Ошибка при выходе: {e}")

    def _save_debug_html(self, filename: str):
        """Сохранение исходника страницы для отладки"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            self.logger.info(f"HTML для отладки сохранён: {filename}")
        except Exception as e:
            self.logger.warning(f"Не удалось сохранить HTML: {e}")
