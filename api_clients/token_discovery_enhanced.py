# token_discovery_enhanced.py - Multi-source memecoin discovery based on 2025 best practices
# Based on research into successful Solana memecoin bots

import requests
import time
import logging
import json
from typing import List, Dict, Any, Optional
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
    priority: int = 5  # 1-10, higher = more important

class EnhancedTokenDiscovery:
    """
    Enhanced token discovery using multiple data sources based on 2025 best practices

    Sources:
    1. DexScreener - New pairs and trending tokens
    2. Raydium - New liquidity pools (primary memecoin launch platform)
    3. Pump.fun - New token launches (biggest memecoin launchpad)
    4. Birdeye - Trending and new listings
    5. Jupiter - Comprehensive token list (cached)
    6. GMGN - Smart money tracking
    """

    def __init__(self, config=None):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9'
        })
        self.last_request_times = {}

        # Caches
        self.jupiter_cache = []
        self.jupiter_cache_time = None
        self.raydium_seen_pools = set()  # Track seen pools to avoid duplicates

        # Cache TTLs
        self.jupiter_cache_ttl = 1800  # 30 minutes
        self.short_cache_ttl = 60  # 1 minute for hot data

        # Enhanced sources based on research
        self.sources = {
            # 1. DexScreener - Multiple endpoints for better coverage
            'dexscreener_new_pairs': TokenSource(
                name='DexScreener New Pairs',
                url='https://api.dexscreener.com/latest/dex/pairs/solana',
                parser='dexscreener_pairs',
                max_tokens=100,
                rate_limit=1.0,
                priority=9  # High priority for new pairs
            ),
            'dexscreener_trending': TokenSource(
                name='DexScreener Trending',
                url='https://api.dexscreener.com/token-boosts/latest/v1',
                parser='dexscreener_boosts',
                max_tokens=50,
                rate_limit=1.0,
                priority=7
            ),

            # 2. Raydium - New pool detection (critical for early detection)
            'raydium_new_pools': TokenSource(
                name='Raydium New Pools',
                url='https://api.raydium.io/v2/ammV3/ammPools',
                parser='raydium_pools',
                max_tokens=100,
                rate_limit=2.0,
                priority=10  # Highest priority - earliest detection
            ),

            # 3. Pump.fun - Memecoin launchpad (6M+ tokens launched)
            'pumpfun_recent': TokenSource(
                name='Pump.fun Recent Launches',
                url='https://frontend-api.pump.fun/coins?offset=0&limit=100&sort=last_trade_timestamp&order=DESC',
                parser='pumpfun_coins',
                max_tokens=100,
                rate_limit=1.0,
                priority=9
            ),

            # 4. Birdeye - Professional grade analytics
            'birdeye_trending': TokenSource(
                name='Birdeye Trending',
                url='https://public-api.birdeye.so/defi/trending',
                parser='birdeye_trending',
                max_tokens=50,
                rate_limit=1.0,
                priority=8
            ),
            'birdeye_new_listings': TokenSource(
                name='Birdeye New Listings',
                url='https://public-api.birdeye.so/defi/token_creation',
                parser='birdeye_new',
                max_tokens=50,
                rate_limit=1.0,
                priority=9
            ),

            # 5. Jupiter - Comprehensive list (cached, lower priority)
            'jupiter_comprehensive': TokenSource(
                name='Jupiter Token List',
                url='https://token.jup.ag/all',
                parser='jupiter_cached',
                max_tokens=200,
                rate_limit=2.0,
                priority=5  # Lower priority, used as supplement
            ),

            # 6. GMGN - Smart money tracking
            'gmgn_hot_tokens': TokenSource(
                name='GMGN Hot Tokens',
                url='https://gmgn.ai/defi/quotation/v1/rank/sol/swaps/1h?limit=100',
                parser='gmgn_hot',
                max_tokens=50,
                rate_limit=1.0,
                priority=8
            ),
        }

    def discover_all_tokens(self, max_workers: int = 6) -> List[Dict[str, Any]]:
        """Discover tokens from all sources, prioritized by importance"""
        all_tokens = []
        seen_addresses = set()

        logger.info(f"Starting multi-source token discovery from {len(self.sources)} sources...")

        # Sort sources by priority (highest first)
        sorted_sources = sorted(
            self.sources.items(),
            key=lambda x: x[1].priority,
            reverse=True
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_source = {
                executor.submit(self._fetch_from_source, source_name, source): (source_name, source)
                for source_name, source in sorted_sources
            }

            for future in as_completed(future_to_source):
                source_name, source = future_to_source[future]
                try:
                    tokens = future.result(timeout=15)
                    logger.info(f"✓ {source_name}: {len(tokens)} tokens (priority: {source.priority})")

                    # Deduplicate and add metadata
                    for token in tokens:
                        address = token.get('address', '').lower()
                        if address and address not in seen_addresses:
                            seen_addresses.add(address)
                            token['discovery_source'] = source_name
                            token['source_priority'] = source.priority
                            token['discovered_at'] = datetime.now().isoformat()
                            all_tokens.append(token)

                except Exception as e:
                    logger.warning(f"⚠ {source_name}: {str(e)}")

        # Sort by priority and then by score
        all_tokens.sort(key=lambda x: (
            -x.get('source_priority', 0),
            -x.get('memecoin_score', 0),
            -x.get('daily_volume_usd', 0)
        ))

        logger.info(f"✓ Total discovered: {len(all_tokens)} unique tokens")
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

    def _make_request(self, url: str, headers: Optional[Dict] = None) -> requests.Response:
        """Make HTTP request with error handling"""
        req_headers = self.session.headers.copy()
        if headers:
            req_headers.update(headers)

        response = self.session.get(url, timeout=10, headers=req_headers)
        response.raise_for_status()
        return response

    # ========== PARSERS ==========

    def _parse_dexscreener_pairs(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse DexScreener pairs - focus on new/recent pairs"""
        tokens = []
        pairs = data.get('pairs', [])

        for pair in pairs[:max_tokens * 2]:
            try:
                # Only Solana chains
                if pair.get('chainId') != 'solana':
                    continue

                base_token = pair.get('baseToken', {})
                symbol = base_token.get('symbol', '').strip()
                address = base_token.get('address', '').strip()

                if not symbol or not address:
                    continue

                # Skip major tokens
                if symbol.upper() in ['SOL', 'USDC', 'USDT', 'WSOL']:
                    continue

                # Must have minimum volume
                volume_24h = float(pair.get('volume', {}).get('h24', 0))
                if volume_24h < 100:  # At least $100 volume
                    continue

                # Calculate age
                pair_created = pair.get('pairCreatedAt')
                age_hours = self._calculate_age_hours(pair_created)

                # Boost score for very new pairs (< 1 hour old)
                recency_boost = 2.0 if age_hours < 1 else (1.5 if age_hours < 6 else 1.0)

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
                    'pair_address': pair.get('pairAddress'),
                    'dex': pair.get('dexId', 'unknown'),
                    'source_raw': 'dexscreener'
                })

                if len(tokens) >= max_tokens:
                    break

            except Exception as e:
                logger.debug(f"Error parsing DexScreener pair: {e}")
                continue

        return tokens

    def _parse_dexscreener_boosts(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse DexScreener token boosts (promoted/trending)"""
        tokens = []
        # Implementation for boosted tokens
        # This endpoint shows tokens that are being promoted/advertised
        return tokens

    def _parse_raydium_pools(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse Raydium new liquidity pools - CRITICAL for early detection"""
        tokens = []
        pools = data.get('data', []) if isinstance(data, dict) else []

        for pool in pools[:max_tokens]:
            try:
                pool_id = pool.get('id')
                if not pool_id or pool_id in self.raydium_seen_pools:
                    continue

                # Mark as seen
                self.raydium_seen_pools.add(pool_id)

                # Extract token info
                mint_a = pool.get('mintA', {})
                mint_b = pool.get('mintB', {})

                # Determine which is the memecoin (not SOL/USDC/USDT)
                memecoin = None
                if mint_a.get('symbol', '').upper() not in ['SOL', 'USDC', 'USDT', 'WSOL']:
                    memecoin = mint_a
                elif mint_b.get('symbol', '').upper() not in ['SOL', 'USDC', 'USDT', 'WSOL']:
                    memecoin = mint_b

                if not memecoin:
                    continue

                symbol = memecoin.get('symbol', '').strip()
                address = memecoin.get('address', '').strip()

                if not symbol or not address:
                    continue

                # Raydium pools are VERY fresh - highest priority
                tokens.append({
                    'address': address,
                    'symbol': symbol,
                    'name': memecoin.get('name', symbol),
                    'daily_volume_usd': float(pool.get('day', {}).get('volume', 0)),
                    'price_change_24h': float(pool.get('day', {}).get('volumeChangePercent', 0)),
                    'liquidity_usd': float(pool.get('tvl', 0)),
                    'market_cap': 0,
                    'price_usd': float(pool.get('price', 0)),
                    'age_hours': 0.5,  # Assume very fresh
                    'memecoin_score': 3.0,  # Highest score for new Raydium pools
                    'pool_id': pool_id,
                    'dex': 'raydium',
                    'source_raw': 'raydium'
                })

            except Exception as e:
                logger.debug(f"Error parsing Raydium pool: {e}")
                continue

        return tokens

    def _parse_pumpfun_coins(self, data: List, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse Pump.fun recent launches - Major memecoin launchpad"""
        tokens = []

        for coin in (data if isinstance(data, list) else [])[:max_tokens]:
            try:
                symbol = coin.get('symbol', '').strip()
                mint = coin.get('mint', '').strip()

                if not symbol or not mint:
                    continue

                # Pump.fun coins are fresh launches
                created_timestamp = coin.get('created_timestamp', 0)
                age_hours = (time.time() - created_timestamp / 1000) / 3600 if created_timestamp else 24

                # High score for recent launches
                recency_score = 2.5 if age_hours < 1 else (2.0 if age_hours < 6 else 1.5)

                tokens.append({
                    'address': mint,
                    'symbol': symbol,
                    'name': coin.get('name', symbol),
                    'daily_volume_usd': float(coin.get('usd_market_cap', 0)),
                    'price_change_24h': 0,
                    'liquidity_usd': 0,
                    'market_cap': float(coin.get('usd_market_cap', 0)),
                    'price_usd': 0,
                    'age_hours': age_hours,
                    'memecoin_score': recency_score,
                    'description': coin.get('description', ''),
                    'image_uri': coin.get('image_uri', ''),
                    'twitter': coin.get('twitter', ''),
                    'telegram': coin.get('telegram', ''),
                    'bonding_curve': coin.get('bonding_curve', ''),
                    'source_raw': 'pumpfun'
                })

            except Exception as e:
                logger.debug(f"Error parsing Pump.fun coin: {e}")
                continue

        return tokens

    def _parse_birdeye_trending(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse Birdeye trending tokens"""
        tokens = []
        items = data.get('data', {}).get('items', [])

        for item in items[:max_tokens]:
            try:
                address = item.get('address', '').strip()
                symbol = item.get('symbol', '').strip()

                if not address or not symbol:
                    continue

                tokens.append({
                    'address': address,
                    'symbol': symbol,
                    'name': item.get('name', symbol),
                    'daily_volume_usd': float(item.get('v24hUSD', 0)),
                    'price_change_24h': float(item.get('priceChange24h', 0)),
                    'liquidity_usd': float(item.get('liquidity', 0)),
                    'market_cap': float(item.get('mc', 0)),
                    'price_usd': float(item.get('price', 0)),
                    'age_hours': 24,
                    'memecoin_score': 1.8,
                    'source_raw': 'birdeye'
                })

            except Exception as e:
                logger.debug(f"Error parsing Birdeye trending: {e}")
                continue

        return tokens

    def _parse_birdeye_new(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse Birdeye new token listings"""
        tokens = []
        # Similar to trending but for new listings
        return tokens

    def _parse_gmgn_hot(self, data: Dict, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse GMGN hot tokens (smart money activity)"""
        tokens = []
        ranks = data.get('data', {}).get('rank', [])

        for item in ranks[:max_tokens]:
            try:
                address = item.get('address', '').strip()
                symbol = item.get('symbol', '').strip()

                if not address or not symbol:
                    continue

                # GMGN tokens have smart money backing - boost score
                tokens.append({
                    'address': address,
                    'symbol': symbol,
                    'name': item.get('name', symbol),
                    'daily_volume_usd': float(item.get('swaps', 0)),
                    'price_change_24h': float(item.get('price_change_percent', 0)),
                    'liquidity_usd': 0,
                    'market_cap': float(item.get('market_cap', 0)),
                    'price_usd': float(item.get('price', 0)),
                    'age_hours': 12,
                    'memecoin_score': 2.2,  # Smart money boost
                    'smart_money': True,
                    'source_raw': 'gmgn'
                })

            except Exception as e:
                logger.debug(f"Error parsing GMGN hot: {e}")
                continue

        return tokens

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
            parsed = self._parse_jupiter_tokens(all_tokens, 500)
            self.jupiter_cache = parsed
            self.jupiter_cache_time = now
            logger.info(f"Cached {len(parsed)} Jupiter tokens")

            return parsed[:max_tokens]

        except Exception as e:
            logger.error(f"Failed to refresh Jupiter cache: {e}")
            return self.jupiter_cache[:max_tokens] if self.jupiter_cache else []

    def _parse_jupiter_tokens(self, data: List, max_tokens: int) -> List[Dict[str, Any]]:
        """Parse Jupiter token list - prioritize memecoins"""
        tokens = []

        for token in data:
            try:
                symbol = token.get('symbol', '').strip()
                address = token.get('address', '').strip()

                if not symbol or not address:
                    continue

                # Skip stablecoins/major tokens
                if symbol.upper() in ['USDC', 'USDT', 'SOL', 'WSOL', 'BTC', 'ETH', 'WETH', 'WBTC', 'DAI']:
                    continue

                # Symbol length checks
                if len(symbol) > 20 or len(symbol) < 2:
                    continue

                # Calculate memecoin score
                memecoin_score = self._calculate_memecoin_score(symbol, token.get('name', ''))

                # Only include if has some memecoin potential
                if memecoin_score > 0:
                    tokens.append({
                        'address': address,
                        'symbol': symbol,
                        'name': token.get('name', ''),
                        'daily_volume_usd': 0,
                        'price_change_24h': 0,
                        'liquidity_usd': 0,
                        'market_cap': 0,
                        'price_usd': 0,
                        'age_hours': 48,
                        'memecoin_score': memecoin_score,
                        'source_raw': 'jupiter'
                    })

                if len(tokens) >= max_tokens * 2:
                    break

            except Exception:
                continue

        # Sort by memecoin score
        tokens.sort(key=lambda x: x.get('memecoin_score', 0), reverse=True)
        return tokens[:max_tokens]

    def _calculate_memecoin_score(self, symbol: str, name: str) -> float:
        """Calculate memecoin likelihood score"""
        score = 0.0
        text = f"{symbol} {name}".lower()

        # Memecoin keywords (2025 updated list)
        keywords = [
            'meme', 'dog', 'cat', 'moon', 'pump', 'pepe', 'shib', 'doge', 'inu', 'bonk',
            'wojak', 'chad', 'frog', 'rocket', 'safe', 'baby', 'elon', 'floki', 'troll',
            'ape', 'banana', 'monke', 'smol', 'chungus', 'cope', 'seethe', 'kek', 'giga',
            'based', 'sigma', 'alpha', 'beta', 'nugget', 'tendie', 'wagmi', 'ngmi'
        ]

        for keyword in keywords:
            if keyword in text:
                score += 2.0

        # Symbol patterns
        if len(symbol) <= 6:
            score += 1.0
        if any(char in symbol.upper() for char in ['X', 'Z', 'Q', 'W', '69', '420']):
            score += 0.5
        if symbol.isupper() and len(symbol) <= 5:
            score += 0.5

        return score

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
