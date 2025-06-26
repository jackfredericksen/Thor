# api_clients/pumpfun.py

import requests
from config import API_KEYS, API_URLS


class PumpFunClient:
    def __init__(self):
        self.base_url = API_URLS["pumpfun"]
        self.headers = {"Authorization": f"Bearer {API_KEYS['pumpfun']}"}

    def fetch_new_tokens(self):
        resp = requests.get(f"{self.base_url}/new", headers=self.headers)
        resp.raise_for_status()
        return resp.json()
