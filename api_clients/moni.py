# api_clients/moni.py

import requests
from config import API_KEYS, API_URLS


class MoniClient:
    def __init__(self):
        self.base_url = API_URLS["moni"]
        self.headers = {"Authorization": f"Bearer {API_KEYS['moni']}"}

    def get_sentiment(self, token_address):
        resp = requests.get(f"{self.base_url}/{token_address}/sentiment", headers=self.headers)
        resp.raise_for_status()
        return resp.json()
