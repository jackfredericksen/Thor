# api_clients/token_discovery.py

import requests
import time
import random
from typing import List, Dict, Optional


class TokenDiscoveryError(Exception):
    """Custom exception for token discovery errors"""
    pass


class TokenDiscoveryClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 2  # seconds between requests
        
    def _wait_for_rate_limit(self):
        """Implement rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _make_request(self, url: str, params: Dict = None, retries: int = 2) -> Optional[Dict]:
        """Make HTTP request with retries"""
        self._wait_for_rate_limit()
        
        for attempt in range(retries):
            try:
                if attempt > 0:
                    delay = 1 + random.uniform(0, 1)
                    print(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                
                response = self.session.get(url, params=params, timeout=15)
                
                if response.status_code != 200:
                    print(f"API returned {response.status_code} for {url}")
                    if attempt == retries - 1:
                        raise TokenDiscoveryError(f"API returned {response.status_code}")
                    continue
                
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    raise TokenDiscoveryError(f"Request failed: {str(e)}")
        
        return None
    
    def discover_new_tokens(self) -> List[Dict]:
        """Discover new tokens using only working APIs"""
        print("📡 Discovering new tokens...")
        all_tokens = []
        
        # Try working sources in order of preference
        sources = [
            ("Jupiter Popular Tokens", self._get_jupiter_popular_tokens),
            ("Dexscreener Search", self._get_dexscreener_search_tokens),
            ("CoinGecko Trending", self._get_coingecko_trending),
        ]
        
        for source_name, source_func in sources:
            try:
                print(f"🔍 Trying {source_name}...")
                tokens = source_func()
                if tokens:
                    print(f"✅ Got {len(tokens)} tokens from {source_name}")
                    all_tokens.extend(tokens)
                    # Get tokens from multiple sources
                    if len(all_tokens) >= 10:  # Enough tokens
                        break
            except Exception as e:
                print(f"❌ {source_name} failed: {e}")
                continue
        
        # Remove duplicates based on address
        seen_addresses = set()
        unique_tokens = []
        for token in all_tokens:
            addr = token.get('address')
            if addr and addr not in seen_addresses:
                seen_addresses.add(addr)
                unique_tokens.append(token)
        
        if not unique_tokens:
            print("⚠️ All sources failed, using mock data")
            return self._get_mock_tokens()
        
        return unique_tokens[:15]  # Return top 15 tokens
    
    def _get_jupiter_popular_tokens(self) -> List[Dict]:
        """Get popular tokens from Jupiter token list"""
        try:
            url = "https://token.jup.ag/strict"
            data = self._make_request(url)
            
            if not data or not isinstance(data, list):
                raise TokenDiscoveryError("Invalid Jupiter response")
            
            # Filter for Solana tokens with good metadata
            tokens = []
            for token in data:
                # Skip if missing required fields
                if not all([token.get('address'), token.get('symbol'), token.get('name')]):
                    continue
                
                # Skip stablecoins and wrapped tokens for trading
                symbol = token.get('symbol', '').upper()
                if any(skip in symbol for skip in ['USD', 'USDT', 'USDC', 'WRAPPED', 'W']):
                    continue
                
                # Skip tokens with very low decimals (likely NFTs or weird tokens)
                decimals = token.get('decimals', 0)
                if decimals < 6:
                    continue
                
                tokens.append({
                    'address': token.get('address'),
                    'symbol': token.get('symbol'),
                    'name': token.get('name'),
                    'decimals': decimals,
                    'price': 0,  # No price data from this endpoint
                    'volume': 0,
                    'source': 'jupiter'
                })
                
                if len(tokens) >= 10:  # Limit to 10 tokens
                    break
            
            return tokens
            
        except Exception as e:
            raise TokenDiscoveryError(f"Jupiter API error: {e}")
    
    def _get_dexscreener_search_tokens(self) -> List[Dict]:
        """Get tokens from Dexscreener search (this works!)"""
        try:
            # Search for popular terms to find active tokens
            search_terms = ['SOL', 'BONK', 'RAY', 'ORCA']
            all_tokens = []
            
            for term in search_terms:
                url = "https://api.dexscreener.com/latest/dex/search"
                params = {'q': term}
                data = self._make_request(url, params)
                
                if data and 'pairs' in data:
                    pairs = data['pairs'][:5]  # Take first 5 pairs per search
                    
                    for pair in pairs:
                        base_token = pair.get('baseToken', {})
                        if base_token.get('address'):
                            # Get volume and price data
                            volume_24h = float(pair.get('volume', {}).get('h24', 0))
                            price_usd = float(pair.get('priceUsd', 0))
                            liquidity = float(pair.get('liquidity', {}).get('usd', 0))
                            
                            # Only include tokens with decent volume and liquidity
                            if volume_24h > 1000 and liquidity > 5000:
                                all_tokens.append({
                                    'address': base_token.get('address'),
                                    'symbol': base_token.get('symbol'),
                                    'name': base_token.get('name'),
                                    'price': price_usd,
                                    'volume': volume_24h,
                                    'liquidity': liquidity,
                                    'source': 'dexscreener'
                                })
                
                time.sleep(0.5)  # Small delay between searches
            
            # Sort by volume and return top tokens
            all_tokens.sort(key=lambda x: x['volume'], reverse=True)
            return all_tokens[:8]  # Top 8 by volume
            
        except Exception as e:
            raise TokenDiscoveryError(f"Dexscreener search error: {e}")
    
    def _get_coingecko_trending(self) -> List[Dict]:
        """Get trending tokens from CoinGecko"""
        try:
            url = "https://api.coingecko.com/api/v3/search/trending"
            data = self._make_request(url)
            
            if not data or 'coins' not in data:
                raise TokenDiscoveryError("Invalid CoinGecko response")
            
            tokens = []
            for coin_data in data['coins'][:5]:  # Top 5 trending
                coin = coin_data.get('item', {})
                
                # CoinGecko doesn't always have Solana addresses, so we'll use what we can
                tokens.append({
                    'address': f"coingecko_{coin.get('id', 'unknown')}",  # Placeholder address
                    'symbol': coin.get('symbol'),
                    'name': coin.get('name'),
                    'price': 0,  # Would need separate price API call
                    'volume': 0,
                    'market_cap_rank': coin.get('market_cap_rank', 999),
                    'source': 'coingecko_trending'
                })
            
            return tokens
            
        except Exception as e:
            raise TokenDiscoveryError(f"CoinGecko trending error: {e}")
    
    def _get_mock_tokens(self) -> List[Dict]:
        """Return high-quality mock tokens for testing"""
        return [
            {
                'address': 'So11111111111111111111111111111111111112',
                'symbol': 'SOL',
                'name': 'Solana',
                'price': 98.50,
                'volume': 45000000,
                'liquidity': 25000000,
                'source': 'mock'
            },
            {
                'address': '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R',
                'symbol': 'RAY',
                'name': 'Raydium',
                'price': 2.15,
                'volume': 8500000,
                'liquidity': 12000000,
                'source': 'mock'
            },
            {
                'address': 'orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE',
                'symbol': 'ORCA',
                'name': 'Orca',
                'price': 1.45,
                'volume': 3200000,
                'liquidity': 8500000,
                'source': 'mock'
            },
            {
                'address': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
                'symbol': 'BONK',
                'name': 'Bonk',
                'price': 0.0000125,
                'volume': 15000000,
                'liquidity': 5500000,
                'source': 'mock'
            },
            {
                'address': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                'symbol': 'USDC',
                'name': 'USD Coin',
                'price': 1.00,
                'volume': 85000000,
                'liquidity': 45000000,
                'source': 'mock'
            }
        ]
    
    def get_token_details(self, token_address: str) -> Optional[Dict]:
        """Get detailed information about a specific token"""
        try:
            # Try Dexscreener search for the specific token
            url = "https://api.dexscreener.com/latest/dex/search"
            params = {'q': token_address}
            data = self._make_request(url, params)
            
            if data and 'pairs' in data and data['pairs']:
                pair = data['pairs'][0]  # Take first match
                base_token = pair.get('baseToken', {})
                
                return {
                    'address': base_token.get('address'),
                    'symbol': base_token.get('symbol'),
                    'name': base_token.get('name'),
                    'price': float(pair.get('priceUsd', 0)),
                    'volume': float(pair.get('volume', {}).get('h24', 0)),
                    'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                    'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0)),
                    'source': 'dexscreener_detail'
                }
        except Exception as e:
            print(f"Error getting token details: {e}")
        
        return None