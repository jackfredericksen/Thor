# api_clients/gmgn.py

import requests
from config import API_KEYS, API_URLS


class GMGNClient:
    def __init__(self):
        self.base_url = API_URLS["gmgn"]
        self.api_key = API_KEYS["gmgn"]
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def place_order(self, token_address, side, quantity, order_type="market", limit_price=None, slippage=0.01):
        payload = {
            "token_address": token_address,
            "side": side,
            "quantity": quantity,
            "type": order_type,
            "slippage": slippage,
        }
        if order_type == "limit":
            payload["limit_price"] = limit_price
        resp = self.session.post(f"{self.base_url}/orders", json=payload)
        resp.raise_for_status()
        return resp.json()

    def check_order_status(self, order_id):
        resp = self.session.get(f"{self.base_url}/orders/{order_id}")
        resp.raise_for_status()
        return resp.json()

    def authenticate_telegram(self, telegram_token):
        # Implement authentication flow if needed
        pass

    def authenticate_wallet(self, wallet_address):
        # Implement wallet login flow if needed
        pass

    def fetch_smart_trades(self, min_value=1000):
        resp = self.session.get(f"{self.base_url}/smartmoney/trades", params={"min_value": min_value})
        resp.raise_for_status()
        return resp.json()

    def fetch_wallet_tags(self, wallet_address):
        resp = self.session.get(f"{self.base_url}/wallets/{wallet_address}/tags")
        resp.raise_for_status()
        return resp.json()
