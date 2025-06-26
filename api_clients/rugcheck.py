# api_clients/rugcheck.py

import requests
from config import API_KEYS, API_URLS


class RugcheckClient:
    def __init__(self):
        self.base_url = API_URLS["rugcheck"]
        self.headers = {"Authorization": f"Bearer {API_KEYS['rugcheck']}"}

    def audit_token(self, token_address):
        resp = requests.post(self.base_url, json={"contract": token_address}, headers=self.headers)
        resp.raise_for_status()
        return resp.json()
