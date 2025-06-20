import os
import requests
import json
import logging
from dotenv import load_dotenv
from modules.cookie_manager import CookieManager
from typing import Optional

# Завантажуємо змінні середовища
load_dotenv()

logger = logging.getLogger(__name__)

_cookie_manager = CookieManager()


class LardiOfferClient:
    """
    Клієнт для отримання інформації про конкретний вантаж з Lardi-Trans.
    """
    def __init__(self):
        self.base_url = "https://lardi-trans.com/webapi/proposal/offer/gruz/"
        self._update_headers_with_cookies() # Оновлюємо заголовки при ініціалізації

    def _update_headers_with_cookies(self):
        """Оновлює заголовки HTTP з поточними cookie від CookieManager."""
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "user-agent": "Mozilla/5.0",
            "cookie": _cookie_manager.get_cookie_string(),  # Беремо cookie з менеджера
            "referer": "https://lardi-trans.com/log/search/gruz/",
            "origin": "https://lardi-trans.com"
        }

    def get_offer(self, offer_id: int, retry_count: int = 1) -> Optional[dict]:
        """Отримати інформацію про вантаж за його ID."""
        url = f"{self.base_url}{offer_id}/awaiting/?currentId={offer_id}"
        self._update_headers_with_cookies()

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status() # виклик HTTPError для 4xx/5xx статусів
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                logger.warning(f"Отримано 401 Unauthorized для offer_id={offer_id}. Спроба оновити cookie.")
                if retry_count > 0:
                    if _cookie_manager.refresh_lardi_cookies():
                        logger.info("Cookie успішно оновлено. Повторюємо запит.")
                        self._update_headers_with_cookies() # Оновлюємо заголовки після оновлення cookie
                        return  self.get_offer(offer_id=offer_id, retry_count=retry_count - 1)
                    else:
                        logger.error("Не вдалося оновити cookie. Не можу повторити запит.")
                        raise Exception(f"Error 401: Не вдалося авторизуватись, неможливо оновити cookie.")
                else:
                    logger.error(f"Не вдалося отримати дані після повторної спроби. Максимальна кількість спроб.")
                    raise Exception(f"Error: {response.status_code}: {response.text}")
            else:
                logger.error(f"Непередбачена HTTP помилка для offer_id={offer_id}: {e}")
                raise Exception(f"Error {response.status_code}: {response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Помилка мережі при отриманні offer_id={offer_id}: {e}")
            raise Exception(f"Network Error: {e}")
        except Exception as e:
            logger.error(f"Невідома помилка при отриманні offer_id={offer_id}: {e}")
            raise Exception(f"Unknown Error: {e}")


class LardiClient:
    """
    Клієнт для пошуку вантажів та управління фільтрами на Lardi-Trans.
    """
    def __init__(self):
        self.url = "https://lardi-trans.com/webapi/proposal/search/gruz/"
        self._update_headers_with_cookies() # Оновлюємо заголовки при ініціалізації
        self.page = 1
        self.page_size = 20
        self.sort_by_country = False
        self.filters = self.default_filters()

    def _update_headers_with_cookies(self):
        """Оновлює заголовки HTTP з поточними cookie від CookieManager."""
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "origin": "https://lardi-trans.com",
            "referer": "https://lardi-trans.com/log/search/gruz/",
            "user-agent": "Mozilla/5.0",
            "cookie": _cookie_manager.get_cookie_string(), # Беремо cookie з менеджера
        }

    def default_filters(self):
        """Повертає фільтри за замовчуванням."""
        return {
            "directionFrom": {"directionRows": [{"countrySign": "UA"}]},
            "directionTo": {"directionRows": [{"countrySign": "UA"}]},
            "mass1": None, # Додано, щоб можна було встановлювати через інтерфейс
            "mass2": None, # Додано, щоб можна було встановлювати через інтерфейс
            "volume1": None,
            "volume2": None,
            "dateFromISO": None,
            "dateToISO": None,
            "bodyTypeIds": [],
            "loadTypes": ["top", "back", "side", "rack_off"], # Додано дефолтні значення
            "paymentFormIds": [2, 10],
            "groupage": False,
            "photos": False,
            "showIgnore": False,
            "onlyActual": False,
            "onlyNew": False,
            "onlyRelevant": False,
            "onlyShippers": False,
            "onlyCarrier": False,
            "onlyExpedition": False,
            "onlyWithStavka": False,
            "distanceKmFrom": None,
            "distanceKmTo": None,
            "onlyPartners": False,
            "partnerGroups": [],
            "cargos": [],
            "cargoPackagingIds": [],
            "excludeCargos": [],
            "cargoBodyTypeProperties": [],
            "paymentCurrencyId": 4, # UAH (наприклад)
            "paymentValue": None,
            "paymentValueType": "TOTAL",
            "companyRefId": None,
            "companyName": None,
            "length1": None,
            "length2": None,
            "width1": None,
            "width2": None,
            "height1": None,
            "height2": None,
            "includeDocuments": [],
            "excludeDocuments": [],
            "adr": None,
        }

    def set_filter(self, key: str, value):
        """Оновити або додати фільтр."""
        # Для вкладених словників, ми будемо оновлювати їх безпосередньо в обробниках.
        # Для простих ключів - просто встановлюємо значення.
        self.filters[key] = value

    def load_data(self, retry_count: int = 1) -> Optional[dict]:
        """
        Завантажує дані за поточними фільтрами.
        Реалізовано механізм повторної спроби у разі 401 помилки.
        """
        payload = {
            "page": self.page,
            "size": self.page_size,
            "sortByCountryFirst": self.sort_by_country,
            "filter": self.filters,
        }
        self._update_headers_with_cookies()  # Переконаємося, що cookie актуальні перед запитом

        try:
            response = requests.post(self.url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                logger.warning(f"Отримано 401 Unauthorized під час завантаження даних. Спроба оновити cookie.")
                if retry_count > 0:
                    if _cookie_manager.refresh_lardi_cookies():
                        logger.info("Cookie успішно оновлено. Повторюємо запит.")
                        self._update_headers_with_cookies()  # Оновлюємо заголовки після оновлення cookie
                        return self.load_data(retry_count - 1)  # Повторюємо запит
                    else:
                        logger.error("Не вдалося оновити cookie. Не можу повторити запит.")
                        raise Exception(f"Error 401: Не вдалося авторизуватись, неможливо оновити cookie.")
                else:
                    logger.error(f"Не вдалося завантажити дані після повторної спроби. Максимальна кількість спроб.")
                    raise Exception(f"Error {response.status_code}: {response.text}")
            else:
                logger.error(f"Непередбачена HTTP помилка під час завантаження даних: {e}")
                raise Exception(f"Error {response.status_code}: {response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Помилка мережі при завантаженні даних: {e}")
            raise Exception(f"Network Error: {e}")
        except Exception as e:
            logger.error(f"Невідома помилка при завантаженні даних: {e}")
            raise Exception(f"Unknown Error: {e}")

    def update_cookie(self, new_cookie: str):
        """
        Цей метод тепер фактично не буде використовуватися для оновлення cookie,
        оскільки оновлення відбувається автоматично через CookieManager.
        Однак, я залишаю його для сумісності, якщо ви все ж захочете вручну встановити cookie.
        """
        logger.warning("Ручне оновлення cookie через update_cookie() тепер не рекомендується. Використовуйте автоматичне оновлення.")
        # Тут можна було б оновити _cookie_manager.cookies, але це менш безпечно,
        # ніж повний вхід. Якщо все ж потрібна ця функція, її варто переробити.
        # Для простоти, я просто оновлюю заголовки.
        self.headers["cookie"] = new_cookie


