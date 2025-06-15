import os
import requests
import json
from dotenv import load_dotenv

# Завантажуємо змінні середовища
load_dotenv()


class LardiOfferClient:
    """
    Клієнт для отримання інформації про конкретний вантаж з Lardi-Trans.
    """
    def __init__(self):
        self.base_url = "https://lardi-trans.com/webapi/proposal/offer/gruz/"
        self.cookie = os.getenv("LARDI_COOKIE", "")
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "user-agent": "Mozilla/5.0",
            "cookie": self.cookie,
            "referer": "https://lardi-trans.com/log/search/gruz/",
            "origin": "https://lardi-trans.com"
        }

    def get_offer(self, offer_id: int):
        """Отримати інформацію про вантаж за його ID."""
        url = f"{self.base_url}{offer_id}/awaiting/?currentId={offer_id}"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json()
        else:
            # Змінено для кращого обробника помилок в боті
            raise Exception(f"Error {response.status_code}: {response.text}")


class LardiClient:
    """
    Клієнт для пошуку вантажів та управління фільтрами на Lardi-Trans.
    """
    def __init__(self):
        self.url = "https://lardi-trans.com/webapi/proposal/search/gruz/"
        self.cookie = os.getenv("LARDI_COOKIE", "")
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "origin": "https://lardi-trans.com",
            "referer": "https://lardi-trans.com/log/search/gruz/",
            "user-agent": "Mozilla/5.0",
            "cookie": self.cookie,
        }
        self.page = 1
        self.page_size = 20
        self.sort_by_country = False
        self.filters = self.default_filters()

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

    def load_data(self):
        """Завантажує дані за поточними фільтрами."""
        payload = {
            "page": self.page,
            "size": self.page_size,
            "sortByCountryFirst": self.sort_by_country,
            "filter": self.filters,
        }
        response = requests.post(self.url, headers=self.headers, json=payload)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error {response.status_code}: {response.text}")

    def update_cookie(self, new_cookie: str):
        """Оновлення cookie у файлі .env"""
        self.cookie = new_cookie
        self.headers["cookie"] = new_cookie
        os.environ["LARDI_COOKIE"] = new_cookie # Оновлюємо змінну середовища


