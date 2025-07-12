from functools import wraps

import requests
import logging
from datetime import datetime, timezone

from asgiref.sync import sync_to_async
from dotenv import load_dotenv

from modules.cookie_manager import CookieManager
from typing import Optional, Dict, Any, List

from modules.utils import user_filter_to_dict

load_dotenv()

logger = logging.getLogger(__name__)

_cookie_manager = CookieManager()


def lardi_api_retry_on_401(func):
    """
    Декоратор для автоматичної обробки 401 помилок та повторної спроби запиту
    після оновлення cookie.
    """

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        max_retries = 1  # Одна спроба після 401
        for attempt in range(max_retries + 1):
            try:
                # Оновлюємо заголовки перед кожною спробою
                self._update_headers_with_cookies()
                # Перетворюємо синхронний виклик на асинхронний, якщо функція сама по собі синхронна
                if not hasattr(func, '__wrapped__') and not hasattr(func,
                                                                    '__name__') and func.__module__ == 'builtins':  # heuristic for detecting if it's a plain function not wrapped by sync_to_async
                    return await sync_to_async(func)(self, *args, **kwargs)
                else:
                    return await func(self, *args, **kwargs)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 401 and attempt < max_retries:
                    logger.warning("Отримано 401 Unauthorized. Спроба оновити cookie та повторити запит...")
                    # refresh_lardi_cookies є синхронним, тому обгортаємо його
                    refresh_success = await sync_to_async(_cookie_manager.refresh_lardi_cookies)()
                    if refresh_success:
                        logger.info("Cookie успішно оновлено. Повторюємо запит.")
                        # Важливо: _update_headers_with_cookies() буде викликано на початку наступної ітерації
                        continue  # Повторюємо цикл
                    else:
                        logger.error("Не вдалося оновити cookie. Відмова від повторної спроби.")
                        raise  # Прокидаємо оригінальну помилку 401, якщо оновлення не вдалося
                else:
                    logger.error(f"HTTP помилка {e.response.status_code} після {attempt + 1} спроб: {e}")
                    raise  # Прокидаємо інші HTTP помилки або 401 після вичерпання спроб
            except requests.exceptions.RequestException as e:
                logger.error(f"Мережева помилка після {attempt + 1} спроб: {e}")
                raise  # Прокидаємо мережеві помилки
            except Exception as e:
                logger.error(f"Невідома помилка після {attempt + 1} спроб: {e}")
                raise  # Прокидаємо інші невідомі помилки
        # Цей рядок ніколи не повинен бути досягнутий, якщо помилка прокинута,
        # але на випадок, якщо щось піде не так і цикл завершиться без повернення.
        logger.error("Неочікуване завершення декоратора без повернення або прокидання помилки.")
        raise Exception("Невідома помилка в API запиті після всіх спроб.")

    return wrapper


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
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0",
            "referer": "https://lardi-trans.com/log/search/gruz/",
            "origin": "https://lardi-trans.com",
            "cookie": _cookie_manager.get_cookie_string()  # Беремо cookie з менеджера
        }

    @lardi_api_retry_on_401
    async def get_offer(self, offer_id: int) -> Optional[dict]:
        """Отримати інформацію про вантаж за ID."""
        url = f"{self.base_url}{offer_id}/awaiting/?currentId={offer_id}"
        response = await sync_to_async(requests.get)(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()


class LardiClient:
    """
    Клієнт для пошуку вантажів та управління фільтрами на Lardi-Trans.
    """

    def __init__(self):
        self.url = "https://lardi-trans.com/webapi/proposal/search/gruz/"
        self._update_headers_with_cookies()  # Оновлюємо заголовки при ініціалізації
        self.page = 1
        self.page_size = 20  # 20 це стандарт для Lardi
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
            "mass1": None,
            "mass2": None,
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
            "paymentCurrencyId": 4,  # UAH
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
        self.filters[key] = value

    @lardi_api_retry_on_401
    async def load_data(self) -> Optional[dict]:
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

        response = await sync_to_async(requests.post)(self.url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()

    @lardi_api_retry_on_401
    async def get_proposals(self, filters) -> Optional[dict]:
        """
        Завантажує дані за фільтрами користувача.
        """
        payload = {
            "page": self.page,
            "size": self.page_size,
            "sortByCountryFirst": self.sort_by_country,
            "filter": filters,
        }

        response = await sync_to_async(requests.post)(self.url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()

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

    @lardi_api_retry_on_401
    async def get_offers(self, user_telegram_id: int) -> Optional[List[Dict[str, Any]]]:
        """
        Асинхронно отримує список вантажів з Lardi-Trans API, використовуючи фільтри
        з бази даних для конкретного користувача, або дефолтні.
        """
        lardi_filter_obj = await self._get_filter_object_for_user(user_telegram_id)
        if lardi_filter_obj:
            payload = user_filter_to_dict(lardi_filter_obj)
            logger.info(f"Використання фільтрів з БД для користувача {user_telegram_id}.")
        else:
            payload = self.default_filters()
            logger.info(f"Фільтри не знайдено для користувача {user_telegram_id}. Використано фільтри за замовчуванням.")

        response = await sync_to_async(requests.post)(self.url, headers=self.headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("proposals", [])

    @lardi_api_retry_on_401
    async def get_all_offers(self, user_telegram_id: int) -> list:
        """
        Асинхронно отримує всі вантажі з Lardi-Trans API, використовуючи фільтри
        з бази даних для конкретного користувача, або дефолтні.
        """
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

            try:
                response = await sync_to_async(requests.post)(self.url, headers=self.headers, json=payload)
                response.raise_for_status()
                data = response.json()
                proposals = data.get("result", {}).get("proposals", [])
                logger.info(f"LardiAPI - INFO - Сторінка {page}: отримано {len(proposals)} вантажів")
                if not isinstance(proposals, list):
                    logger.warning(f"LardiAPI - WARNING - proposals не є списком: {proposals}")
                    proposals = []
                all_proposals.extend([p for p in proposals if isinstance(p, dict)])
                total_pages += 1
                if not proposals or len(proposals) < page_size:
                    break
                page += 1
            except requests.exceptions.HTTPError as e:
                logger.error(f"LardiAPI - ERROR - {e.response.status_code}: {e}")
                break
            except requests.exceptions.RequestException as e:
                logger.error(f"LardiAPI - ERROR - {e}")
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
            created_at_str = offer.get('dateCreate')
            if created_at_str:
                try:
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

                    # Приведення last_notification_time до UTC, якщо воно не має tzinfo
                    if last_notification_time.tzinfo is None:
                        last_notification_time = last_notification_time.replace(tzinfo=timezone.utc)
                    if dt_object.tzinfo is not None and dt_object.tzinfo.utcoffset(dt_object) is not None:
                        dt_object = dt_object.astimezone(timezone.utc)
                    else:
                        dt_object = dt_object.replace(tzinfo=timezone.utc)

                    if dt_object > last_notification_time:
                        new_offers.append(offer)
                except ValueError as e:
                    logger.error(f"Помилка парсингу дати '{created_at_str}: {e}'")
            else:
                logger.warning(f"Вантаж {offer.get('id')} не має поля 'createDate'.")

        return new_offers


class LardiGeoClient:

    def __init__(self):
        self.url = "https://lardi-trans.com/webapi/geo/region-area-town/"
        self._update_headers_with_cookies()

    def _update_headers_with_cookies(self):
        """Оновлює заголовки HTTP з поточними cookie від CookieManager."""
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0",
            "referer": "https://lardi-trans.com/log/search/gruz/wf2i640-4iwt2i640-",
            "origin": "https://lardi-trans.com",
            "cookie": _cookie_manager.get_cookie_string()
        }

    @lardi_api_retry_on_401
    async def get_geo_data(self, query: str, sign: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Отримує Географічні дані (регіон, місто) з LardiTrans API
        :param query: Пошуковий запит (Назва міста або регіону).
        :param sign: Необов'язковий параметр для фільтрації за ознакою (наприклад, "UA").
        :return: Список словників з географічним даними.
        """
        params = {
            "query": query,
            'sign': sign if sign else "UA"
        }
        try:
            response = requests.get(self.url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Таймаут запиту при отриманні геоданих для запиту '{query}.'")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Помилка при запиті геоданих для запиту '{query}.'\n Exception: {e}")
            return []


lardi_notification_client = LardiNotificationClient()
