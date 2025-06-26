# api_clients/bubblemaps.py

import requests
from config import API_KEYS, API_URLS


class BubblemapsClient:
    def __init__(self):
        self.base_url = API_URLS["bubblemaps"]
        self.headers = {"Authorization": f"Bearer {API_KEYS['bubblemaps']}"}

    def analyze_wallets(self, token_address):
        resp = requests.get(f"{self.base_url}/{token_address}", headers=self.headers)
        resp.raise_for_status()
        return resp.json()
