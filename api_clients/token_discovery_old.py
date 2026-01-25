# token_discovery.py - Optimized for fast discovery with caching

import requests
import time
import logging
import json
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class TokenSource:
    name: str
    url: str
    parser: str
    rate_limit: float = 1.0
    max_tokens: int = 100

class TokenDiscovery:
    """Fast token discovery with intelligent caching"""

    def __init__(self, config=None):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; TradingBot/1.0)',
            'Accept': 'application/json'
        })
        self.last_request_times = {}

        # Cache for Jupiter tokens (refresh every 30 minutes)
        self.jupiter_cache = []
        self.jupiter_cache_time = None
        self.jupiter_cache_ttl = 1800  # 30 minutes

        # Working sources - Multiple APIs for diversity
        self.sources = {
            'dexscreener_solana': TokenSource(
                name='DexScreener Solana Trending',
                url='https://api.dexscreener.com/latest/dex/search?q=solana',
                parser='dexscreener_search',
                max_tokens=50,
                rate_limit=1.0
            ),
            'jupiter_trending': TokenSource(
                name='Jupiter Trending (Cached)',
                url='https://token.jup.ag/all',
                parser='jupiter_cached',
                max_tokens=100,
                rate_limit=2.0
            ),
        }

    def discover_all_tokens(self, max_workers: int = 4) -> List[Dict[str, Any]]:
        """Discover tokens from all working sources with intelligent caching"""
        all_tokens = []
        seen_addresses = set()

        logger.info(f"Starting optimized token discovery...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_source = {
                executor.submit(self._fetch_from_source, source_name, source): source_name
                for source_name, source in self.sources.items()
            }

            for future in as_completed(future_to_source):
                source_name = future_to_source[future]
                try:
                    tokens = future.result(timeout=10)
                    logger.info(f"✓ {source_name}: {len(tokens)} tokens")

                    # Deduplicate and add metadata
                    for token in tokens:
                        address = token.get('address', '').lower()
                        if address and address not in seen_addresses:
                            seen_addresses.add(address)
                            token['discovery_source'] = source_name
                            token['discovered_at'] = datetime.now().isoformat()
                            all_tokens.append(token)

                except Exception as e:
                    logger.warning(f"⚠ {source_name}: {str(e)}")

        logger.info(f"✓ Discovered {len(all_tokens)} unique tokens")
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
            # Special handling for cached sources
            if source.parser == 'jupiter_cached':
                tokens = self._get_jupiter_cached(source.max_tokens)
            else:
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

    def _get_jupiter_cached(self, max_tokens: int) -> List[Dict[str, Any]]:
        """Get Jupiter tokens from cache, refresh if needed"""
        now = time.time()

        # Check if cache is valid
        if (self.jupiter_cache and self.jupiter_cache_time and
            (now - self.jupiter_cache_time) < self.jupiter_cache_ttl):
            logger.info("Using cached Jupiter tokens")
            return self.jupiter_cache[:max_tokens]

        # Refresh cache
        logger.info("Refreshing Jupiter token cache...")
        try:
            response = self._make_request('https://token.jup.ag/all')
            all_tokens = response.json()

            # Parse and cache
            parsed = self._parse_jupiter_tokens(all_tokens, 500)  # Cache top 500
            self.jupiter_cache = parsed
            self.jupiter_cache_time = now
            logger.info(f"Cached {len(parsed)} Jupiter tokens")

            return parsed[:max_tokens]

        except Exception as e:
            logger.error(f"Failed to refresh Jupiter cache: {e}")
            # Return old cache if available
            return self.jupiter_cache[:max_tokens] if self.jupiter_cache else []

    def _make_request(self, url: str) -> requests.Response:
        """Make HTTP request with error handling"""
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        return response

    def _parse_dexscreener_search(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse DexScreener search results - FAST"""
        tokens = []
        pairs = data.get('pairs', [])

        for pair in pairs[:max_tokens * 2]:  # Check 2x to account for filtering
            try:
                base_token = pair.get('baseToken', {})

                # Quick validations
                symbol = base_token.get('symbol', '').strip()
                address = base_token.get('address', '').strip()

                if not symbol or not address:
                    continue

                # Skip major tokens
                if symbol.upper() in ['SOL', 'USDC', 'USDT', 'WSOL', 'BTC', 'ETH']:
                    continue

                # Must have volume
                volume_24h = float(pair.get('volume', {}).get('h24', 0))
                if volume_24h < 500:  # At least $500 volume
                    continue

                # Calculate age
                age_hours = self._calculate_age_hours(pair.get('pairCreatedAt'))

                tokens.append({
                    'address': address,
                    'symbol': symbol,
                    'name': base_token.get('name', symbol),
                    'daily_volume_usd': volume_24h,
                    'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0)),
                    'liquidity_usd': float(pair.get('liquidity', {}).get('usd', 0)),
                    'market_cap': float(pair.get('fdv', 0) or 0),
                    'price_usd': float(pair.get('priceUsd', 0)),
                    'age_hours': age_hours,
                    'source_raw': 'dexscreener'
                })

                if len(tokens) >= max_tokens:
                    break

            except Exception as e:
                logger.debug(f"Error parsing pair: {e}")
                continue

        return tokens

    def _parse_jupiter_tokens(self, data: List, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse Jupiter token list - prioritize memecoins"""
        tokens = []

        for token in data:
            try:
                symbol = token.get('symbol', '').strip()
                name = token.get('name', '').strip()
                address = token.get('address', '').strip()

                if not symbol or not address:
                    continue

                # Skip stablecoins/major tokens
                if symbol.upper() in ['USDC', 'USDT', 'SOL', 'WSOL', 'BTC', 'ETH', 'WETH', 'WBTC', 'DAI', 'PYUSD']:
                    continue

                # Symbol length checks
                if len(symbol) > 20 or len(symbol) < 2:
                    continue

                # Calculate memecoin score
                memecoin_score = 0
                text_to_check = f"{symbol} {name}".lower()

                # Memecoin keywords
                memecoin_keywords = [
                    'meme', 'dog', 'cat', 'moon', 'pump', 'pepe', 'shib', 'doge', 'inu', 'bonk',
                    'wojak', 'chad', 'frog', 'rocket', 'safe', 'baby', 'elon', 'floki'
                ]

                for keyword in memecoin_keywords:
                    if keyword in text_to_check:
                        memecoin_score += 2

                # Short symbols (often memecoins)
                if len(symbol) <= 6:
                    memecoin_score += 1

                # Edgy characters
                if any(char in symbol.upper() for char in ['X', 'Z', 'Q', 'W']):
                    memecoin_score += 0.5

                # Only include if some memecoin potential
                if memecoin_score > 0:
                    tokens.append({
                        'address': address,
                        'symbol': symbol,
                        'name': name,
                        'daily_volume_usd': 0,
                        'price_change_24h': 0,
                        'liquidity_usd': 0,
                        'market_cap': 0,
                        'price_usd': 0,
                        'age_hours': 48,
                        'memecoin_score': memecoin_score,
                        'source_raw': 'jupiter'
                    })

                if len(tokens) >= max_tokens * 2:  # Collect extra for sorting
                    break

            except Exception:
                continue

        # Sort by memecoin score
        tokens.sort(key=lambda x: x.get('memecoin_score', 0), reverse=True)

        return tokens[:max_tokens]

    def _calculate_age_hours(self, timestamp) -> float:
        """Calculate age in hours from timestamp"""
        if not timestamp:
            return 24.0

        try:
            if isinstance(timestamp, (int, float)):
                if timestamp > 1e10:
                    timestamp = timestamp / 1000
                created_time = datetime.fromtimestamp(timestamp)
            else:
                created_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

            age = datetime.now() - created_time.replace(tzinfo=None)
            return age.total_seconds() / 3600

        except Exception:
            return 24.0
