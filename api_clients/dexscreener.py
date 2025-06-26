# api_clients/dexscreener.py

import requests
from config import API_KEYS, API_URLS


class DexscreenerClient:
    def __init__(self):
        self.base_url = API_URLS["dexscreener"]

    def fetch_tokens(self):
        # Example: get top tokens from Dexscreener
        resp = requests.get(self.base_url)
        resp.raise_for_status()
        return resp.json()

    def fetch_token_details(self, token_address):
        # You can add detailed token data fetching here if available
        pass
