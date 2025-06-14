import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()


class LardiOfferClient:
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
            raise Exception(f"❌ Error {response.status_code}: {response.text}")

    def print_offer_pretty(self, data: dict):
        """Красивий вивід отриманих даних."""
        print(f"\n📄 Деталі вантажу\n{'=' * 40}")
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                print(f"{key}: {value}")
        print("=" * 40)

client = LardiOfferClient()
offer_id = 233984329976
data = client.get_offer(offer_id)
client.print_offer_pretty(data.get('cargo', {}))
