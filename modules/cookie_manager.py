import json
import os
import logging
import time  # Для пауз
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from modules.app_config import env_config

logger = logging.getLogger(__name__)


class CookieManager:
    """
    Керує завантаженням, збереженням та оновленням Lardi-Trans cookie.
    Використовує Selenium для автоматизованого входу та отримання cookie.
    """

    def __init__(self, cookies_file='cookies.json'):
        self.cookies_file = cookies_file
        self.cookies = self._load_cookies()
        # Змінений URL сторінки входу, як вказано користувачем
        self.login_url = env_config.LARDI_LOGIN_URL
        self.username = env_config.LARDI_USERNAME
        self.password = env_config.LARDI_PASSWORD

        self.authenticated_page_url = "https://lardi-trans.com/log/search/gruz/"

    def _load_cookies(self) -> dict:
        """Завантажує cookie з файлу JSON."""
        if os.path.exists(self.cookies_file):
            try:
                with open(self.cookies_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                    logger.info(f"Cookie завантажено з {self.cookies_file}")
                    return cookies
            except json.JSONDecodeError as e:
                logger.error(f"Помилка декодування JSON у файлі cookie ({self.cookies_file}): {e}. Створюємо новий файл.")
                return {}
            except Exception as e:
                logger.error(f"Не вдалося завантажити cookie з {self.cookies_file}: {e}. Створюємо новий файл.")
                return {}
        logger.info(f"Файл cookie {self.cookies_file} не знайдено. Почнемо з порожніх cookie.")
        return {}

    def _save_cookies(self):
        """Зберігає поточні cookie у файл JSON."""
        try:
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(self.cookies, f, indent=4, ensure_ascii=False)
            logger.info(f"Cookie збережено у {self.cookies_file}")
        except Exception as e:
            logger.error(f"Не вдалося зберегти cookie у {self.cookies_file}: {e}")

    def get_cookie_string(self) -> str:
        """Повертає cookie у форматі рядка для заголовка 'Cookie'."""
        self.cookies = self._load_cookies()
        return "; ".join([f"{key}={value}" for key, value in self.cookies.items()])

    def _handle_session_limit_modal(self, driver) -> bool:
        """
        Перевіряє наявність модального вікна ліміту сесій та натискає кнопку видалення.
        Повертає True, якщо модальне вікно було оброблено, False - інакше.
        """
        delete_button_xpath = "//button[contains(@class, 'passport--limit-modal__sessions__session__delete')]"
        try:
            logger.info("Перевіряю наявність кнопки видалення сесії...")
            delete_button = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, delete_button_xpath))
            )
            logger.warning("Знайдено кнопку видалення сесії. Натискаю...")
            delete_button.click()
            # Чекаємо, поки модальне вікно зникне або сторінка оновиться
            time.sleep(0.5)
            logger.info("Кнопку видалення сесії натиснуто.")
            return True
        except TimeoutException:
            logger.info("Кнопка видалення сесії не знайдена (таймаут).")
            return False
        except Exception as e:
            logger.error(f"Помилка при спробі натиснути кнопку видалення сесії: {e}")
            return False

    def refresh_lardi_cookies(self) -> bool:
        """
        Виконує вхід на Lardi-Trans за допомогою Selenium для отримання нових cookie.
        Повертає True, якщо оновлення успішне, False - якщо ні.
        """
        if not self.username or not self.password:
            logger.error("Логін або пароль Lardi-Trans не налаштовані в .env. Неможливо оновити cookie автоматично.")
            return False

        driver = None
        try:
            options = uc.ChromeOptions()
            # options.add_argument('--headless')  # Запуск без вікна браузера
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--start-maximized')
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-blink-features=AutomationControlled")

            options.add_argument(r"--user-data-dir=C:\Users\artur\PycharmProjects\LardiTrans_Search\modules\profile")
            logger.info("Запуск Undetected ChromeDriver...")

            driver = uc.Chrome(options=options)
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                'source': '''
                    delete window.cdc_adoQpoasnfa76fcZLmcfl_Array;
                    delete window.cdc_adoQpoasnfa76fcZLmcfl_Promise;
                    delete window.cdc_adoQpoasnfa76fcZLmcfl_Symbol;
                '''
            })
            driver.set_page_load_timeout(30)
            wait = WebDriverWait(driver, 30)

            logger.info(f"Спроба перейти на автентифіковану сторінку для перевірки статусу входу: {self.login_url}")
            driver.get(self.authenticated_page_url)
            time.sleep(2)

            if self.login_url not in driver.current_url:
                logger.info("Браузер, схоже, вже авторизований. Копіюємо cookie")
                all_browser_cookies = driver.get_cookies()
                new_cookies = {}
                for cookie in all_browser_cookies:
                    new_cookies[cookie['name']] = cookie['value']

                if new_cookies:
                    self.cookies.update(new_cookies)
                    self._save_cookies()
                    logger.info("Cookie Lardi-Trans успішно оновлено (перезавантажено з вже авторизованої сторінки).")
                    return True
                else:
                    logger.warning("Після перевірки авторизації не отримано нових cookie. Спроба авторизуватись.")

            logger.info(f"Перехід на сторінку входу: {self.login_url}")
            driver.get(self.login_url)
            time.sleep(1)

            login_field_xpath = "//input[@name='login']"
            username_input = wait.until(EC.presence_of_element_located((By.XPATH, login_field_xpath)))
            logger.info(f"Знайдено поле логіну за XPath: {login_field_xpath}")

            password_field_xpath = "//input[@type='password']"
            password_input = wait.until(EC.presence_of_element_located((By.XPATH, password_field_xpath)))
            logger.info(f"Знайдено поле паролю за XPath: {password_field_xpath}")

            if username_input.get_attribute('value'):
                logger.info("Поле логіну вже заповнене. Пропускаємо введення.")
            else:
                username_input.send_keys(self.username)
                logger.info("Введено логін.")

            if password_input.get_attribute('value'):
                logger.info("Поле паролю вже заповнене. Пропускаємо введення.")
            else:
                password_input.send_keys(self.password)
                logger.info("Введено пароль.")

            remember_me_checkbox_xpath = "//span[@class='passport-checkbox__label']"
            try:
                remember_me_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, remember_me_checkbox_xpath)))
                if not remember_me_checkbox.is_selected(): # Перевіряємо, чи не обраний вже
                    remember_me_checkbox.click()
                    logger.info("Натиснуто чекбокс 'Запам'ятати мене'.")
                else:
                    logger.info("Чекбокс 'Запам'ятати мене' вже обраний.")
            except TimeoutException:
                logger.warning("Не вдалося знайти або натиснути чекбокс 'Запам'ятати мене' за таймаут.")
            except Exception as e:
                logger.warning(f"Помилка при натисканні чекбоксу 'Запам'ятати мене': {e}")

            login_button_xpath = "//button[@type='submit' and text()='Увійти']"
            login_button = wait.until(EC.element_to_be_clickable((By.XPATH, login_button_xpath)))
            logger.info(f"Знайдено кнопку 'Увійти' за XPath: {login_button_xpath}. Натискання...")
            time.sleep(1)
            login_button.click()

            self._handle_session_limit_modal(driver)

            time.sleep(2)

            if self.login_url in driver.current_url:
                if "Неправильный логин или пароль" in driver.page_source or "Incorrect login or password" in driver.page_source:
                    logger.error("Вхід не вдався: невірний логін або пароль.")
                    return False
                logger.error("Вхід не вдався: залишилися на сторінці входу без явного повідомлення про помилку.")
                return False

            all_browser_cookies = driver.get_cookies()
            new_cookies = {}
            for cookie in all_browser_cookies:
                new_cookies[cookie['name']] = cookie['value']

            if new_cookies:
                self.cookies.update(new_cookies)
                self._save_cookies()
                logger.info("Cookie Lardi-Trans успішно оновлено за допомогою Selenium.")
                return True
            else:
                logger.error("Після входу через Selenium не отримано нових cookie. Можливо, вхід не вдався.")
                return False

        except TimeoutException:
            logger.error("Таймаут очікування елементів або завантаження сторінки під час входу через Selenium.")
            return False
        except WebDriverException as e:
            logger.error(f"Помилка WebDriver під час входу через Selenium: {e}")
            return False
        except Exception as e:
            logger.error(f"Непередбачена помилка під час оновлення cookie через Selenium: {e}")
            return False
        finally:
            if driver:
                logger.info("Закриття браузера Selenium.")
                driver.quit()

