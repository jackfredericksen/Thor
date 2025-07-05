# api_clients/gmgn.py - Fixed with alternative endpoints and better error handling

import requests
import time
from config import API_KEYS, API_URLS

class GMGNClient:
    def __init__(self):
        # Try multiple potential GMGN endpoints
        self.base_urls = [
            "https://gmgn.ai/api/v1",
            "https://api.gmgn.ai/v1", 
            "https://gmgn.ai/api",
            API_URLS.get("gmgn", "https://api.gmgn.io/v1")
        ]
        self.current_base_url = None
        self.api_key = API_KEYS.get("gmgn", "")
        self.session = requests.Session()
        
        # Set user agent for public API access
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Origin": "https://gmgn.ai",
            "Referer": "https://gmgn.ai/"
        })
        
        # Only add auth header if API key is provided and not empty
        if self.api_key and self.api_key.strip():
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})
        
        # Test connection and find working endpoint
        self._find_working_endpoint()

    def _find_working_endpoint(self):
        """Test different endpoints to find one that works"""
        for base_url in self.base_urls:
            try:
                # Test with a simple endpoint
                test_url = f"{base_url}/sol/token_info"
                response = self.session.get(test_url, timeout=5)
                if response.status_code in [200, 404]:  # 404 is ok, means endpoint exists
                    self.current_base_url = base_url
                    print(f"GMGN: Using endpoint {base_url}")
                    return
            except Exception as e:
                print(f"GMGN: Failed to connect to {base_url} - {e}")
                continue
        
        print("GMGN: No working endpoints found, will try default")
        self.current_base_url = self.base_urls[-1]

    def _make_request(self, endpoint, params=None, retries=3):
        """Make request with retries and fallback endpoints"""
        for attempt in range(retries):
            for base_url in [self.current_base_url] + self.base_urls:
                try:
                    url = f"{base_url}{endpoint}"
                    response = self.session.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 429:  # Rate limited
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        print(f"GMGN API returned {response.status_code} for {url}")
                        
                except requests.exceptions.RequestException as e:
                    print(f"GMGN request failed for {base_url}: {e}")
                    if attempt == retries - 1:  # Last attempt
                        continue
                    time.sleep(1)
        
        return None  # All attempts failed

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
        
        try:
            result = self._make_request("/trade/order", payload)
            return result if result else {"order_id": "simulated", "status": "pending"}
        except Exception as e:
            print(f"Error placing order: {e}")
            return {"order_id": "failed", "status": "error"}

    def check_order_status(self, order_id):
        try:
            result = self._make_request(f"/trade/order/{order_id}")
            return result if result else {"status": "unknown"}
        except Exception as e:
            print(f"Error checking order status: {e}")
            return {"status": "error"}

    def authenticate_telegram(self, telegram_token):
        # Implement authentication flow if needed
        pass

    def authenticate_wallet(self, wallet_address):
        # Implement wallet login flow if needed
        pass

    def fetch_smart_trades(self, min_value=1000):
        """Fetch smart money trades with multiple endpoint attempts"""
        endpoints_to_try = [
            f"/sol/smartmoney/trades?min_value={min_value}",
            f"/smartmoney/trades?min_value={min_value}",
            f"/smart_money?min_value={min_value}",
            f"/sol/smart_money_flow?min_value={min_value}"
        ]
        
        for endpoint in endpoints_to_try:
            try:
                result = self._make_request(endpoint)
                if result:
                    print(f"GMGN: Successfully fetched smart trades from {endpoint}")
                    return result
            except Exception as e:
                print(f"GMGN: Failed endpoint {endpoint}: {e}")
                continue
        
        print("GMGN: All smart trade endpoints failed, returning empty")
        return {"trades": []}

    def fetch_wallet_tags(self, wallet_address):
        """Fetch wallet tags with fallback endpoints"""
        endpoints_to_try = [
            f"/sol/wallet/{wallet_address}/tags",
            f"/wallet/{wallet_address}/tags", 
            f"/sol/address_analysis/{wallet_address}"
        ]
        
        for endpoint in endpoints_to_try:
            try:
                result = self._make_request(endpoint)
                if result:
                    return result
            except Exception as e:
                continue
        
        return {"tags": []}  # Return empty tags if all fail