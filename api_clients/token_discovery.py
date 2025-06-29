# api_clients/token_discovery.py

import requests
import time
import random
from typing import List, Dict, Optional
from config import API_URLS, DEFAULT_HEADERS, GMGN_HEADERS, RATE_LIMITS


class TokenDiscoveryError(Exception):
    """Custom exception for token discovery errors"""
    pass


class TokenDiscoveryClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        
        # Circuit breaker settings
        self.failure_count = 0
        self.circuit_open = False
        self.last_failure_time = 0
        self.circuit_timeout = RATE_LIMITS["circuit_breaker_timeout"]
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = RATE_LIMITS["min_request_interval"]
        
    def _wait_for_rate_limit(self):
        """Implement rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open"""
        if not self.circuit_open:
            return False
        
        if time.time() - self.last_failure_time > self.circuit_timeout:
            self.circuit_open = False
            self.failure_count = 0
            print("Circuit breaker reset - attempting requests again")
            return False
        
        return True
    
    def _handle_failure(self, error_msg: str):
        """Handle request failures for circuit breaker"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= RATE_LIMITS["circuit_breaker_threshold"]:
            self.circuit_open = True
            print(f"Circuit breaker OPEN after {self.failure_count} failures")
        
        raise TokenDiscoveryError(error_msg)
    
    def _make_request(self, url: str, params: Dict = None, custom_headers: Dict = None, retries: int = 3) -> Optional[Dict]:
        """Make HTTP request with retries and error handling"""
        if self._is_circuit_open():
            raise TokenDiscoveryError("Circuit breaker OPEN for make_request")
        
        self._wait_for_rate_limit()
        
        # Use custom headers if provided
        headers = custom_headers or DEFAULT_HEADERS
        
        for attempt in range(retries):
            try:
                if attempt > 0:
                    delay = random.uniform(0.5, 2.0) * (2 ** attempt)
                    print(f"_make_request attempt {attempt + 1} failed. Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                
                response = self.session.get(url, params=params, headers=headers, timeout=30)
                
                if response.status_code == 403:
                    error_msg = f"token_discovery client error: {response.status_code} Client Error: Forbidden for url: {url}"
                    if attempt == retries - 1:
                        self._handle_failure(error_msg)
                    continue
                
                if response.status_code == 404:
                    error_msg = f"token_discovery client error: {response.status_code} Client Error: Not Found for url: {url}"
                    if attempt == retries - 1:
                        self._handle_failure(error_msg)
                    continue
                
                if response.status_code == 503:
                    error_msg = f"API returned {response.status_code}"
                    print(error_msg)
                    if attempt == retries - 1:
                        self._handle_failure(error_msg)
                    continue
                
                response.raise_for_status()
                
                # Try to parse JSON
                try:
                    data = response.json()
                    # Reset failure count on success
                    self.failure_count = 0
                    return data
                except ValueError as e:
                    error_msg = f"token_discovery client error: {str(e)}"
                    if attempt == retries - 1:
                        self._handle_failure(error_msg)
                    continue
                
            except requests.exceptions.RequestException as e:
                error_msg = f"token_discovery client error: {str(e)}"
                if attempt == retries - 1:
                    self._handle_failure(error_msg)
        
        return None
    
    def discover_new_tokens(self) -> List[Dict]:
        """Discover new tokens from multiple sources with fallback options"""
        print("📡 Discovering new tokens...")
        all_tokens = []
        
        # Try multiple sources in order of preference
        sources = [
            self._get_dexscreener_tokens,
            self._get_jupiter_tokens,
            self._get_pumpfun_tokens,
            self._get_gmgn_tokens,
            self._get_mock_tokens
        ]
        
        for source_func in sources:
            try:
                tokens = source_func()
                if tokens:
                    all_tokens.extend(tokens)
                    print(f"✅ Got {len(tokens)} tokens from {source_func.__name__}")
                    break  # If we get tokens from one source, use those
            except Exception as e:
                print(f"❌ {source_func.__name__} failed: {e}")
                continue
        
        if not all_tokens:
            print("⚠️ All token sources failed, using mock data for testing")
            return self._get_mock_tokens()
        
        return all_tokens
    
    def _get_dexscreener_tokens(self) -> List[Dict]:
        """Get tokens from Dexscreener API using correct endpoint"""
        try:
            # Use the correct Dexscreener endpoint for Solana pairs
            url = API_URLS["dexscreener_pairs"]
            data = self._make_request(url)
            
            if data and 'pairs' in data:
                tokens = []
                for pair in data['pairs'][:10]:  # Limit to 10 most recent
                    base_token = pair.get('baseToken', {})
                    if base_token.get('address'):
                        tokens.append({
                            'address': base_token.get('address'),
                            'symbol': base_token.get('symbol'),
                            'name': base_token.get('name'),
                            'price': float(pair.get('priceUsd', 0)),
                            'volume': float(pair.get('volume', {}).get('h24', 0)),
                            'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                            'source': 'dexscreener'
                        })
                return tokens
        except Exception as e:
            raise TokenDiscoveryError(f"Dexscreener API error: {e}")
        return []
    
    def _get_jupiter_tokens(self) -> List[Dict]:
        """Get tokens from Jupiter token list"""
        try:
            url = API_URLS["jupiter_tokens"]
            data = self._make_request(url)
            
            if data and isinstance(data, list):
                tokens = []
                # Get some popular tokens from Jupiter list
                for token in data[:10]:  # First 10 tokens
                    tokens.append({
                        'address': token.get('address'),
                        'symbol': token.get('symbol'),
                        'name': token.get('name'),
                        'price': 0,  # Price not available from this endpoint
                        'volume': 0,
                        'market_cap': 0,
                        'source': 'jupiter'
                    })
                return tokens
        except Exception as e:
            raise TokenDiscoveryError(f"Jupiter API error: {e}")
        return []
    
    def _get_pumpfun_tokens(self) -> List[Dict]:
        """Get tokens from Pump.fun API"""
        try:
            url = API_URLS["pumpfun_new"]
            params = {
                'offset': 0,
                'limit': 10,
                'sort': 'created_timestamp',
                'order': 'DESC'
            }
            data = self._make_request(url, params)
            
            if data and isinstance(data, list):
                tokens = []
                for token in data[:10]:
                    total_supply = float(token.get('total_supply', 1))
                    market_cap = float(token.get('usd_market_cap', 0))
                    price = market_cap / total_supply if total_supply > 0 else 0
                    
                    tokens.append({
                        'address': token.get('mint'),
                        'symbol': token.get('symbol'),
                        'name': token.get('name'),
                        'price': price,
                        'volume': float(token.get('volume_24h', 0)),
                        'market_cap': market_cap,
                        'source': 'pumpfun'
                    })
                return tokens
        except Exception as e:
            raise TokenDiscoveryError(f"Pump.fun API error: {e}")
        return []
    
    def _get_gmgn_tokens(self) -> List[Dict]:
        """Get tokens from GMGN API using correct endpoints"""
        try:
            # Try the new pairs endpoint first
            url = API_URLS["gmgn_new_pairs"]
            data = self._make_request(url, custom_headers=GMGN_HEADERS)
            
            if data and 'data' in data:
                tokens = []
                token_list = data['data']
                if isinstance(token_list, list):
                    for token in token_list[:10]:
                        tokens.append({
                            'address': token.get('address') or token.get('mint'),
                            'symbol': token.get('symbol'),
                            'name': token.get('name'),
                            'price': float(token.get('price', 0)),
                            'volume': float(token.get('volume_24h', 0)),
                            'market_cap': float(token.get('market_cap', 0)),
                            'source': 'gmgn'
                        })
                    return tokens
        except Exception as e:
            raise TokenDiscoveryError(f"GMGN API error: {e}")
        return []
    
    def _get_mock_tokens(self) -> List[Dict]:
        """Return mock tokens for testing when all APIs fail"""
        return [
            {
                'address': 'So11111111111111111111111111111111111112',
                'symbol': 'SOL',
                'name': 'Solana',
                'price': 100.50,
                'volume': 50000000,
                'market_cap': 40000000000,
                'source': 'mock'
            },
            {
                'address': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                'symbol': 'USDC',
                'name': 'USD Coin',
                'price': 1.00,
                'volume': 100000000,
                'market_cap': 25000000000,
                'source': 'mock'
            },
            {
                'address': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
                'symbol': 'USDT',
                'name': 'Tether USD',
                'price': 1.00,
                'volume': 80000000,
                'market_cap': 95000000000,
                'source': 'mock'
            }
        ]