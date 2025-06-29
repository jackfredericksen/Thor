# api_clients/token_discovery.py

import requests
import time
import random
from typing import List, Dict, Optional
from datetime import datetime, timedelta


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
        self.min_request_interval = 1  # Faster for memecoin discovery
        
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
        """Discover NEW and TRENDING memecoins from the ecosystem"""
        print("📡 Scanning for new pairs and trending memecoins...")
        all_tokens = []
        
        # Try multiple strategies to find NEW tokens
        strategies = [
            ("New Solana Pairs (Last 24h)", self._get_new_solana_pairs),
            ("Trending Memecoins", self._get_trending_memecoins),
            ("High Volume New Tokens", self._get_high_volume_new_tokens),
            ("Recent Pump.fun Launches", self._get_recent_pumpfun_tokens),
            ("CoinGecko New/Trending", self._get_coingecko_new_trending),
        ]
        
        for strategy_name, strategy_func in strategies:
            try:
                print(f"🔍 {strategy_name}...")
                tokens = strategy_func()
                if tokens:
                    print(f"✅ Found {len(tokens)} tokens from {strategy_name}")
                    all_tokens.extend(tokens)
            except Exception as e:
                print(f"❌ {strategy_name} failed: {e}")
                continue
        
        # Remove duplicates and filter for recent tokens only
        unique_tokens = self._deduplicate_and_filter_recent(all_tokens)
        
        if not unique_tokens:
            print("⚠️ No new tokens found, using backup discovery")
            return self._get_backup_discovery()
        
        # Sort by age (newest first) and activity
        unique_tokens.sort(key=lambda x: (x.get('age_hours', 9999), -x.get('volume', 0)))
        
        print(f"🚀 Total discovered: {len(unique_tokens)} new/trending tokens")
        return unique_tokens[:20]  # Return top 20 newest
    
    def _get_new_solana_pairs(self) -> List[Dict]:
        """Get newly created Solana pairs from Dexscreener"""
        try:
            # Search for recent meme-related keywords to find new pairs
            memecoin_keywords = [
                'doge', 'pepe', 'shiba', 'floki', 'bonk', 'meme', 'cat', 'dog', 
                'moon', 'rocket', 'inu', 'coin', 'trump', 'elon', 'wojak'
            ]
            
            all_tokens = []
            for keyword in memecoin_keywords[:5]:  # Limit searches
                url = "https://api.dexscreener.com/latest/dex/search"
                params = {'q': keyword}
                data = self._make_request(url, params)
                
                if data and 'pairs' in data:
                    for pair in data['pairs'][:8]:  # Top 8 per keyword
                        if pair.get('chainId') == 'solana':
                            token = self._process_dexscreener_pair(pair)
                            if token and self._is_recent_token(token):
                                all_tokens.append(token)
                
                time.sleep(0.3)  # Small delay between searches
            
            return all_tokens[:15]  # Return top 15 newest
            
        except Exception as e:
            raise TokenDiscoveryError(f"New Solana pairs error: {e}")
    
    def _get_trending_memecoins(self) -> List[Dict]:
        """Get trending memecoins using different search strategies"""
        try:
            trending_tokens = []
            
            # Strategy 1: Search for tokens with high % gains
            trending_searches = [
                'sol +100%', 'solana memecoin', 'new meme token', 
                'trending solana', 'pump solana'
            ]
            
            for search_term in trending_searches[:3]:
                url = "https://api.dexscreener.com/latest/dex/search"
                params = {'q': search_term}
                data = self._make_request(url, params)
                
                if data and 'pairs' in data:
                    for pair in data['pairs'][:5]:
                        if pair.get('chainId') == 'solana':
                            # Check if token has high price change (trending indicator)
                            price_change = float(pair.get('priceChange', {}).get('h24', 0))
                            if abs(price_change) > 20:  # High volatility = trending
                                token = self._process_dexscreener_pair(pair)
                                if token:
                                    trending_tokens.append(token)
                
                time.sleep(0.3)
            
            return trending_tokens[:10]
            
        except Exception as e:
            raise TokenDiscoveryError(f"Trending memecoins error: {e}")
    
    def _get_high_volume_new_tokens(self) -> List[Dict]:
        """Get tokens with unusually high volume (potential viral memes)"""
        try:
            high_vol_tokens = []
            
            # Search for terms that indicate high activity
            volume_searches = ['volume', 'viral', 'pump', 'moonshot']
            
            for term in volume_searches[:2]:
                url = "https://api.dexscreener.com/latest/dex/search"
                params = {'q': term}
                data = self._make_request(url, params)
                
                if data and 'pairs' in data:
                    for pair in data['pairs'][:10]:
                        if pair.get('chainId') == 'solana':
                            volume_24h = float(pair.get('volume', {}).get('h24', 0))
                            # Look for tokens with significant volume
                            if volume_24h > 50000:  # $50k+ volume
                                token = self._process_dexscreener_pair(pair)
                                if token and self._is_recent_token(token):
                                    high_vol_tokens.append(token)
            
            return high_vol_tokens[:8]
            
        except Exception as e:
            raise TokenDiscoveryError(f"High volume tokens error: {e}")
    
    def _get_recent_pumpfun_tokens(self) -> List[Dict]:
        """Get recent token launches from Pump.fun"""
        try:
            # Try different Pump.fun endpoints for new tokens
            endpoints = [
                "https://frontend-api.pump.fun/coins?offset=0&limit=20&sort=created_timestamp&order=DESC",
                "https://frontend-api.pump.fun/coins/king-of-the-hill?limit=15"
            ]
            
            all_pumpfun_tokens = []
            
            for endpoint in endpoints:
                try:
                    data = self._make_request(endpoint)
                    if data and isinstance(data, list):
                        for token_data in data[:10]:
                            token = self._process_pumpfun_token(token_data)
                            if token:
                                all_pumpfun_tokens.append(token)
                except:
                    continue
            
            return all_pumpfun_tokens[:12]
            
        except Exception as e:
            raise TokenDiscoveryError(f"Pump.fun tokens error: {e}")
    
    def _get_coingecko_new_trending(self) -> List[Dict]:
        """Get new and trending tokens from CoinGecko"""
        try:
            trending_tokens = []
            
            # Get trending coins
            url = "https://api.coingecko.com/api/v3/search/trending"
            data = self._make_request(url)
            
            if data and 'coins' in data:
                for coin_data in data['coins'][:8]:
                    coin = coin_data.get('item', {})
                    # Filter for newer coins (lower market cap rank often = newer)
                    market_cap_rank = coin.get('market_cap_rank')
                    if not market_cap_rank or market_cap_rank > 1000:  # Focus on smaller/newer coins
                        trending_tokens.append({
                            'address': f"coingecko_{coin.get('id', 'unknown')}",
                            'symbol': coin.get('symbol'),
                            'name': coin.get('name'),
                            'price': 0,
                            'volume': 0,
                            'market_cap_rank': market_cap_rank or 9999,
                            'age_hours': 24,  # Assume recent for trending
                            'source': 'coingecko_trending'
                        })
            
            return trending_tokens
            
        except Exception as e:
            raise TokenDiscoveryError(f"CoinGecko trending error: {e}")
    
    def _process_dexscreener_pair(self, pair: Dict) -> Optional[Dict]:
        """Process Dexscreener pair data into standard format"""
        try:
            base_token = pair.get('baseToken', {})
            if not base_token.get('address'):
                return None
            
            # Calculate age
            created_at = pair.get('pairCreatedAt')
            age_hours = 9999
            if created_at:
                created_time = datetime.fromtimestamp(created_at / 1000)
                age_hours = (datetime.now() - created_time).total_seconds() / 3600
            
            volume_24h = float(pair.get('volume', {}).get('h24', 0))
            price_usd = float(pair.get('priceUsd', 0))
            liquidity = float(pair.get('liquidity', {}).get('usd', 0))
            price_change = float(pair.get('priceChange', {}).get('h24', 0))
            
            return {
                'address': base_token.get('address'),
                'symbol': base_token.get('symbol'),
                'name': base_token.get('name'),
                'price': price_usd,
                'volume': volume_24h,
                'liquidity': liquidity,
                'price_change_24h': price_change,
                'age_hours': age_hours,
                'created_at': created_at,
                'source': 'dexscreener_new'
            }
        except Exception:
            return None
    
    def _process_pumpfun_token(self, token_data: Dict) -> Optional[Dict]:
        """Process Pump.fun token data"""
        try:
            address = token_data.get('mint')
            if not address:
                return None
            
            market_cap = float(token_data.get('usd_market_cap', 0))
            total_supply = float(token_data.get('total_supply', 1))
            price = market_cap / total_supply if total_supply > 0 else 0
            
            # Calculate age
            created_timestamp = token_data.get('created_timestamp', 0)
            age_hours = 9999
            if created_timestamp:
                age_hours = (time.time() - created_timestamp) / 3600
            
            return {
                'address': address,
                'symbol': token_data.get('symbol'),
                'name': token_data.get('name'),
                'price': price,
                'volume': 0,  # Pump.fun doesn't provide volume
                'market_cap': market_cap,
                'age_hours': age_hours,
                'created_at': created_timestamp * 1000,
                'source': 'pumpfun_new'
            }
        except Exception:
            return None
    
    def _is_recent_token(self, token: Dict) -> bool:
        """Check if token is recent (created within last 7 days)"""
        age_hours = token.get('age_hours', 9999)
        return age_hours < 168  # 7 days
    
    def _deduplicate_and_filter_recent(self, tokens: List[Dict]) -> List[Dict]:
        """Remove duplicates and filter for recent tokens only"""
        seen_addresses = set()
        unique_recent_tokens = []
        
        for token in tokens:
            address = token.get('address')
            if not address or address in seen_addresses:
                continue
            
            # Only include recent tokens (less than 7 days old)
            if self._is_recent_token(token):
                seen_addresses.add(address)
                unique_recent_tokens.append(token)
        
        return unique_recent_tokens
    
    def _get_backup_discovery(self) -> List[Dict]:
        """Backup discovery when main methods fail"""
        try:
            print("🔄 Using backup discovery...")
            # Get some active Solana tokens as backup
            url = "https://api.dexscreener.com/latest/dex/search"
            params = {'q': 'solana'}
            data = self._make_request(url, params)
            
            backup_tokens = []
            if data and 'pairs' in data:
                for pair in data['pairs'][:10]:
                    if pair.get('chainId') == 'solana':
                        token = self._process_dexscreener_pair(pair)
                        if token:
                            backup_tokens.append(token)
            
            return backup_tokens
            
        except Exception:
            return self._get_mock_tokens()
    
    def _get_mock_tokens(self) -> List[Dict]:
        """Mock tokens for testing (should rarely be used now)"""
        return [
            {
                'address': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
                'symbol': 'BONK',
                'name': 'Bonk',
                'price': 0.0000125,
                'volume': 15000000,
                'liquidity': 5500000,
                'age_hours': 12,  # Recent
                'source': 'mock_new'
            }
        ]