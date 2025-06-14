import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

class LardiClient:
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
        return {
            "directionFrom": {"directionRows": [{"countrySign": "UA"}]},
            "directionTo": {"directionRows": [{"countrySign": "UA"}]},
            "bodyTypeIds": [34],
            "loadTypes": ["top", "back", "side", "rack_off"],
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
        }

    def set_filter(self, key, value):
        """Оновити або додати фільтр."""
        self.filters[key] = value

    def load_data(self):
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

    def update_cookie(self, new_cookie):
        """Оновлення cookie у файлі .env"""
        self.cookie = new_cookie
        self.headers["cookie"] = new_cookie
        with open(".env", "w") as f:
            f.write(f"LARDI_COOKIE={new_cookie}\n")
        print("✅ Cookie оновлено та збережено у .env")

    def show_filters(self):
        print(json.dumps(self.filters, indent=2, ensure_ascii=False))

    def print_results_pretty(self, data: dict):
        results = data.get("result", {}).get("proposals", {})

        if not results:
            print("🔍 Нічого не знайдено.")
            return

        for i, item in enumerate(results, 1):
            print(f"\n📦 Результат #{i}")
            print("-" * 40)
            for key, value in item.items():
                if isinstance(value, (dict, list)):
                    short_value = json.dumps(value, ensure_ascii=False)
                    print(f"{key}: {short_value[:120]}{'...' if len(short_value) > 120 else ''}")
                else:
                    print(f"{key}: {value}")
            print("-" * 40)

client = LardiClient()
data = client.load_data()

for key, value in data.items():
    print(key, value)

client.print_results_pretty(data)
