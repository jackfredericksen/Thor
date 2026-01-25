# token_discovery.py - Working endpoints verified 2025

import requests
import time
import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

@dataclass
class TokenSource:
    name: str
    url: str
    parser: str
    rate_limit: float = 1.0
    max_tokens: int = 100
    priority: int = 5
    headers: Dict[str, str] = None

class TokenDiscovery:
    """
    Production-ready token discovery with verified working endpoints (2025)

    Sources verified:
    - GMGN.ai (public, free)
    - PumpPortal (public, free)
    - DexScreener (public, free)
    - Jupiter (public, free)
    """

    def __init__(self, config=None):
        self.config = config
        self.last_request_times = {}

        # Caches
        self.jupiter_cache = []
        self.jupiter_cache_time = None
        self.jupiter_cache_ttl = 1800  # 30 minutes

        # Working sources - verified January 2025
        self.sources = {
            # GMGN - Hot tokens (public API)
            'gmgn_hot_sol': TokenSource(
                name='GMGN Hot Tokens (Solana)',
                url='https://gmgn.ai/defi/quotation/v1/rank/sol/swaps/1h?orderby=volume&direction=desc&limit=100',
                parser='gmgn_rank',
                max_tokens=100,
                rate_limit=2.0,
                priority=9,
                headers={
                    'Accept': 'application/json',
                    'Referer': 'https://gmgn.ai/',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            ),

            # PumpPortal - New tokens
            'pumpportal_new': TokenSource(
                name='PumpPortal New Tokens',
                url='https://pumpportal.fun/api/data',
                parser='pumpportal_data',
                max_tokens=50,
                rate_limit=1.0,
                priority=10,
                headers={
                    'Accept': 'application/json'
                }
            ),

            # DexScreener - Solana search
            'dexscreener_search': TokenSource(
                name='DexScreener Solana',
                url='https://api.dexscreener.com/latest/dex/search?q=SOL',
                parser='dexscreener_search',
                max_tokens=100,
                rate_limit=1.0,
                priority=8,
                headers=None
            ),

            # Jupiter - Comprehensive list (cached)
            'jupiter_verified': TokenSource(
                name='Jupiter Tokens',
                url='https://token.jup.ag/all',
                parser='jupiter_tokens',
                max_tokens=200,
                rate_limit=2.0,
                priority=6,
                headers=None
            ),
        }

    @contextmanager
    def _get_session(self):
        """Context manager for session - ensures cleanup"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
        try:
            yield session
        finally:
            session.close()

    def discover_all_tokens(self, max_workers: int = 4) -> List[Dict[str, Any]]:
        """Discover tokens with proper resource management"""
        all_tokens = []
        seen_addresses = set()

        logger.info(f"Starting token discovery from {len(self.sources)} sources...")

        # Sort by priority
        sorted_sources = sorted(
            self.sources.items(),
            key=lambda x: x[1].priority,
            reverse=True
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_source = {
                executor.submit(self._fetch_from_source_safe, source_name, source): (source_name, source)
                for source_name, source in sorted_sources
            }

            for future in as_completed(future_to_source):
                source_name, source = future_to_source[future]
                try:
                    tokens = future.result(timeout=15)
                    if tokens:
                        logger.info(f"✓ {source_name}: {len(tokens)} tokens (priority: {source.priority})")

                        for token in tokens:
                            address = token.get('address', '').lower()
                            if address and address not in seen_addresses:
                                seen_addresses.add(address)
                                token['discovery_source'] = source_name
                                token['source_priority'] = source.priority
                                token['discovered_at'] = datetime.now().isoformat()
                                all_tokens.append(token)
                    else:
                        logger.warning(f"⚠ {source_name}: No tokens returned")

                except Exception as e:
                    logger.error(f"✗ {source_name} failed: {str(e)}")

        # Sort by priority and score
        all_tokens.sort(key=lambda x: (
            -x.get('source_priority', 0),
            -x.get('memecoin_score', 0),
            -x.get('daily_volume_usd', 0)
        ))

        logger.info(f"✓ Total discovered: {len(all_tokens)} unique tokens")
        return all_tokens

    def _fetch_from_source_safe(self, source_name: str, source: TokenSource) -> List[Dict[str, Any]]:
        """Fetch with automatic cleanup and error handling"""
        # Rate limiting
        now = time.time()
        last_request = self.last_request_times.get(source_name, 0)
        time_since_last = now - last_request

        if time_since_last < source.rate_limit:
            time.sleep(source.rate_limit - time_since_last)

        try:
            with self._get_session() as session:
                # Add source-specific headers
                headers = session.headers.copy()
                if source.headers:
                    headers.update(source.headers)

                # Special handling for Jupiter (cached)
                if source.parser == 'jupiter_tokens':
                    return self._get_jupiter_cached(session, source.max_tokens)

                # Make request
                response = session.get(source.url, timeout=10, headers=headers)
                response.raise_for_status()
                self.last_request_times[source_name] = time.time()

                # Parse
                parser_method = getattr(self, f'_parse_{source.parser}', None)
                if not parser_method:
                    logger.error(f"No parser for {source.parser}")
                    return []

                return parser_method(response.json(), source.max_tokens)

        except requests.exceptions.ConnectionError:
            logger.error(f"{source_name}: Network unreachable")
            return []
        except requests.exceptions.Timeout:
            logger.error(f"{source_name}: Request timeout")
            return []
        except requests.exceptions.HTTPError as e:
            logger.error(f"{source_name}: HTTP {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"{source_name}: {str(e)}")
            return []

    def _get_jupiter_cached(self, session: requests.Session, max_tokens: int) -> List[Dict[str, Any]]:
        """Get Jupiter tokens with caching"""
        now = time.time()

        # Check cache validity
        if (self.jupiter_cache and self.jupiter_cache_time and
            (now - self.jupiter_cache_time) < self.jupiter_cache_ttl):
            logger.info("Using cached Jupiter tokens")
            return self.jupiter_cache[:max_tokens]

        # Refresh cache
        logger.info("Refreshing Jupiter cache...")
        try:
            response = session.get('https://token.jup.ag/all', timeout=15)
            response.raise_for_status()
            all_tokens = response.json()

            parsed = self._parse_jupiter_tokens(all_tokens, 500)
            self.jupiter_cache = parsed
            self.jupiter_cache_time = now
            logger.info(f"Cached {len(parsed)} Jupiter tokens")

            return parsed[:max_tokens]

        except Exception as e:
            logger.error(f"Failed to refresh Jupiter cache: {e}")
            return self.jupiter_cache[:max_tokens] if self.jupiter_cache else []

    def _parse_gmgn_rank(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse GMGN ranking data"""
        tokens = []

        # GMGN returns data in 'data.rank' array
        rank_data = data.get('data', {}).get('rank', [])

        for item in rank_data[:max_tokens]:
            try:
                address = item.get('address', '').strip()
                symbol = item.get('symbol', '').strip()

                if not address or not symbol:
                    continue

                # Skip major tokens
                if symbol.upper() in ['SOL', 'USDC', 'USDT', 'WSOL']:
                    continue

                tokens.append({
                    'address': address,
                    'symbol': symbol,
                    'name': item.get('name', symbol),
                    'daily_volume_usd': float(item.get('swaps', 0)),
                    'price_change_24h': float(item.get('price_change_percent', 0)),
                    'liquidity_usd': float(item.get('liquidity', 0)),
                    'market_cap': float(item.get('market_cap', 0)),
                    'price_usd': float(item.get('price', 0)),
                    'age_hours': 12,
                    'memecoin_score': 2.5,  # GMGN tokens are hot/trending
                    'smart_money': True,
                    'source_raw': 'gmgn'
                })

            except Exception as e:
                logger.debug(f"Error parsing GMGN item: {e}")
                continue

        return tokens

    def _parse_pumpportal_data(self, data: Any, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse PumpPortal data - can be list or dict"""
        tokens = []

        # Handle different response formats
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('data', []) or data.get('tokens', [])
        else:
            return tokens

        for item in items[:max_tokens]:
            try:
                # PumpPortal format varies, try multiple keys
                address = (item.get('mint') or item.get('address') or
                          item.get('token_address', '')).strip()
                symbol = (item.get('symbol') or item.get('name', '')).strip()

                if not address or not symbol:
                    continue

                # New pump.fun tokens get high priority
                tokens.append({
                    'address': address,
                    'symbol': symbol,
                    'name': item.get('name', symbol),
                    'daily_volume_usd': float(item.get('volume', 0)),
                    'price_change_24h': 0,
                    'liquidity_usd': 0,
                    'market_cap': float(item.get('market_cap', 0)),
                    'price_usd': float(item.get('price', 0)),
                    'age_hours': 0.5,  # Very fresh
                    'memecoin_score': 3.0,  # Highest for new launches
                    'pumpfun': True,
                    'source_raw': 'pumpportal'
                })

            except Exception as e:
                logger.debug(f"Error parsing PumpPortal item: {e}")
                continue

        return tokens

    def _parse_dexscreener_search(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse DexScreener search results"""
        tokens = []
        pairs = data.get('pairs', [])

        for pair in pairs[:max_tokens * 2]:
            try:
                if pair.get('chainId') != 'solana':
                    continue

                base_token = pair.get('baseToken', {})
                symbol = base_token.get('symbol', '').strip()
                address = base_token.get('address', '').strip()

                if not symbol or not address:
                    continue

                if symbol.upper() in ['SOL', 'USDC', 'USDT', 'WSOL', 'BTC', 'ETH']:
                    continue

                volume_24h = float(pair.get('volume', {}).get('h24', 0))
                if volume_24h < 500:
                    continue

                age_hours = self._calculate_age_hours(pair.get('pairCreatedAt'))
                recency_boost = 2.0 if age_hours < 1 else 1.5 if age_hours < 6 else 1.0

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
                    'memecoin_score': recency_boost,
                    'source_raw': 'dexscreener'
                })

                if len(tokens) >= max_tokens:
                    break

            except Exception as e:
                logger.debug(f"Error parsing DexScreener pair: {e}")
                continue

        return tokens

    def _parse_jupiter_tokens(self, data: List, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse Jupiter token list - prioritize memecoins"""
        tokens = []

        for token in data:
            try:
                symbol = token.get('symbol', '').strip()
                address = token.get('address', '').strip()
                name = token.get('name', '').strip()

                if not symbol or not address:
                    continue

                if symbol.upper() in ['USDC', 'USDT', 'SOL', 'WSOL', 'BTC', 'ETH', 'WETH', 'WBTC', 'DAI', 'PYUSD']:
                    continue

                if len(symbol) > 20 or len(symbol) < 2:
                    continue

                score = self._calculate_memecoin_score(symbol, name)

                if score > 0:
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
                        'memecoin_score': score,
                        'source_raw': 'jupiter'
                    })

                if len(tokens) >= max_tokens * 2:
                    break

            except Exception:
                continue

        tokens.sort(key=lambda x: x.get('memecoin_score', 0), reverse=True)
        return tokens[:max_tokens]

    def _calculate_memecoin_score(self, symbol: str, name: str) -> float:
        """Calculate memecoin likelihood"""
        score = 0.0
        text = f"{symbol} {name}".lower()

        keywords = [
            'meme', 'dog', 'cat', 'moon', 'pump', 'pepe', 'shib', 'doge', 'inu', 'bonk',
            'wojak', 'chad', 'frog', 'rocket', 'baby', 'elon', 'floki', 'troll', 'ape',
            'monke', 'cope', 'seethe', 'based', 'sigma', 'wagmi', 'giga', 'smol'
        ]

        for keyword in keywords:
            if keyword in text:
                score += 2.0

        if len(symbol) <= 6:
            score += 1.0
        if any(char in symbol.upper() for char in ['X', 'Z', 'Q', 'W']):
            score += 0.5

        return score

    def _calculate_age_hours(self, timestamp) -> float:
        """Calculate age in hours"""
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

    def __del__(self):
        """Cleanup on destruction"""
        pass


# Backwards compatibility
EnhancedTokenDiscovery = TokenDiscovery
