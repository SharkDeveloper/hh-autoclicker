"""
Автоматический отклик на вакансии HeadHunter
"""
import json
import time
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import quote, urlencode
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hh_auto_apply.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class HHAutoApply:
    """Класс для автоматизации откликов на hh.ru"""
    
    def __init__(self, config_path: str = "config.json"):
        """Инициализация с загрузкой конфигурации"""
        self.config = self._load_config(config_path)
        self.driver = None
        self.applied_count = 0
        self.skipped_count = 0
        self.error_count = 0
        self.applied_vacancies = set()
        self._load_applied_vacancies()
        
    def _load_config(self, config_path: str) -> Dict:
        """Загрузка конфигурации из JSON файла"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Файл конфигурации {config_path} не найден!")
            raise
        except json.JSONDecodeError:
            logger.error(f"Ошибка парсинга JSON в файле {config_path}")
            raise
    
    def _load_applied_vacancies(self):
        """Загрузка списка уже откликнутых вакансий"""
        applied_file = Path("applied_vacancies.txt")
        if applied_file.exists():
            with open(applied_file, 'r', encoding='utf-8') as f:
                self.applied_vacancies = set(line.strip() for line in f if line.strip())
            logger.info(f"Загружено {len(self.applied_vacancies)} уже откликнутых вакансий")
    
    def _save_applied_vacancy(self, vacancy_id: str):
        """Сохранение ID откликнутой вакансии"""
        self.applied_vacancies.add(vacancy_id)
        with open("applied_vacancies.txt", 'a', encoding='utf-8') as f:
            f.write(f"{vacancy_id}\n")
    
    def _setup_driver(self):
        """Настройка и запуск браузера"""
        import os
        chrome_options = Options()
        
        if self.config['browser_settings']['headless']:
            chrome_options.add_argument('--headless')
        
        # Настройки для избежания детекции бота
        ua = UserAgent()
        chrome_options.add_argument(f'user-agent={ua.random}')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        
        # Подавление ошибок GPU и WebGL
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--log-level=3')  # Подавляем большинство логов Chrome
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])  # Отключаем логирование
        
        # Получаем путь к chromedriver
        # Пробуем использовать webdriver-manager, если не получается - используем встроенный менеджер Selenium
        try:
            driver_path = ChromeDriverManager().install()
            logger.info(f"Путь к chromedriver: {driver_path}")
            
            # Исправляем путь, если он указывает не на .exe файл
            if not driver_path.endswith('.exe'):
                driver_dir = os.path.dirname(driver_path)
                # Ищем chromedriver.exe в директории и подпапках
                found = False
                for root, dirs, files in os.walk(driver_dir):
                    for file in files:
                        if file == 'chromedriver.exe':
                            driver_path = os.path.join(root, file)
                            logger.info(f"Найден chromedriver.exe: {driver_path}")
                            found = True
                            break
                    if found:
                        break
                
                # Если не нашли, используем встроенный менеджер Selenium
                if not found or not os.path.exists(driver_path):
                    logger.info("Используем встроенный менеджер Selenium для автоматической установки драйвера")
                    service = Service()  # Selenium 4.6+ автоматически найдет драйвер
                else:
                    service = Service(driver_path)
            else:
                # Проверяем, что файл существует
                if os.path.exists(driver_path):
                    service = Service(driver_path)
                else:
                    logger.warning(f"Файл {driver_path} не найден, используем встроенный менеджер")
                    service = Service()
        except Exception as e:
            logger.warning(f"Ошибка при установке через ChromeDriverManager: {e}")
            logger.info("Используем встроенный менеджер Selenium")
            service = Service()  # Используем встроенный менеджер Selenium
        
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Удаление webdriver свойства
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.driver.implicitly_wait(self.config['browser_settings']['implicit_wait'])
        self.driver.set_page_load_timeout(self.config['browser_settings']['page_load_timeout'])
        
        logger.info("Браузер успешно запущен")
    
    def _log_page_elements(self, step_name: str):
        """Детальное логирование элементов на странице для отладки"""
        try:
            logger.info(f"=== ЛОГИРОВАНИЕ ЭЛЕМЕНТОВ: {step_name} ===")
            logger.info(f"Текущий URL: {self.driver.current_url}")
            
            # Логируем все кнопки
            try:
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                logger.info(f"Найдено кнопок на странице: {len(buttons)}")
                for i, btn in enumerate(buttons[:20]):  # Логируем первые 20
                    try:
                        text = btn.text.strip()
                        is_displayed = btn.is_displayed()
                        is_enabled = btn.is_enabled()
                        data_qa = btn.get_attribute('data-qa') or ''
                        aria_label = btn.get_attribute('aria-label') or ''
                        class_name = btn.get_attribute('class') or ''
                        btn_type = btn.get_attribute('type') or ''
                        
                        logger.info(f"  Кнопка #{i+1}: текст='{text[:50]}', видима={is_displayed}, активна={is_enabled}, "
                                  f"data-qa='{data_qa}', type='{btn_type}', class='{class_name[:50]}'")
                    except Exception as e:
                        logger.debug(f"  Кнопка #{i+1}: ошибка при получении данных - {e}")
            except Exception as e:
                logger.warning(f"Ошибка при логировании кнопок: {e}")
            
            # Логируем все поля ввода
            try:
                inputs = self.driver.find_elements(By.TAG_NAME, "input")
                logger.info(f"Найдено полей ввода на странице: {len(inputs)}")
                for i, inp in enumerate(inputs[:20]):  # Логируем первые 20
                    try:
                        input_type = inp.get_attribute('type') or 'text'
                        placeholder = inp.get_attribute('placeholder') or ''
                        name = inp.get_attribute('name') or ''
                        data_qa = inp.get_attribute('data-qa') or ''
                        is_displayed = inp.is_displayed()
                        is_enabled = inp.is_enabled()
                        value = inp.get_attribute('value') or ''
                        
                        logger.info(f"  Поле #{i+1}: type='{input_type}', placeholder='{placeholder}', "
                                  f"name='{name}', data-qa='{data_qa}', видимо={is_displayed}, "
                                  f"активно={is_enabled}, value='{value[:30]}'")
                    except Exception as e:
                        logger.debug(f"  Поле #{i+1}: ошибка при получении данных - {e}")
            except Exception as e:
                logger.warning(f"Ошибка при логировании полей ввода: {e}")
            
            # Логируем элементы с data-qa атрибутами
            try:
                data_qa_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-qa]")
                logger.info(f"Найдено элементов с data-qa: {len(data_qa_elements)}")
                for i, elem in enumerate(data_qa_elements[:30]):  # Логируем первые 30
                    try:
                        data_qa = elem.get_attribute('data-qa')
                        tag = elem.tag_name
                        text = elem.text.strip()[:50]
                        is_displayed = elem.is_displayed()
                        
                        logger.info(f"  data-qa элемент #{i+1}: data-qa='{data_qa}', tag='{tag}', "
                                  f"текст='{text}', видим={is_displayed}")
                    except Exception as e:
                        logger.debug(f"  data-qa элемент #{i+1}: ошибка - {e}")
            except Exception as e:
                logger.warning(f"Ошибка при логировании data-qa элементов: {e}")
            
            logger.info(f"=== КОНЕЦ ЛОГИРОВАНИЯ: {step_name} ===\n")
        except Exception as e:
            logger.error(f"Ошибка при логировании элементов страницы: {e}")
    
    def _save_page_html(self, filename: str):
        """Сохранение HTML страницы в файл для анализа"""
        try:
            html = self.driver.page_source
            filepath = Path(f"debug_{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"HTML страницы сохранен в: {filepath}")
        except Exception as e:
            logger.warning(f"Не удалось сохранить HTML: {e}")
    
    def _log_element_details(self, element, element_name: str):
        """Детальное логирование информации об элементе"""
        try:
            if element:
                text = element.text.strip()[:100] if hasattr(element, 'text') else ''
                tag = element.tag_name if hasattr(element, 'tag_name') else 'unknown'
                is_displayed = element.is_displayed() if hasattr(element, 'is_displayed') else False
                is_enabled = element.is_enabled() if hasattr(element, 'is_enabled') else False
                
                attrs = {}
                try:
                    attrs['data-qa'] = element.get_attribute('data-qa')
                    attrs['id'] = element.get_attribute('id')
                    attrs['class'] = element.get_attribute('class')
                    attrs['type'] = element.get_attribute('type')
                    attrs['name'] = element.get_attribute('name')
                    attrs['placeholder'] = element.get_attribute('placeholder')
                    attrs['aria-label'] = element.get_attribute('aria-label')
                except:
                    pass
                
                logger.info(f"Детали элемента '{element_name}':")
                logger.info(f"  Тег: {tag}")
                logger.info(f"  Текст: '{text}'")
                logger.info(f"  Видим: {is_displayed}")
                logger.info(f"  Активен: {is_enabled}")
                logger.info(f"  Атрибуты: {attrs}")
            else:
                logger.warning(f"Элемент '{element_name}' не найден (None)")
        except Exception as e:
            logger.debug(f"Ошибка при логировании деталей элемента '{element_name}': {e}")
    
    def _login(self):
        """Авторизация на hh.ru"""
        try:
            logger.info("Начинаю авторизацию на hh.ru...")
            self.driver.get("https://hh.ru/account/login")
            
            # Ждем загрузки React-приложения
            wait = WebDriverWait(self.driver, 30)
            
            # Ждем, пока страница полностью загрузится
            logger.info("Ожидание загрузки страницы...")
            time.sleep(1)  # Даем React-приложению время на инициализацию
            
            # Проверяем, что React-приложение загрузилось
            try:
                wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
                logger.info("Страница загружена")
            except:
                logger.warning("Таймаут ожидания загрузки страницы")
            
            # Ждем появления формы входа (React-компонент)
            logger.info("Ожидание появления формы входа...")
            time.sleep(1)
            
            # Ждем загрузки React-приложения - проверяем наличие React-корня
            logger.info("Ожидание загрузки React-приложения...")
            try:
                wait.until(lambda driver: driver.execute_script(
                    "return document.getElementById('HH-React-Root') !== null && "
                    "document.querySelector('[data-qa=\"applicant-login-card\"]') !== null"
                ))
                logger.info("React-приложение загружено")
            except:
                logger.warning("Таймаут ожидания React-приложения")
            
            time.sleep(2)  # Дополнительное время для инициализации компонентов
            
            # Логируем состояние страницы перед началом поиска элементов
            self._log_page_elements("После загрузки страницы входа")
            
            # ШАГ 0: Нажимаем кнопку "Войти" чтобы открыть форму входа
            logger.info("=" * 60)
            logger.info("ШАГ 0: Нажатие кнопки 'Войти' для открытия формы...")
            logger.info("=" * 60)
            try:
                submit_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-qa='submit-button']"))
                )
                logger.info(f"Найдена кнопка 'Войти': текст='{submit_button.text}', видима={submit_button.is_displayed()}, активна={submit_button.is_enabled()}")
                
                # Ждем, пока кнопка станет активной, если она disabled
                if not submit_button.is_enabled():
                    logger.info("Кнопка 'Войти' неактивна, ждем активации...")
                    for _ in range(15):
                        try:
                            if submit_button.is_enabled():
                                logger.info("Кнопка 'Войти' активирована")
                                break
                        except:
                            pass
                        time.sleep(1)
                        submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[data-qa='submit-button']")
                
                # Кликаем на кнопку "Войти"
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
                time.sleep(0.5)
                self.driver.execute_script("arguments[0].click();", submit_button)
                logger.info("✓ Нажата кнопка 'Войти'")
                time.sleep(1)
                
                # Логируем состояние после нажатия "Войти"
                self._log_page_elements("После нажатия кнопки 'Войти'")
            except Exception as e:
                logger.warning(f"Не удалось нажать кнопку 'Войти': {e}")
                logger.info("Возможно, форма уже открыта")
            
            # ШАГ 1: Находим и кликаем на radio button "Почта" для выбора способа входа
            logger.info("=" * 60)
            logger.info("ШАГ 1: Поиск переключателя 'Почта' для выбора способа входа...")
            logger.info("=" * 60)
            
            # Ищем radio button для выбора почты
            email_radio_selectors = [
                "input[data-qa='credential-type-EMAIL']",
                "input[type='radio'][value='EMAIL']",
                "input[type='radio'][name*='credential'][value*='EMAIL']",
                "[data-qa='credential-type-EMAIL']"
            ]
            
            email_radio = None
            # Пробуем найти radio button "Почта"
            for selector in email_radio_selectors:
                try:
                    logger.debug(f"Пробуем селектор для radio 'Почта': {selector}")
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.debug(f"  Найдено элементов с селектором '{selector}': {len(elements)}")
                    for elem in elements:
                        try:
                            is_displayed = elem.is_displayed()
                            is_enabled = elem.is_enabled()
                            data_qa = elem.get_attribute('data-qa') or ''
                            value = elem.get_attribute('value') or ''
                            logger.debug(f"    Radio: data-qa='{data_qa}', value='{value}', видим={is_displayed}, активен={is_enabled}")
                            
                            if is_displayed and ('EMAIL' in data_qa.upper() or 'EMAIL' in value.upper()):
                                email_radio = elem
                                logger.info(f"✓ Найден radio button 'Почта' с селектором: {selector}")
                                self._log_element_details(email_radio, "Radio button 'Почта'")
                                break
                        except Exception as e:
                            logger.debug(f"    Ошибка при проверке radio: {e}")
                            continue
                    if email_radio:
                        break
                except Exception as e:
                    logger.debug(f"  Ошибка с селектором '{selector}': {e}")
                    continue
            
            # Если не нашли через селекторы, пробуем через JavaScript
            if not email_radio:
                logger.info("Пробуем найти radio button 'Почта' через JavaScript...")
                try:
                    email_radio = self.driver.execute_script("""
                        var radios = document.querySelectorAll('input[type="radio"]');
                        for (var i = 0; i < radios.length; i++) {
                            var radio = radios[i];
                            if (radio.offsetParent !== null && !radio.disabled) {
                                var dataQa = (radio.getAttribute('data-qa') || '').toUpperCase();
                                var value = (radio.getAttribute('value') || '').toUpperCase();
                                if (dataQa.includes('EMAIL') || value.includes('EMAIL')) {
                                    return radio;
                                }
                            }
                        }
                        return null;
                    """)
                    if email_radio:
                        logger.info("Radio button 'Почта' найден через JavaScript")
                except Exception as e:
                    logger.debug(f"Ошибка при поиске radio через JavaScript: {e}")
            
            # Кликаем на radio button "Почта"
            if email_radio:
                try:
                    logger.info("Попытка клика на radio button 'Почта'...")
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", email_radio)
                    time.sleep(0.5)
                    # Для radio button лучше использовать клик через Selenium, а не JS
                    email_radio.click()
                    logger.info("✓ Выбран способ входа 'Почта'")
                    time.sleep(2)
                    
                    # Логируем состояние после выбора почты
                    self._log_page_elements("После выбора способа входа 'Почта'")
                except Exception as e:
                    logger.error(f"✗ Ошибка при клике на radio 'Почта': {e}")
                    # Пробуем через JS как запасной вариант
                    try:
                        self.driver.execute_script("arguments[0].click();", email_radio)
                        logger.info("✓ Выбран способ входа 'Почта' (через JS)")
                        time.sleep(2)
                    except:
                        pass
            else:
                logger.warning("✗ Radio button 'Почта' не найден, возможно уже выбран или используется другой способ входа")
                # Логируем все элементы, если не нашли нужный
                self._log_page_elements("Radio button 'Почта' не найден - логируем все элементы")
            
            # Ждем появления полей ввода после выбора способа входа
            logger.info("=" * 60)
            logger.info("ШАГ 2: Ожидание появления полей ввода...")
            logger.info("=" * 60)
            time.sleep(2)
            
            # Варианты селекторов для поля email/логина
            email_selectors = [
                "input[data-qa='applicant-login-input-email']",
                "input[data-qa='login-input-username']",
                "input[data-qa*='email']",
                "input[data-qa*='EMAIL']",
                "input[name='username']",
                "input[type='email']",
                "input[type='text'][placeholder*='почт']",
                "input[type='text'][placeholder*='телефон']",
                "input[placeholder*='Электронная почта']",
                "input[placeholder*='телефон']",
                "input[placeholder*='Почта']",
                "input[placeholder*='Телефон']",
                "input#username",
                ".bloko-input[type='text']",
                "input.magritte-input",
                "input.magritte-input[type='text']",
                "input[autocomplete='username']",
                "input[autocomplete='email']"
            ]
            
            email_input = None
            # Пробуем найти поле несколько раз с задержками
            for attempt in range(5):
                logger.debug(f"Попытка {attempt + 1}/5: поиск поля email...")
                for selector in email_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        logger.debug(f"  Селектор '{selector}': найдено {len(elements)} элементов")
                        for elem in elements:
                            try:
                                is_displayed = elem.is_displayed()
                                is_enabled = elem.is_enabled()
                                placeholder = elem.get_attribute('placeholder') or ''
                                logger.debug(f"    Поле: placeholder='{placeholder}', видимо={is_displayed}, активно={is_enabled}")
                                
                                if is_displayed and is_enabled:
                                    email_input = elem
                                    logger.info(f"✓ Найдено поле email с селектором: {selector}")
                                    self._log_element_details(email_input, "Поле email")
                                    break
                            except Exception as e:
                                logger.debug(f"    Ошибка при проверке поля: {e}")
                                continue
                        if email_input:
                            break
                    except Exception as e:
                        logger.debug(f"  Ошибка с селектором '{selector}': {e}")
                        continue
                
                if email_input:
                    break
                
                logger.debug(f"Попытка {attempt + 1}/5: поля ввода еще не появились, ждем...")
                time.sleep(2)
            
            # Если не нашли через селекторы, пробуем через JavaScript
            if not email_input:
                logger.info("Пробуем найти поле ввода через JavaScript...")
                try:
                    email_input = self.driver.execute_script("""
                        var inputs = document.querySelectorAll('input[type="text"], input[type="email"]');
                        for (var i = 0; i < inputs.length; i++) {
                            var input = inputs[i];
                            if (input.offsetParent !== null && !input.disabled) {
                                var placeholder = (input.placeholder || '').toLowerCase();
                                var name = (input.name || '').toLowerCase();
                                if (placeholder.includes('почт') || placeholder.includes('телефон') || 
                                    placeholder.includes('email') || name.includes('username') || 
                                    name.includes('login')) {
                                    return input;
                                }
                            }
                        }
                        return null;
                    """)
                    if email_input:
                        logger.info("Поле email найдено через JavaScript")
                except Exception as e:
                    logger.debug(f"Ошибка при поиске через JavaScript: {e}")
            
            if not email_input:
                logger.error("Не удалось найти поле для ввода email")
                logger.info("Возможно, форма загружается или требуется ручная авторизация...")
                logger.info("Попробуйте авторизоваться вручную в открывшемся браузере...")
                input("Нажмите Enter после успешной авторизации...")
                return True  # Предполагаем, что пользователь авторизовался вручную
            
            # Заполнение email
            if email_input:
                logger.info("Заполнение поля email...")
                # Прокручиваем к полю, если нужно
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", email_input)
                time.sleep(0.5)
                
                email_input.clear()
                time.sleep(0.3)
                email_input.click()  # Кликаем для фокуса
                time.sleep(0.3)
                email_input.send_keys(self.config['hh_credentials']['email'])
                logger.info(f"✓ Email введен: {self.config['hh_credentials']['email'][:10]}...")
                time.sleep(1.5)
                
                # Логируем состояние после ввода email
                self._log_page_elements("После ввода email")
            else:
                logger.error("✗ Поле email не найдено, не могу заполнить")
            # Если пользователь вручную авторизуется, то не нужно искать кнопку "Войти с паролем"
            if not self.config["application_settings"]["manual_authorization"]:
                    
                # Варианты селекторов для кнопки "Войти с паролем" / "Продолжить" / "Дальше"
                logger.info("=" * 60)
                logger.info("ШАГ 3: Поиск кнопки 'Войти с паролем' / 'Продолжить'...")
                logger.info("=" * 60)
                # ПРИОРИТЕТ: сначала ищем кнопку "Войти с паролем" для почты
                continue_btn = None
                
                # Сначала ищем кнопку "Войти с паролем" с data-qa='expand-login-by-password'
                try:
                    logger.debug("Ищем кнопку 'Войти с паролем' с data-qa='expand-login-by-password'")
                    password_btn = self.driver.find_element(By.CSS_SELECTOR, "button[data-qa='expand-login-by-password']")
                    if password_btn.is_displayed() and password_btn.is_enabled():
                        continue_btn = password_btn
                        logger.info(f"✓ Найдена кнопка 'Войти с паролем' с data-qa='expand-login-by-password', текст: '{password_btn.text.strip()}'")
                        self._log_element_details(continue_btn, "Кнопка 'Войти с паролем'")
                except NoSuchElementException:
                    logger.debug("Кнопка 'Войти с паролем' не найдена через data-qa")
                except Exception as e:
                    logger.debug(f"Ошибка при поиске кнопки 'Войти с паролем': {e}")
                
                # Если не нашли "Войти с паролем", ищем другие варианты
                if not continue_btn:
                    continue_selectors = [
                        "button[data-qa='account-login-submit']",
                        "button[type='submit']",
                        "button.magritte-button[type='submit']",
                        ".magritte-button[type='submit']"
                    ]
                    
                    for selector in continue_selectors:
                        try:
                            logger.debug(f"Пробуем селектор для кнопки продолжения: {selector}")
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            logger.debug(f"  Найдено элементов с селектором '{selector}': {len(elements)}")
                            for btn in elements:
                                try:
                                    is_displayed = btn.is_displayed()
                                    is_enabled = btn.is_enabled()
                                    text = btn.text.strip()
                                    data_qa = btn.get_attribute('data-qa') or ''
                                    logger.debug(f"    Кнопка: текст='{text[:50]}', data-qa='{data_qa}', видима={is_displayed}, активна={is_enabled}")
                                    
                                    if is_displayed and is_enabled:
                                        text_lower = text.lower()
                                        # Игнорируем кнопку "Дальше" - она для телефона
                                        if 'дальше' in text_lower and 'expand-login-by-password' not in data_qa:
                                            logger.debug(f"    Пропускаем кнопку 'Дальше' - она для телефона")
                                            continue
                                        # Ищем кнопки с текстом "парол" или другие подходящие
                                        if 'парол' in text_lower or 'продолж' in text_lower:
                                            continue_btn = btn
                                            logger.info(f"✓ Найдена кнопка продолжения с селектором: {selector}, текст: '{text}'")
                                            self._log_element_details(continue_btn, "Кнопка продолжения")
                                            break
                                except Exception as e:
                                    logger.debug(f"    Ошибка при проверке кнопки: {e}")
                                    continue
                            if continue_btn:
                                break
                        except NoSuchElementException:
                            logger.debug(f"  Селектор '{selector}' не нашел элементов")
                            continue
                        except Exception as e:
                            logger.debug(f"  Ошибка с селектором '{selector}': {e}")
                            continue
                
                # Если не нашли через селекторы, пробуем через JavaScript
                if not continue_btn:
                    logger.info("Пробуем найти кнопку 'Войти с паролем' через JavaScript...")
                    try:
                        continue_btn = self.driver.execute_script("""
                            // Сначала ищем кнопку "Войти с паролем" с data-qa='expand-login-by-password'
                            var passwordBtn = document.querySelector('button[data-qa="expand-login-by-password"]');
                            if (passwordBtn && passwordBtn.offsetParent !== null && !passwordBtn.disabled) {
                                return passwordBtn;
                            }
                            
                            // Если не нашли, ищем другие кнопки, но игнорируем "Дальше"
                            var buttons = document.querySelectorAll('button[type="submit"], button[data-qa*="submit"], button[data-qa*="login"]');
                            for (var i = 0; i < buttons.length; i++) {
                                var btn = buttons[i];
                                if (btn.offsetParent !== null && !btn.disabled) {
                                    var text = (btn.textContent || btn.innerText || '').toLowerCase();
                                    var dataQa = (btn.getAttribute('data-qa') || '').toLowerCase();
                                    // Игнорируем кнопку "Дальше" - она для телефона
                                    if (text.includes('дальше') && !dataQa.includes('expand-login-by-password')) {
                                        continue;
                                    }
                                    // Ищем кнопки с текстом "парол"
                                    if (text.includes('парол')) {
                                        return btn;
                                    }
                                }
                            }
                            return null;
                        """)
                        if continue_btn:
                            logger.info("Кнопка 'Войти с паролем' найдена через JavaScript")
                    except Exception as e:
                        logger.debug(f"Ошибка при поиске кнопки через JavaScript: {e}")
                
                if continue_btn:
                    try:
                        logger.info("Попытка клика на кнопку 'Войти с паролем'...")
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", continue_btn)
                        time.sleep(0.5)
                        self.driver.execute_script("arguments[0].click();", continue_btn)
                        logger.info("✓ Нажата кнопка 'Войти с паролем' / 'Продолжить'")
                        time.sleep(1)
                        
                        # Логируем состояние после клика
                        self._log_page_elements("После клика на кнопку 'Войти с паролем'")
                    except ElementClickInterceptedException:
                        logger.warning("Кнопка перехвачена, пробуем кликнуть через JS")
                        self.driver.execute_script("arguments[0].click();", continue_btn)
                        time.sleep(1)
                else:
                    # Пробуем нажать Enter в поле email
                    logger.warning("✗ Кнопка 'Войти с паролем' не найдена, пробуем нажать Enter")
                    if email_input:
                        email_input.send_keys(Keys.RETURN)
                        time.sleep(1)
                    else:
                        logger.error("Поле email тоже не найдено, не могу продолжить")
                        self._log_page_elements("Кнопка 'Войти с паролем' не найдена - логируем все элементы")
                
                # Заполнение пароля
                logger.info("=" * 60)
                logger.info("ШАГ 4: Ожидание появления поля пароля...")
                logger.info("=" * 60)
                time.sleep(2)
                
                password_selectors = [
                    "input[data-qa='login-input-password']",
                    "input[name='password']",
                    "input[type='password']",
                    "input[autocomplete='current-password']",
                    "input[autocomplete='password']",
                    "input#password",
                    "input.magritte-input[type='password']"
                ]
                
                password_input = None
                # Пробуем найти поле несколько раз с задержками
                for attempt in range(5):
                    logger.debug(f"Попытка {attempt + 1}/5: поиск поля пароля...")
                    for selector in password_selectors:
                        try:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            logger.debug(f"  Селектор '{selector}': найдено {len(elements)} элементов")
                            for elem in elements:
                                try:
                                    is_displayed = elem.is_displayed()
                                    is_enabled = elem.is_enabled()
                                    placeholder = elem.get_attribute('placeholder') or ''
                                    logger.debug(f"    Поле пароля: placeholder='{placeholder}', видимо={is_displayed}, активно={is_enabled}")
                                    
                                    if is_displayed and is_enabled:
                                        password_input = elem
                                        logger.info(f"✓ Найдено поле пароля с селектором: {selector}")
                                        self._log_element_details(password_input, "Поле пароля")
                                        break
                                except Exception as e:
                                    logger.debug(f"    Ошибка при проверке поля пароля: {e}")
                                    continue
                            if password_input:
                                break
                        except Exception as e:
                            logger.debug(f"  Ошибка с селектором '{selector}': {e}")
                            continue
                    
                    if password_input:
                        break
                    
                    logger.debug(f"Попытка {attempt + 1}/5: поле пароля еще не появилось, ждем...")
                    time.sleep(2)
                
                # Если не нашли через селекторы, пробуем через JavaScript
                if not password_input:
                    logger.info("Пробуем найти поле пароля через JavaScript...")
                    try:
                        password_input = self.driver.execute_script("""
                            var inputs = document.querySelectorAll('input[type="password"]');
                            for (var i = 0; i < inputs.length; i++) {
                                var input = inputs[i];
                                if (input.offsetParent !== null && !input.disabled) {
                                    return input;
                                }
                            }
                            return null;
                        """)
                        if password_input:
                            logger.info("Поле пароля найдено через JavaScript")
                    except Exception as e:
                        logger.debug(f"Ошибка при поиске пароля через JavaScript: {e}")
                
                if not password_input:
                    logger.error("Не удалось найти поле для ввода пароля")
                    logger.info("Попробуйте авторизоваться вручную в открывшемся браузере...")
                    input("Нажмите Enter после успешной авторизации...")
                    return True
                
                # Прокручиваем к полю пароля
                if password_input:
                    logger.info("Заполнение поля пароля...")
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", password_input)
                    time.sleep(0.5)
                    
                    password_input.clear()
                    time.sleep(0.3)
                    password_input.click()  # Кликаем для фокуса
                    time.sleep(0.3)
                    password_input.send_keys(self.config['hh_credentials']['password'])
                    logger.info("✓ Пароль введен")
                    time.sleep(1.5)
                    
                    # Логируем состояние после ввода пароля
                    self._log_page_elements("После ввода пароля")
                else:
                    logger.error("✗ Поле пароля не найдено, не могу заполнить")
                
                # Нажатие кнопки входа
                logger.info("=" * 60)
                logger.info("ШАГ 5: Поиск финальной кнопки входа...")
                logger.info("=" * 60)
                login_selectors = [
                    "button[data-qa='account-login-submit']",
                    "button[type='submit']",
                    ".bloko-button[type='submit']"
                ]
                
                login_btn = None
                for selector in login_selectors:
                    try:
                        logger.debug(f"Пробуем селектор для финальной кнопки входа: {selector}")
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        logger.debug(f"  Найдено элементов с селектором '{selector}': {len(elements)}")
                        for btn in elements:
                            try:
                                is_displayed = btn.is_displayed()
                                is_enabled = btn.is_enabled()
                                text = btn.text.strip()
                                logger.debug(f"    Кнопка входа: текст='{text[:50]}', видима={is_displayed}, активна={is_enabled}")
                                
                                if is_displayed and is_enabled:
                                    login_btn = btn
                                    logger.info(f"✓ Найдена кнопка входа с селектором: {selector}, текст: '{text}'")
                                    self._log_element_details(login_btn, "Финальная кнопка входа")
                                    break
                            except Exception as e:
                                logger.debug(f"    Ошибка при проверке кнопки входа: {e}")
                                continue
                        if login_btn:
                            break
                    except NoSuchElementException:
                        logger.debug(f"  Селектор '{selector}' не нашел элементов")
                        continue
                    except Exception as e:
                        logger.debug(f"  Ошибка с селектором '{selector}': {e}")
                        continue
                
                if login_btn:
                    try:
                        logger.info("Попытка клика на финальную кнопку входа...")
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", login_btn)
                        time.sleep(0.5)
                        self.driver.execute_script("arguments[0].click();", login_btn)
                        logger.info("✓ Нажата кнопка входа")
                    except ElementClickInterceptedException:
                        logger.warning("Кнопка входа перехвачена, пробуем кликнуть через JS")
                        self.driver.execute_script("arguments[0].click();", login_btn)
                else:
                    # Пробуем нажать Enter в поле пароля
                    logger.warning("✗ Кнопка входа не найдена, пробуем нажать Enter в поле пароля")
                    if password_input:
                        password_input.send_keys(Keys.RETURN)
                        logger.info("Нажат Enter в поле пароля")
                    else:
                        logger.error("Поле пароля тоже не найдено")
                        self._log_page_elements("Кнопка входа не найдена - логируем все элементы")
            else:
                logger.info("Авторизация на hh.ru не требуется, т.к. выполняется вручную")
                time.sleep(1)
            
            # Ожидание успешной авторизации
            logger.info("=" * 60)
            logger.info("ШАГ 6: Проверка успешности авторизации...")
            logger.info("=" * 60)
            time.sleep(1)
            
            # Логируем финальное состояние страницы
            self._log_page_elements("Финальное состояние после входа")
            
            # Проверка успешной авторизации
            current_url = self.driver.current_url
            logger.info(f"Текущий URL после входа: {current_url}")
            
            # Проверяем различные признаки успешной авторизации
            if "login" not in current_url.lower():
                # Дополнительная проверка - ищем элементы, которые появляются после входа
                try:
                    # Проверяем наличие элементов личного кабинета
                    self.driver.find_element(By.CSS_SELECTOR, "[data-qa='mainmenu_applicantResumes'], .supernova-navi-item, [data-qa='mainmenu_myResumes']")
                    logger.info("✅ Авторизация успешна!")
                    return True
                except NoSuchElementException:
                    # Если не нашли элементы, но и не на странице логина - возможно авторизовались
                    if "hh.ru" in current_url:
                        logger.info("✅ Авторизация успешна (по URL)")
                        return True
            
            # Если требуется капча или двухфакторная аутентификация
            try:
                captcha = self.driver.find_element(By.CSS_SELECTOR, "[class*='captcha'], [id*='captcha']")
                if captcha:
                    logger.warning("Обнаружена капча. Требуется ручная авторизация.")
                    logger.info("Пожалуйста, пройдите капчу в открывшемся браузере...")
                    input("Нажмите Enter после успешной авторизации...")
                    return True
            except NoSuchElementException:
                pass
            
            logger.warning("Не удалось автоматически определить успешность авторизации")
            logger.info("Проверьте вручную в браузере. Если авторизовались - нажмите Enter для продолжения...")
            user_input = input("Авторизованы? (y/n или Enter для продолжения): ")
            if user_input.lower() in ['y', 'yes', 'да', '']:
                return True
            return False
                
        except Exception as e:
            logger.error(f"Ошибка при авторизации: {e}", exc_info=True)
            logger.info("Попробуйте авторизоваться вручную в открывшемся браузере...")
            user_input = input("Авторизовались вручную? (y/n): ")
            if user_input.lower() in ['y', 'yes', 'да']:
                return True
            return False
    
    def _build_search_url(self, keyword: str = None) -> str:
        """Построение URL для поиска вакансий
        
        Args:
            keyword: Одно ключевое слово для поиска. Если None, используется первое из списка.
        """
        base_url = "https://hh.ru/search/vacancy"
        params_dict = {}
        
        filters = self.config['search_filters']
        
        # Ключевое слово - используем одно слово за раз
        if keyword:
            params_dict['text'] = keyword
        elif filters.get('keywords'):
            # Если не указано ключевое слово, используем первое из списка
            params_dict['text'] = filters['keywords'][0]
        
        # Зарплата
        if filters.get('salary_min'):
            params_dict['salary'] = str(filters['salary_min'])
        
        # Регион (Москва = 1, СПб = 2, и т.д.)
        if filters.get('area'):
            area_map = {"Москва": "1", "Санкт-Петербург": "2"}
            area = area_map.get(filters['area'], "1")
            params_dict['area'] = area
        
        # Опыт работы
        if filters.get('experience'):
            exp_map = {
                "noExperience": "noExperience",
                "between1And3": "between1And3",
                "between3And6": "between3And6",
                "moreThan6": "moreThan6"
            }
            exp = exp_map.get(filters['experience'], "")
            if exp:
                params_dict['experience'] = exp
        
        # Тип занятости
        if filters.get('employment'):
            employment_map = {
                "full": "full",
                "part": "part",
                "project": "project",
                "volunteer": "volunteer",
                "probation": "probation"
            }
            emp = employment_map.get(filters['employment'], "")
            if emp:
                params_dict['employment'] = emp
        
        # График работы
        if filters.get('schedule'):
            schedule_map = {
                "fullDay": "fullDay",
                "shift": "shift",
                "flexible": "flexible",
                "remote": "remote",
                "flyInFlyOut": "flyInFlyOut"
            }
            schedule = schedule_map.get(filters['schedule'], "")
            if schedule:
                params_dict['schedule'] = schedule
        
        # Строим URL с правильным кодированием
        url = f"{base_url}?{urlencode(params_dict, doseq=True)}"
        logger.info(f"URL поиска (ключевое слово: '{keyword or filters.get('keywords', [''])[0]}'): {url}")
        return url
    
    def _get_vacancy_links(self) -> List[str]:
        """Получение списка ссылок на вакансии со страницы поиска"""
        vacancy_links = []
        try:
            # Ждем загрузки страницы поиска (уменьшена задержка)
            time.sleep(1)
            
            # Логируем состояние страницы для отладки
            current_url = self.driver.current_url
            logger.info(f"Текущий URL страницы поиска: {current_url}")
            
            # Проверяем, что мы на странице поиска
            if '/search/vacancy' not in current_url:
                logger.warning(f"Не на странице поиска! URL: {current_url}")
            
            # Используем только основной селектор для скорости
            # Если не найдем, попробуем альтернативные
            try:
                wait = WebDriverWait(self.driver, 5)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-qa='serp-item__title']")))
                cards = self.driver.find_elements(By.CSS_SELECTOR, "a[data-qa='serp-item__title']")
                logger.info(f"Найдено {len(cards)} вакансий основным селектором")
            except TimeoutException:
                # Если основной селектор не сработал, пробуем альтернативные
                logger.debug("Основной селектор не нашел элементы, пробуем альтернативные...")
                cards = []
                alternative_selectors = [
                    "a[href^='https://hh.ru/vacancy/']",
                    "a[href*='/vacancy/'][data-qa*='serp']"
                ]
                for selector in alternative_selectors:
                    try:
                        found_cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if found_cards:
                            cards = found_cards
                            logger.info(f"Найдено {len(cards)} вакансий селектором '{selector}'")
                            break
                    except:
                        continue
            
            # Убираем дубликаты и проверяем ссылки
            seen_links = set()
            for card in cards:
                try:
                    link = card.get_attribute('href')
                    if link:
                        # Обрабатываем относительные ссылки
                        if link.startswith('/vacancy/'):
                            link = f"https://hh.ru{link}"
                        
                        if '/vacancy/' in link:
                            # Очистка URL от параметров
                            clean_link = link.split('?')[0]
                            # Убираем дубликаты
                            if clean_link not in seen_links:
                                seen_links.add(clean_link)
                                vacancy_links.append(clean_link)
                except Exception as e:
                    logger.debug(f"Ошибка при обработке элемента: {e}")
                    continue
            
            logger.info(f"Найдено {len(vacancy_links)} уникальных вакансий на странице")
            if vacancy_links and logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Первые 5 вакансий:")
                for i, link in enumerate(vacancy_links[:5], 1):
                    logger.debug(f"  {i}. {link}")
            
            return vacancy_links
            
        except Exception as e:
            logger.error(f"Ошибка при получении ссылок на вакансии: {e}", exc_info=True)
            return []
    
    def _apply_to_vacancy(self, vacancy_url: str, search_page_url: str = None) -> bool:
        """Отправка отклика на вакансию"""
        search_page_url = search_page_url or self.driver.current_url  # Сохраняем URL для возврата
        try:
            vacancy_id = vacancy_url.split('/')[-1].split('?')[0]
            
            # Проверка, не откликались ли уже
            if self.config['application_settings']['skip_already_applied']:
                if vacancy_id in self.applied_vacancies:
                    logger.info(f"Пропускаю вакансию {vacancy_id} - уже откликались")
                    self.skipped_count += 1
                    return False
            
            logger.info(f"Открываю вакансию: {vacancy_url}")
            self.driver.get(vacancy_url)
            time.sleep(random.uniform(1.5, 2.5))  # Уменьшена задержка
            
            # Проверка, не попали ли мы на страницу vacancy_response (форма отклика)
            current_url = self.driver.current_url
            if 'vacancy_response' in current_url or '/applicant/vacancy_response' in current_url:
                logger.warning(f"Пропускаю вакансию {vacancy_id} - открылась страница формы отклика (vacancy_response), такая вакансия требует особой обработки")
                self.skipped_count += 1
                
                # Возвращаемся на страницу поиска
                logger.info("Возвращаюсь на страницу поиска...")
                self.driver.get(search_page_url)
                time.sleep(1)
                
                return False
            
            # Поиск кнопки отклика
            wait = WebDriverWait(self.driver, 3)
            
            # Различные варианты селекторов для кнопки отклика
            apply_selectors = [
                "button[data-qa='vacancy-response-link-top']",
                "a[data-qa='vacancy-response-link-top']",
                "button[data-qa='vacancy-response-button']",
                ".bloko-button[data-qa*='response']",
                "a.bloko-button[href*='response']"
            ]
            
            apply_button = None
            for selector in apply_selectors:
                try:
                    apply_button = wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if not apply_button:
                # Проверка, может уже откликнулись
                try:
                    already_applied = self.driver.find_element(
                        By.CSS_SELECTOR, 
                        "[data-qa*='already-applied'], .vacancy-response-link-already-applied"
                    )
                    logger.info(f"Уже откликались на вакансию {vacancy_id}")
                    self._save_applied_vacancy(vacancy_id)
                    self.skipped_count += 1
                    
                    # Возвращаемся на страницу поиска
                    logger.info("Возвращаюсь на страницу поиска...")
                    self.driver.get(search_page_url)
                    time.sleep(1)  # Уменьшена задержка
                    
                    return False
                except NoSuchElementException:
                    logger.warning(f"Не найдена кнопка отклика для вакансии {vacancy_id}")
                    self.error_count += 1
                    
                    # Возвращаемся на страницу поиска
                    logger.info("Возвращаюсь на страницу поиска...")
                    self.driver.get(search_page_url)
                    time.sleep(1)  # Уменьшена задержка
                    
                    return False
            
            # Прокрутка к кнопке
            self.driver.execute_script("arguments[0].scrollIntoView(true);", apply_button)
            time.sleep(1)
            
            # Клик на кнопку отклика
            apply_button.click()
            time.sleep(random.uniform(1, 1.5))  # Уменьшена задержка
            
            # Проверка, не попали ли мы на страницу vacancy_response после клика
            current_url = self.driver.current_url
            if 'vacancy_response' in current_url or '/applicant/vacancy_response' in current_url:
                logger.warning(f"Пропускаю вакансию {vacancy_id} - после клика открылась страница формы отклика (vacancy_response), такая вакансия требует особой обработки")
                self.skipped_count += 1
                
                # Возвращаемся на страницу поиска
                logger.info("Возвращаюсь на страницу поиска...")
                self.driver.get(search_page_url)
                time.sleep(1)
                
                return False
            
            # Обработка cookies banner, если он есть
            try:
                cookies_banner = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "[data-qa='cookies-policy-informer'], .cookies-policy-informer"
                )
                if cookies_banner.is_displayed():
                    logger.debug("Найден cookies banner, закрываю...")
                    try:
                        accept_button = self.driver.find_element(
                            By.CSS_SELECTOR,
                            "button[data-qa='cookies-policy-informer-accept'], .cookies-policy-informer-accept"
                        )
                        self.driver.execute_script("arguments[0].click();", accept_button)
                        time.sleep(0.5)
                    except:
                        # Если не нашли кнопку, просто скрываем баннер через JS
                        self.driver.execute_script("arguments[0].style.display='none';", cookies_banner)
                        time.sleep(0.5)
            except NoSuchElementException:
                pass  # Cookies banner не найден, это нормально
            
            # Заполнение сопроводительного письма, если требуется
            try:
                cover_letter_textarea = wait.until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        "textarea[data-qa='vacancy-response-popup-form-letter-input']"
                    ))
                )
                cover_letter = self.config['application_settings']['cover_letter']
                cover_letter_textarea.clear()
                cover_letter_textarea.send_keys(cover_letter)
                time.sleep(0.5)
            except TimeoutException:
                logger.debug("Поле для сопроводительного письма не найдено, пропускаю")
            
            # Подтверждение отклика
            try:
                submit_button = wait.until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        "button[data-qa='vacancy-response-submit-popup']"
                    ))
                )
                # Прокручиваем к кнопке и используем JS клик для надежности
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
                time.sleep(0.3)
                # Пробуем обычный клик, если не получается - используем JS
                try:
                    submit_button.click()
                except:
                    self.driver.execute_script("arguments[0].click();", submit_button)
                time.sleep(random.uniform(1, 2))
                
                logger.info(f"✅ Успешно откликнулся на вакансию {vacancy_id}")
                self._save_applied_vacancy(vacancy_id)
                self.applied_count += 1
                
                # Возвращаемся на страницу поиска
                logger.info("Возвращаюсь на страницу поиска...")
                self.driver.get(search_page_url)
                time.sleep(2)
                
                return True
                
            except TimeoutException:
                # Возможно, отклик прошел без дополнительного подтверждения
                logger.info(f"✅ Отклик отправлен на вакансию {vacancy_id}")
                self._save_applied_vacancy(vacancy_id)
                self.applied_count += 1
                
                # Возвращаемся на страницу поиска
                logger.info("Возвращаюсь на страницу поиска...")
                self.driver.get(search_page_url)
                time.sleep(2)
                
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при отклике на вакансию {vacancy_url}: {e}")
            self.error_count += 1
            
            # Возвращаемся на страницу поиска даже при ошибке
            try:
                logger.info("Возвращаюсь на страницу поиска после ошибки...")
                self.driver.get(search_page_url)
                time.sleep(2)
            except Exception as return_error:
                logger.warning(f"Не удалось вернуться на страницу поиска: {return_error}")
            
            return False
    
    def _human_like_delay(self):
        """Человекоподобная задержка"""
        delay = self.config['application_settings']['delay_between_applications']
        # Добавляем случайность ±30%
        random_delay = delay * random.uniform(0.7, 1.3)
        time.sleep(random_delay)
    
    def run(self):
        """Основной метод запуска автоотклика"""
        try:
            logger.info("=" * 50)
            logger.info("Запуск автоматического отклика на hh.ru")
            logger.info("=" * 50)
            
            # Настройка браузера
            self._setup_driver()
            
            # Авторизация
            if not self._login():
                logger.error("Не удалось авторизоваться. Завершение работы.")
                return
            
            max_applications = self.config['application_settings']['max_applications_per_day']
            applications_today = 0
            
            # Получаем список ключевых слов
            keywords = self.config['search_filters'].get('keywords', [])
            if not keywords:
                logger.error("Ключевые слова не указаны в конфиге!")
                return
            
            logger.info(f"Будем искать по {len(keywords)} ключевым словам: {keywords}")
            
            # Цикл по каждому ключевому слову
            for keyword_index, keyword in enumerate(keywords, 1):
                if applications_today >= max_applications:
                    logger.info(f"Достигнут лимит откликов на сегодня ({max_applications})")
                    break
                
                logger.info("=" * 60)
                logger.info(f"ПОИСК ПО КЛЮЧЕВОМУ СЛОВУ {keyword_index}/{len(keywords)}: '{keyword}'")
                logger.info("=" * 60)
                
                # Построение URL поиска для текущего ключевого слова
                search_url = self._build_search_url(keyword=keyword)
                self.driver.get(search_url)
                time.sleep(1.5)  # Уменьшена задержка
                
                # Цикл по страницам поиска для текущего ключевого слова
                page = 0
                while applications_today < max_applications:
                    page += 1
                    logger.info(f"\n--- Ключевое слово '{keyword}' - Страница {page} ---")
                    
                    # Получение ссылок на вакансии
                    vacancy_links = self._get_vacancy_links()
                    
                    if not vacancy_links:
                        logger.info(f"Вакансии не найдены для '{keyword}' на странице {page}. Переход к следующему ключевому слову.")
                        break
                    
                    # Сохраняем URL текущей страницы поиска
                    current_search_url = self.driver.current_url
                    
                    # Обработка каждой вакансии
                    for vacancy_url in vacancy_links:
                        if applications_today >= max_applications:
                            logger.info(f"Достигнут лимит откликов на сегодня ({max_applications})")
                            break
                        
                        logger.info(f"Обрабатываю вакансию {vacancy_url} ({applications_today + 1}/{max_applications})")
                        
                        if self._apply_to_vacancy(vacancy_url, current_search_url):
                            applications_today += 1
                            logger.info(f"Прогресс: {applications_today}/{max_applications} откликов отправлено")
                        else:
                            logger.info(f"Не удалось откликнуться на вакансию {vacancy_url}")
                        
                        # Задержка между откликами
                        self._human_like_delay()
                    
                    # Переход на следующую страницу для текущего ключевого слова
                    if applications_today >= max_applications:
                        logger.info(f"Достигнут лимит откликов на сегодня ({max_applications})")
                        break
                    
                    try:
                        # Убеждаемся, что мы на странице поиска
                        if '/search/vacancy' not in self.driver.current_url:
                            logger.warning("Не на странице поиска, возвращаюсь...")
                            self.driver.get(current_search_url)
                            time.sleep(2)
                        
                        next_button = self.driver.find_element(
                            By.CSS_SELECTOR,
                            "a[data-qa='pager-next']"
                        )
                        
                        # Проверяем, не disabled ли кнопка
                        button_class = next_button.get_attribute("class") or ""
                        if "disabled" in button_class or "HH-Pager-Disabled" in button_class:
                            logger.info(f"Достигнута последняя страница для '{keyword}'. Переход к следующему ключевому слову.")
                            break
                        
                        logger.info("Переход на следующую страницу...")
                        next_button.click()
                        time.sleep(random.uniform(1.5, 2.5))  # Уменьшена задержка
                        
                        # Обновляем URL страницы поиска
                        current_search_url = self.driver.current_url
                        logger.info(f"Перешел на страницу: {current_search_url}")
                        
                    except NoSuchElementException:
                        logger.info(f"Кнопка 'Следующая страница' не найдена для '{keyword}'. Переход к следующему ключевому слову.")
                        break
                    except Exception as e:
                        logger.error(f"Ошибка при переходе на следующую страницу: {e}")
                        break
                
                logger.info(f"Завершен поиск по ключевому слову '{keyword}'. Найдено откликов: {applications_today}/{max_applications}")
                
                if applications_today >= max_applications:
                    logger.info(f"Достигнут лимит откликов на сегодня ({max_applications})")
                    break
            
            # Итоговая статистика
            logger.info("\n" + "=" * 50)
            logger.info("ИТОГОВАЯ СТАТИСТИКА:")
            logger.info(f"Откликов отправлено: {self.applied_count}")
            logger.info(f"Пропущено: {self.skipped_count}")
            logger.info(f"Ошибок: {self.error_count}")
            logger.info("=" * 50)
            
        except KeyboardInterrupt:
            logger.info("\nПрервано пользователем")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}", exc_info=True)
        finally:
            if self.driver:
                logger.info("Закрываю браузер...")
                self.driver.quit()


def main():
    """Точка входа"""
    try:
        auto_apply = HHAutoApply()
        auto_apply.run()
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}", exc_info=True)


if __name__ == "__main__":
    main()

