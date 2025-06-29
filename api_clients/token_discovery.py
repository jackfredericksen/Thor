# token_discovery.py

import requests
import time
import logging
from typing import List, Dict, Any, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class TokenSource:
    name: str
    url: str
    parser: str
    rate_limit: float = 1.0  # seconds between requests
    max_tokens: int = 1000

class TokenDiscovery:
    """Comprehensive Solana memecoin discovery system"""
    
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.last_request_times = {}
        
        # Multiple data sources for comprehensive coverage
        self.sources = {
            'dexscreener_trending': TokenSource(
                name='Dexscreener Trending',
                url='https://api.dexscreener.com/latest/dex/search/?q=SOL&sort=volume24hDesc',
                parser='dexscreener',
                max_tokens=500
            ),
            'dexscreener_new': TokenSource(
                name='Dexscreener New',
                url='https://api.dexscreener.com/latest/dex/tokens/new/solana',
                parser='dexscreener',
                max_tokens=200
            ),
            'jupiter_trending': TokenSource(
                name='Jupiter Trending',
                url='https://price.jup.ag/v4/price?ids=ALL&showExtraInfo=true',
                parser='jupiter',
                max_tokens=300
            ),
            'coingecko_trending': TokenSource(
                name='CoinGecko Trending',
                url='https://api.coingecko.com/api/v3/search/trending',
                parser='coingecko',
                max_tokens=100
            ),
            'birdeye_trending': TokenSource(
                name='Birdeye Trending',
                url='https://public-api.birdeye.so/defi/tokenlist?sort_by=volume24hUSD&sort_type=desc&offset=0&limit=500',
                parser='birdeye',
                max_tokens=500
            ),
            'pump_fun_new': TokenSource(
                name='Pump.fun New',
                url='https://frontend-api.pump.fun/coins?offset=0&limit=1000&sort=created_timestamp&order=DESC',
                parser='pumpfun',
                max_tokens=1000
            ),
            'pump_fun_trending': TokenSource(
                name='Pump.fun Trending',
                url='https://frontend-api.pump.fun/coins?offset=0&limit=500&sort=volume_24h&order=DESC',
                parser='pumpfun',
                max_tokens=500
            ),
            'raydium_pools': TokenSource(
                name='Raydium New Pools',
                url='https://api.raydium.io/v2/main/pairs',
                parser='raydium',
                max_tokens=300
            )
        }
    
    def discover_all_tokens(self, max_workers: int = 5) -> List[Dict[str, Any]]:
        """Discover tokens from all sources concurrently"""
        all_tokens = []
        seen_addresses = set()
        
        logger.info(f"Starting token discovery from {len(self.sources)} sources...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all source fetch tasks
            future_to_source = {
                executor.submit(self._fetch_from_source, source_name, source): source_name
                for source_name, source in self.sources.items()
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_source):
                source_name = future_to_source[future]
                try:
                    tokens = future.result(timeout=30)  # 30 second timeout per source
                    logger.info(f"Got {len(tokens)} tokens from {source_name}")
                    
                    # Deduplicate tokens
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
            # Get API key if available (most sources don't need one)
            api_key = None
            source_base = source_name.split('_')[0]  # e.g., 'birdeye_trending' -> 'birdeye'
            if hasattr(self, 'config') and self.config:
                api_key = self.config.API_KEYS.get(source_base, '')
            
            response = self._make_request(source.url, api_key=api_key)
            self.last_request_times[source_name] = time.time()
            
            # Parse based on source type
            parser_method = getattr(self, f'_parse_{source.parser}', None)
            if not parser_method:
                logger.error(f"No parser found for {source.parser}")
                return []
            
            tokens = parser_method(response.json(), source.max_tokens)
            return tokens[:source.max_tokens]  # Limit tokens per source
            
        except Exception as e:
            logger.error(f"Error fetching from {source.url}: {str(e)}")
            return []
    
    def _make_request(self, url: str, headers: Dict = None, api_key: str = None) -> requests.Response:
        """Make HTTP request with error handling - most APIs are public"""
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; TradingBot/1.0)',
            'Accept': 'application/json'
        }
        
        # Only add API key if provided and not empty
        if api_key and api_key.strip():
            default_headers['Authorization'] = f'Bearer {api_key}'
        
        if headers:
            default_headers.update(headers)
        
        response = self.session.get(url, headers=default_headers, timeout=10)
        response.raise_for_status()
        return response
    
    def _parse_dexscreener(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse Dexscreener API response"""
        tokens = []
        pairs = data.get('pairs', [])
        
        for pair in pairs[:max_tokens]:
            if pair.get('chainId') != 'solana':
                continue
                
            base_token = pair.get('baseToken', {})
            quote_token = pair.get('quoteToken', {})
            
            # Focus on tokens paired with SOL/USDC
            if quote_token.get('symbol') not in ['SOL', 'USDC', 'WSOL']:
                continue
            
            token = {
                'address': base_token.get('address'),
                'symbol': base_token.get('symbol'),
                'name': base_token.get('name'),
                'daily_volume_usd': float(pair.get('volume', {}).get('h24', 0)),
                'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0)),
                'liquidity_usd': float(pair.get('liquidity', {}).get('usd', 0)),
                'market_cap': float(pair.get('fdv', 0)),
                'price_usd': float(pair.get('priceUsd', 0)),
                'age_hours': self._calculate_age_hours(pair.get('pairCreatedAt')),
                'dex_url': pair.get('url'),
                'source_raw': 'dexscreener'
            }
            
            if token['address']:
                tokens.append(token)
        
        return tokens
    
    def _parse_pumpfun(self, data: List, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse Pump.fun API response"""
        tokens = []
        
        for item in data[:max_tokens]:
            if not isinstance(item, dict):
                continue
                
            token = {
                'address': item.get('mint'),
                'symbol': item.get('symbol'),
                'name': item.get('name'),
                'daily_volume_usd': float(item.get('volume_24h', 0)),
                'market_cap': float(item.get('market_cap', 0)),
                'price_usd': float(item.get('usd_market_cap', 0)) / max(float(item.get('total_supply', 1)), 1),
                'age_hours': self._calculate_age_hours(item.get('created_timestamp')),
                'description': item.get('description', ''),
                'twitter': item.get('twitter'),
                'telegram': item.get('telegram'),
                'website': item.get('website'),
                'source_raw': 'pumpfun'
            }
            
            if token['address']:
                tokens.append(token)
        
        return tokens
    
    def _parse_jupiter(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse Jupiter API response"""
        tokens = []
        price_data = data.get('data', {})
        
        count = 0
        for address, info in price_data.items():
            if count >= max_tokens:
                break
                
            if not info.get('extraInfo'):
                continue
            
            extra = info['extraInfo']
            
            # Filter for recent/active tokens
            if extra.get('quotedPrice', {}).get('24hChange', 0) == 0:
                continue
            
            token = {
                'address': address,
                'symbol': extra.get('quotedPrice', {}).get('symbol', ''),
                'price_usd': float(info.get('price', 0)),
                'price_change_24h': float(extra.get('quotedPrice', {}).get('24hChange', 0)),
                'source_raw': 'jupiter'
            }
            
            if token['address'] and token['symbol']:
                tokens.append(token)
                count += 1
        
        return tokens
    
    def _parse_birdeye(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse Birdeye API response"""
        tokens = []
        token_list = data.get('data', {}).get('tokens', [])
        
        for item in token_list[:max_tokens]:
            token = {
                'address': item.get('address'),
                'symbol': item.get('symbol'),
                'name': item.get('name'),
                'daily_volume_usd': float(item.get('volume24hUSD', 0)),
                'price_change_24h': float(item.get('price24hChangePercent', 0)),
                'price_usd': float(item.get('price', 0)),
                'market_cap': float(item.get('mc', 0)),
                'liquidity_usd': float(item.get('liquidityUSD', 0)),
                'source_raw': 'birdeye'
            }
            
            if token['address']:
                tokens.append(token)
        
        return tokens
    
    def _parse_raydium(self, data: List, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse Raydium API response"""
        tokens = []
        
        for pair in data[:max_tokens]:
            if pair.get('name', '').find('SOL') == -1:
                continue
            
            # Extract the non-SOL token
            base_mint = pair.get('baseMint')
            quote_mint = pair.get('quoteMint')
            
            # Determine which is the token (non-SOL)
            sol_address = 'So11111111111111111111111111111111111111112'
            if base_mint == sol_address:
                token_address = quote_mint
                token_symbol = pair.get('quoteSymbol')
            elif quote_mint == sol_address:
                token_address = base_mint
                token_symbol = pair.get('baseSymbol')
            else:
                continue
            
            token = {
                'address': token_address,
                'symbol': token_symbol,
                'name': pair.get('name'),
                'daily_volume_usd': float(pair.get('volume24h', 0)),
                'liquidity_usd': float(pair.get('liquidity', 0)),
                'source_raw': 'raydium'
            }
            
            if token['address']:
                tokens.append(token)
        
        return tokens
    
    def _parse_coingecko(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse CoinGecko trending API response"""
        tokens = []
        trending_coins = data.get('coins', [])
        
        for coin_data in trending_coins[:max_tokens]:
            coin = coin_data.get('item', {})
            
            # Only include Solana ecosystem tokens
            if 'solana' not in coin.get('name', '').lower():
                continue
            
            token = {
                'symbol': coin.get('symbol'),
                'name': coin.get('name'),
                'market_cap_rank': coin.get('market_cap_rank'),
                'coingecko_id': coin.get('id'),
                'source_raw': 'coingecko'
            }
            
            tokens.append(token)
        
        return tokens
    
    def _calculate_age_hours(self, timestamp) -> float:
        """Calculate token age in hours from various timestamp formats"""
        if not timestamp:
            return 9999  # Unknown age
        
        try:
            if isinstance(timestamp, (int, float)):
                # Unix timestamp
                if timestamp > 1e10:  # Milliseconds
                    timestamp = timestamp / 1000
                created_time = datetime.fromtimestamp(timestamp)
            else:
                # ISO string
                created_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            age = datetime.now() - created_time.replace(tzinfo=None)
            return age.total_seconds() / 3600
            
        except Exception:
            return 9999

# Enhanced main.py integration
def integrate_token_discovery():
    """Integration code for main.py"""
    return '''
# Updated main.py with comprehensive token discovery

import time
import json
import pandas as pd
from datetime import datetime

from config import DB_PATH, FETCH_INTERVAL, API_KEYS
from storage import Storage
from filters import passes_filters, TokenFilter
from technicals import Technicals
from trader import Trader
from smart_money import SmartMoneyTracker
from token_discovery import TokenDiscovery  # NEW
from api_clients.gmgn import GMGNClient

def main():
    storage = Storage(DB_PATH)
    gmgn = GMGNClient()
    smart_tracker = SmartMoneyTracker(gmgn, storage)
    technicals = Technicals()
    trader = Trader(gmgn, storage)
    
    # NEW: Comprehensive token discovery
    token_discovery = TokenDiscovery(config=None)  # Pass your config
    token_filter = TokenFilter()
    
    # Authentication
    gmgn.authenticate_telegram(API_KEYS["telegram_token"])
    gmgn.authenticate_wallet(API_KEYS["wallet_address"])

    print("Bot started. Discovering tokens across the entire Solana ecosystem...")

    while True:
        try:
            # DISCOVER ALL TOKENS (not just top 10!)
            print(f"[{datetime.now()}] Starting comprehensive token discovery...")
            all_discovered_tokens = token_discovery.discover_all_tokens()
            
            print(f"Discovered {len(all_discovered_tokens)} total tokens")
            
            # FILTER TOKENS
            print("Applying memecoin-optimized filters...")
            filtered_tokens = []
            
            for token_data in all_discovered_tokens:
                # Apply your enhanced filters
                if passes_filters(token_data):
                    # Additional sophisticated filtering
                    filter_result = token_filter.filter_token(token_data)
                    if filter_result.passed:
                        token_data['filter_score'] = filter_result.score
                        filtered_tokens.append(token_data)
            
            print(f"Tokens passing filters: {len(filtered_tokens)}")
            
            # Sort by filter score and discovery source priority
            filtered_tokens.sort(key=lambda x: (
                x.get('filter_score', 0),
                1 if 'new' in x.get('discovery_source', '') else 0
            ), reverse=True)
            
            # PROCESS TOKENS
            for i, token_data in enumerate(filtered_tokens[:100]):  # Process top 100
                token_address = token_data['address']
                
                print(f"Processing token {i+1}: {token_data.get('symbol', 'Unknown')} "
                      f"from {token_data.get('discovery_source', 'unknown')}")
                
                # Save to database
                storage.save_token_data(
                    token_address, 
                    json.dumps(token_data), 
                    token_data.get('discovery_source', 'unknown')
                )
                
                # Technical analysis (if price history available)
                if 'price_history' in token_data:
                    prices = pd.Series(token_data['price_history'])
                    rsi = technicals.compute_rsi(prices)
                    slope = technicals.compute_ema_slope(prices)
                    upper_band, lower_band = technicals.compute_volatility_band(prices)
                    rating = technicals.classify_trend(rsi, slope, prices, upper_band, lower_band)
                else:
                    # Use price change as simple signal
                    rating = "bullish" if token_data.get('price_change_24h', 0) > 10 else "neutral"
                
                print(f"Token {token_data.get('symbol')} rated as {rating}")
                
                # Execute trades
                trader.execute_trade(token_address, rating)
            
            # Monitor smart money
            smart_tracker.monitor_smart_trades()
            
            print(f"Cycle complete. Sleeping for {FETCH_INTERVAL} seconds...")
            
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
        
        time.sleep(FETCH_INTERVAL)

if __name__ == "__main__":
    main()
    '''