# token_discovery.py - Replace your existing file with this version

import requests
import time
import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class TokenSource:
    name: str
    url: str
    parser: str
    rate_limit: float = 1.0
    max_tokens: int = 1000

class TokenDiscovery:
    """Working token discovery using verified APIs"""
    
    def __init__(self, config=None):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; TradingBot/1.0)',
            'Accept': 'application/json'
        })
        self.last_request_times = {}
        
        # Working sources - Jupiter-only for maximum reliability and coverage
        self.sources = {
            'jupiter_comprehensive': TokenSource(
                name='Jupiter Comprehensive Token List',
                url='https://token.jup.ag/all',
                parser='jupiter_tokens',
                max_tokens=1000,  # Increased from 500 for more coverage
                rate_limit=2.0
            ),
        }
    
    def discover_all_tokens(self, max_workers: int = 4) -> List[Dict[str, Any]]:
        """Discover tokens from all working sources"""
        all_tokens = []
        seen_addresses = set()
        
        logger.info(f"Starting comprehensive Jupiter token discovery (287k+ tokens)...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_source = {
                executor.submit(self._fetch_from_source, source_name, source): source_name
                for source_name, source in self.sources.items()
            }
            
            for future in as_completed(future_to_source):
                source_name = future_to_source[future]
                try:
                    tokens = future.result(timeout=30)
                    logger.info(f"Got {len(tokens)} tokens from {source_name}")
                    
                    # Deduplicate and add metadata
                    for token in tokens:
                        address = token.get('address', '').lower()
                        if address and address not in seen_addresses:
                            seen_addresses.add(address)
                            token['discovery_source'] = source_name
                            token['discovered_at'] = datetime.now().isoformat()
                            all_tokens.append(token)
                    
                except Exception as e:
                    logger.error(f"Error fetching from {source_name}: {str(e)}")
        
        logger.info(f"Total unique tokens discovered: {len(all_tokens)}")
        return all_tokens
    
    def _fetch_from_source(self, source_name: str, source: TokenSource) -> List[Dict[str, Any]]:
        """Fetch tokens from a single source with rate limiting"""
        # Rate limiting
        now = time.time()
        last_request = self.last_request_times.get(source_name, 0)
        time_since_last = now - last_request
        
        if time_since_last < source.rate_limit:
            time.sleep(source.rate_limit - time_since_last)
        
        try:
            response = self._make_request(source.url)
            self.last_request_times[source_name] = time.time()
            
            # Parse based on source type
            parser_method = getattr(self, f'_parse_{source.parser}', None)
            if not parser_method:
                logger.error(f"No parser found for {source.parser}")
                return []
            
            tokens = parser_method(response.json(), source.max_tokens)
            return tokens[:source.max_tokens]
            
        except Exception as e:
            logger.error(f"Error fetching from {source.url}: {str(e)}")
            return []
    
    def _make_request(self, url: str) -> requests.Response:
        """Make HTTP request with error handling"""
        response = self.session.get(url, timeout=15)
        response.raise_for_status()
        return response
    
    def _parse_jupiter_tokens(self, data: List, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse Jupiter token list with better memecoin detection"""
        tokens = []
        
        for token in data:
            symbol = token.get('symbol', '')
            name = token.get('name', '')
            
            # Skip obvious stablecoins/major tokens
            if (symbol and 
                symbol.upper() not in ['USDC', 'USDT', 'SOL', 'WSOL', 'BTC', 'ETH', 'WETH', 'WBTC', 'DAI', 'PYUSD'] and
                len(symbol) <= 20 and  # Reasonable symbol length
                len(symbol) >= 2):    # Not too short
                
                # Prioritize potential memecoins
                memecoin_score = 0
                
                # Check for memecoin keywords in symbol/name
                memecoin_keywords = ['meme', 'dog', 'cat', 'moon', 'pump', 'pepe', 'shib', 'doge', 'inu', 'bonk']
                text_to_check = f"{symbol} {name}".lower()
                
                for keyword in memecoin_keywords:
                    if keyword in text_to_check:
                        memecoin_score += 1
                
                # Check for common memecoin patterns
                if len(symbol) <= 6:  # Short symbols often memecoins
                    memecoin_score += 0.5
                    
                if any(char in symbol.upper() for char in ['X', 'Z', 'Q']):  # Edgy letters
                    memecoin_score += 0.3
                
                tokens.append({
                    'address': token.get('address'),
                    'symbol': symbol,
                    'name': name,
                    'daily_volume_usd': 0,  # Jupiter doesn't provide this
                    'price_change_24h': 0,  # Jupiter doesn't provide this
                    'liquidity_usd': 0,
                    'market_cap': 0,
                    'price_usd': 0,
                    'age_hours': 48,  # Default assumption for Jupiter tokens
                    'memecoin_score': memecoin_score,  # Our custom scoring
                    'source_raw': 'jupiter'
                })
                
                if len(tokens) >= max_tokens:
                    break
        
        # Sort by memecoin score (highest first) to prioritize memecoins
        tokens.sort(key=lambda x: x.get('memecoin_score', 0), reverse=True)
        
        return tokens
    
    def _parse_coingecko_markets(self, data: List, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse CoinGecko markets data"""
        tokens = []
        
        for coin in data:
            symbol = coin.get('symbol', '').upper()
            
            # Skip major tokens and stablecoins
            if symbol in ['SOL', 'USDC', 'USDT', 'BTC', 'ETH']:
                continue
            
            # Skip very large market caps (already established)
            market_cap = coin.get('market_cap') or 0
            if market_cap > 1_000_000_000:  # Over $1B
                continue
            
            tokens.append({
                'address': '',  # CoinGecko doesn't always provide this
                'symbol': coin.get('symbol', ''),
                'name': coin.get('name', ''),
                'daily_volume_usd': float(coin.get('total_volume') or 0),
                'price_change_24h': float(coin.get('price_change_percentage_24h') or 0),
                'liquidity_usd': 0,
                'market_cap': float(market_cap),
                'price_usd': float(coin.get('current_price') or 0),
                'age_hours': 168,  # Default to 1 week
                'coingecko_id': coin.get('id'),
                'source_raw': 'coingecko'
            })
            
            if len(tokens) >= max_tokens:
                break
        
        return tokens
    
    def _parse_dexscreener(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse DexScreener search results"""
        tokens = []
        pairs = data.get('pairs', [])
        
        for pair in pairs:
            if pair.get('chainId') != 'solana':
                continue
            
            base_token = pair.get('baseToken', {})
            quote_token = pair.get('quoteToken', {})
            
            # Must be paired with SOL/USDC/USDT
            quote_symbol = quote_token.get('symbol', '').upper()
            if quote_symbol not in ['SOL', 'USDC', 'USDT', 'WSOL']:
                continue
            
            base_symbol = base_token.get('symbol', '')
            if not base_symbol or base_symbol.upper() in ['SOL', 'USDC', 'USDT']:
                continue
            
            # Must have some volume
            volume_24h = float(pair.get('volume', {}).get('h24', 0))
            if volume_24h < 100:  # At least $100 daily volume
                continue
            
            tokens.append({
                'address': base_token.get('address'),
                'symbol': base_symbol,
                'name': base_token.get('name', base_symbol),
                'daily_volume_usd': volume_24h,
                'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0)),
                'liquidity_usd': float(pair.get('liquidity', {}).get('usd', 0)),
                'market_cap': float(pair.get('fdv', 0)),
                'price_usd': float(pair.get('priceUsd', 0)),
                'age_hours': self._calculate_age_hours(pair.get('pairCreatedAt')),
                'source_raw': 'dexscreener'
            })
            
            if len(tokens) >= max_tokens:
                break
        
        return tokens
    
    def _calculate_age_hours(self, timestamp) -> float:
        """Calculate age in hours from timestamp"""
        if not timestamp:
            return 24  # Default to 1 day
        
        try:
            if isinstance(timestamp, (int, float)):
                if timestamp > 1e10:  # Milliseconds
                    timestamp = timestamp / 1000
                created_time = datetime.fromtimestamp(timestamp)
            else:
                created_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            age = datetime.now() - created_time.replace(tzinfo=None)
            return age.total_seconds() / 3600
            
        except Exception:
            return 24  # Default to 1 day if parsing fails