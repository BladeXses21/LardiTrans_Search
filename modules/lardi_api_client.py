import requests
import logging
from datetime import datetime, timezone, timedelta

from asgiref.sync import sync_to_async
from dotenv import load_dotenv
from modules.cookie_manager import CookieManager
from typing import Optional, Dict, Any, List

from modules.utils import user_filter_to_dict

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
        self._update_headers_with_cookies()  # Оновлюємо заголовки при ініціалізації

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
        """Отримати інформацію про вантаж за ID."""
        url = f"{self.base_url}{offer_id}"
        self._update_headers_with_cookies()  # Оновлюємо куки перед кожним запитом

        for attempt in range(retry_count + 1):
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()  # Піднімає HTTPError для поганих відповідей (4xx або 5xx)
                return response.json()
            except requests.exceptions.HTTPError as e:
                if response.status_code == 403:
                    logger.warning(f"403 Forbidden for offer {offer_id}. Cookie might be expired. Attempting to refresh...")
                    if _cookie_manager.refresh_lardi_cookies():
                        self._update_headers_with_cookies()
                        continue  # Повторюємо запит з новими куками
                    else:
                        logger.error(f"Failed to refresh cookie for offer {offer_id}.")
                        return None
                elif response.status_code == 404:
                    logger.info(f"Offer {offer_id} not found (404).")
                    return None
                else:
                    logger.error(f"HTTP error {response.status_code} fetching offer {offer_id}: {e}")
                    return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error fetching offer {offer_id}: {e}")
                return None
            except Exception as e:
                logger.error(f"Unknown error fetching offer {offer_id}: {e}")
                return None
        return None  # Якщо всі спроби вичерпано


class LardiClient:
    """
    Клієнт для пошуку вантажів та управління фільтрами на Lardi-Trans.
    """

    def __init__(self):
        self.url = "https://lardi-trans.com/webapi/proposal/search/gruz/"
        self._update_headers_with_cookies()  # Оновлюємо заголовки при ініціалізації
        self.page = 1
        self.page_size = 20  # 20, так як це стандарт для Lardi
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
            "cookie": _cookie_manager.get_cookie_string(),
        }

    def default_filters(self) -> dict:
        """Повертає фільтри за замовчуванням."""
        return {
            "directionFrom": {"directionRows": [{"countrySign": "UA"}]},
            "directionTo": {"directionRows": [{"countrySign": "UA"}]},
            "mass1": None,  # Додано, щоб можна було встановлювати через інтерфейс
            "mass2": None,  # Додано, щоб можна було встановлювати через інтерфейс
            "volume1": None,
            "volume2": None,
            "dateFromISO": None,
            "dateToISO": None,
            "bodyTypeIds": [],
            "loadTypes": [],
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
            "paymentCurrencyId": 4,  # UAH (наприклад)
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

    def load_data(self, retry_count: int = 2) -> Optional[dict]:
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

    def get_proposals(self, filters, retry_count: int = 3) -> Optional[dict]:
        """
        Завантажує дані за фільтрами користувача.
        """

        payload = {
            "page": self.page,
            "size": self.page_size,
            "sortByCountryFirst": self.sort_by_country,
            "filter": filters,
        }

        self._update_headers_with_cookies()

        try:
            print(payload)
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
                        return self.get_proposals(retry_count - 1)  # Повторюємо запит
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

    @sync_to_async
    def _get_filter_object_for_user(self, user_id: int):
        """
        Допоміжна функція для асинхронного отримання LardiSearchFilter.
        """
        from users.models import UserProfile
        from filters.models import LardiSearchFilter

        try:
            user_profile = UserProfile.objects.get(telegram_id=user_id)
            return LardiSearchFilter.objects.get(user=user_profile)
        except (UserProfile.DoesNotExist, LardiSearchFilter.DoesNotExist):
            logger.warning(f"LardiSearchFilter not found for user {user_id}. Using default filters.")
            return None

    async def get_offers(self, user_telegram_id: int) -> Optional[List[Dict[str, Any]]]:
        """
        Асинхронно отримує список вантажів з Lardi-Trans API, використовуючи фільтри
        з бази даних для конкретного користувача, або дефолтні.
        """
        self._update_headers_with_cookies()

        lardi_filter_obj = await self._get_filter_object_for_user(user_telegram_id)
        if lardi_filter_obj:
            payload = user_filter_to_dict(lardi_filter_obj)
            logger.info(f"Використання фільтрів з БД для користувача {user_telegram_id}.")
        else:
            payload = self.default_filters()
            logger.info(f"Фільтри не знайдено для користувача {user_telegram_id}. Використано фільтри за замовчуванням.")

        try:
            response = requests.post(self.url, headers=self.headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("proposals")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request Error: {e}")
            raise Exception(f"Request Error: {e}")
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

    async def get_all_offers(self, user_telegram_id: int) -> list:
        """
        Асинхронно отримує всі вантажі з Lardi-Trans API, використовуючи фільтри
        з бази даних для конкретного користувача, або дефолтні.
        """
        self._update_headers_with_cookies()

        lardi_filter_obj = await self._get_filter_object_for_user(user_telegram_id)
        if lardi_filter_obj:
            filters = user_filter_to_dict(lardi_filter_obj)
            logger.info(f"Використання фільтрів з БД для користувача {user_telegram_id}.")
        else:
            filters = self.default_filters()
            logger.info(f"Фільтри не знайдено для користувача {user_telegram_id}. Використано фільтри за замовчуванням.")

        all_proposals = []
        page = 1
        page_size = 20
        total_pages = 0

        for i in range(0, 100):
            payload = {
                "page": page,
                "size": page_size,
                "sortByCountryFirst": self.sort_by_country,
                "filter": filters,
            }
            self._update_headers_with_cookies()

            try:
                response = requests.post(self.url, headers=self.headers, json=payload)
                # logger.info(f"LardiAPI - INFO - RESPONSE {response.json()}")
                response.raise_for_status()
                data = response.json()
                proposals = data.get("result", {}).get("proposals", [])
                logger.info(f"LardiAPI - INFO - Сторінка {page}: отримано {len(proposals)} вантажів")
                logger.info(f"LardiAPI - INFO - Тип proposals: {type(proposals)} на сторінці {page}")
                if not isinstance(proposals, list):
                    logger.warning(f"LardiAPI - WARNING - proposals не є списком: {proposals}")
                    proposals = []
                all_proposals.extend([p for p in proposals if isinstance(p, dict)])
                total_pages += 1
                if not proposals or len(proposals) < page_size:
                    break
                page += 1
            except Exception as e:
                logger.error(f"Помилка при отриманні сторінки {page} вантажів: {e}")
                break
        logger.info(f"LardiAPI - INFO - Завершено. Всього сторінок: {total_pages}. Всього вантажів: {len(all_proposals)}")
        return all_proposals


class LardiNotificationClient(LardiClient):
    """
    Клієнт для Lardi-Trans API, спеціалізований на пошуку нових вантажів для сповіщень.
    """

    async def get_new_offers(self, user_telegram_id: int, last_notification_time: datetime) -> List[Dict[str, Any]]:
        """
        Отримує список нових вантажів, створених після last_notification_time,
        з використанням фільтрів користувача.
        """
        all_offers = await self.get_all_offers(user_telegram_id)
        if not all_offers:
            return []

        new_offers = []
        for offer in all_offers:
            if not isinstance(offer, dict):
                logger.warning(f"OFFER - WARNING - Пропущено некоректний запис (не dict): {offer}")
                continue
            logger.info(f"OFFER - INFO - {offer}")
            created_at_str = offer.get('dateCreate')
            if created_at_str:
                try:
                    # Розбираємо дату з урахуванням мілісекунд та часового поясу
                    # Приклад: "2024-06-24T10:30:00.123+03:00" або "2024-06-24T10:30:00"
                    if '.' in created_at_str and '+' in created_at_str:
                        dt_object = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%S.%f%z')
                    elif '.' in created_at_str:
                        dt_object = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%S.%f')
                        dt_object = dt_object.replace(tzinfo=timezone.utc)  # Припускаємо UTC, якщо немає зони
                    elif '+' in created_at_str:
                        dt_object = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%S%z')
                    else:
                        dt_object = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%S')
                        dt_object = dt_object.replace(tzinfo=timezone.utc)  # Припускаємо UTC, якщо немає зони

                    if last_notification_time.tzinfo is None:
                        last_notification_time = last_notification_time.replace(tzinfo=timezone.utc)

                    if dt_object > last_notification_time:
                        new_offers.append(offer)
                except ValueError as e:
                    logger.error(f"Помилка парсингу дати '{created_at_str}: {e}'")
            else:
                logger.warning(f"Вантаж {offer.get('id')} не має поля 'createDate'.")

        return new_offers


lardi_notification_client = LardiNotificationClient()
