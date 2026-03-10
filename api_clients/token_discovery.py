# token_discovery.py - Working endpoints verified 2025
# Integrates DexScreener HotScanner as primary high-quality discovery source

import requests
import time
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Real-time WebSocket-based sources (higher priority than REST sources)
# ---------------------------------------------------------------------------

class PumpFunSource:
    """
    Drains the PumpFunWebSocketClient deque for brand-new pump.fun launches.
    Priority 15 — above DexHotScanner (10).
    """

    def __init__(self):
        from api_clients.pumpfun import PumpFunWebSocketClient
        self._client = PumpFunWebSocketClient()
        self._client.start()

    def fetch(self) -> List[Dict[str, Any]]:
        return self._client.get_pending_tokens()


class MigrationDiscoverySource:
    """
    Drains the MigrationMonitor deque for pump.fun → PumpSwap graduations.
    Priority 20 — highest of all sources.
    Tokens are immediately flagged is_migration=True for fast-track processing.
    """

    def __init__(self):
        from api_clients.migration_monitor import get_migration_monitor
        self._monitor = get_migration_monitor()

    def fetch(self) -> List[Dict[str, Any]]:
        return self._monitor.get_pending_migrations()


class MeteoraScannerSource:
    """
    Drains the MeteoraScanner deque for new Meteora DLMM/DBC pools.
    Priority 18 — between pumpfun_ws (15) and migration_monitor (20).
    Disabled gracefully when HELIUS_WSS_URL is not set.
    """

    def __init__(self):
        from api_clients.meteora_scanner import get_meteora_scanner
        self._scanner = get_meteora_scanner()

    def fetch(self) -> List[Dict[str, Any]]:
        try:
            return self._scanner.get_pending_pools()
        except Exception:
            return []


class EventProxySource:
    """
    Drains the EventProxyClient deque for sub-ms pool creation events.
    Priority 25 — highest.
    Disabled gracefully when EVENT_PROXY_URL is not set.
    """

    def __init__(self):
        from api_clients.event_proxy_client import get_event_proxy_client
        self._client = get_event_proxy_client()

    def fetch(self) -> List[Dict[str, Any]]:
        try:
            return self._client.get_pending_events()
        except Exception:
            return []


class DexHotScannerSource:
    """
    High-quality token discovery via DexScreener HotScanner.

    Uses the professional scanner from dexscreener-cli-mcp-tool to find
    trending tokens with advanced composite scoring (0-100 scale), including:
    - Volume velocity, transaction velocity
    - Compression score + breakout readiness
    - Relative strength vs chain baseline
    - Boost/profile signals
    - Risk profiling and momentum decay
    """

    def __init__(
        self,
        chains: tuple = ("solana",),
        limit: int = 30,
        min_liquidity_usd: float = 20_000.0,
        min_volume_h24_usd: float = 40_000.0,
        min_txns_h1: int = 15,
    ) -> None:
        self.chains = chains
        self.limit = limit
        self.min_liquidity_usd = min_liquidity_usd
        self.min_volume_h24_usd = min_volume_h24_usd
        self.min_txns_h1 = min_txns_h1
        self._last_run: float = 0.0
        self._cache: List[Dict[str, Any]] = []
        self._cache_ttl: float = 60.0  # Cache results for 60 seconds

    def fetch(self) -> List[Dict[str, Any]]:
        """
        Run HotScanner and convert HotTokenCandidate objects to Thor token dicts.
        Results are cached for 60 seconds to avoid hammering the API.
        """
        now = time.time()
        if self._cache and (now - self._last_run) < self._cache_ttl:
            logger.info(f"DexHotScanner: returning {len(self._cache)} cached tokens")
            return self._cache

        try:
            from api_clients.dex_scanner import ScanFilters, run_hot_scan

            filters = ScanFilters(
                chains=self.chains,
                limit=self.limit,
                min_liquidity_usd=self.min_liquidity_usd,
                min_volume_h24_usd=self.min_volume_h24_usd,
                min_txns_h1=self.min_txns_h1,
            )
            candidates = run_hot_scan(filters)
            tokens = [self._candidate_to_token(c) for c in candidates]
            self._cache = tokens
            self._last_run = now
            logger.info(f"DexHotScanner: discovered {len(tokens)} hot tokens")
            return tokens

        except Exception as exc:
            logger.error(f"DexHotScanner failed: {exc}")
            return self._cache  # return stale cache on failure

    @staticmethod
    def _candidate_to_token(candidate) -> Dict[str, Any]:
        """Convert HotTokenCandidate to Thor's standard token dict format."""
        pair = candidate.pair
        analytics = candidate.analytics

        return {
            # Core identifiers
            "address": pair.base_address,
            "symbol": pair.base_symbol,
            "name": pair.base_name,
            "chain": pair.chain_id,
            # Price and market data
            "price_usd": pair.price_usd,
            "price_change_24h": pair.price_change_h24,
            "price_change_1h": pair.price_change_h1,
            "market_cap": pair.market_cap if pair.market_cap > 0 else pair.fdv,
            "fdv": pair.fdv,
            "liquidity_usd": pair.liquidity_usd,
            # Volume and activity
            "daily_volume_usd": pair.volume_h24,
            "volume_24h": pair.volume_h24,
            "volume_6h": pair.volume_h6,
            "volume_1h": pair.volume_h1,
            "txns_24h": pair.txns_h24,
            "buys_24h": pair.buys_h24,
            "sells_24h": pair.sells_h24,
            "txns_1h": pair.txns_h1,
            "buys_1h": pair.buys_h1,
            "sells_1h": pair.sells_h1,
            # Age and timing
            "age_hours": pair.age_hours if pair.age_hours is not None else 9999.0,
            # Pair info
            "pair_address": pair.pair_address,
            "dex_id": pair.dex_id,
            "quote_symbol": pair.quote_symbol,
            "dex_pair_url": pair.pair_url,
            # DexScreener hotness scoring (0-100)
            "dex_hotness_score": candidate.score,
            "dex_base_score": analytics.base_score,
            "dex_tags": list(candidate.tags),
            "dex_discovery": candidate.discovery,
            # Advanced analytics
            "dex_analytics": {
                "compression_score": analytics.compression_score,
                "breakout_readiness": analytics.breakout_readiness,
                "volume_velocity": analytics.volume_velocity,
                "txn_velocity": analytics.txn_velocity,
                "relative_strength": analytics.relative_strength,
                "chain_baseline_h1": analytics.chain_baseline_h1,
                "boost_velocity": analytics.boost_velocity,
                "momentum_half_life_min": analytics.momentum_half_life_min,
                "momentum_decay_ratio": analytics.momentum_decay_ratio,
                "fast_decay": analytics.fast_decay,
                "risk_score": analytics.risk_score,
                "risk_penalty": analytics.risk_penalty,
                "risk_flags": list(analytics.risk_flags),
                "score_components": dict(analytics.score_components),
            },
            # Boost/profile signals
            "dex_boost_total": candidate.boost_total,
            "dex_boost_count": candidate.boost_count,
            "dex_has_profile": candidate.has_profile,
            # Holder data (if available)
            "holder_count": pair.holders_count,
            # Memecoin score proxy from DexScreener hotness
            "memecoin_score": candidate.score / 25.0,  # Scale 0-100 → 0-4
            # Source metadata
            "discovery_source": "dex_hot_scanner",
            "source_priority": 10,
            "discovered_at": datetime.now().isoformat(),
        }

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
    - DexScreener HotScanner (primary, advanced scoring)
    - GMGN.ai (public, free)
    - PumpPortal (public, free)
    - DexScreener search (public, free)
    - Jupiter (public, free)
    """

    def __init__(self, config=None):
        self.config = config
        self.last_request_times = {}

        # Caches
        self.jupiter_cache = []
        self.jupiter_cache_time = None
        self.jupiter_cache_ttl = 1800  # 30 minutes

        # DexScreener HotScanner (primary REST source)
        self.dex_hot_scanner = DexHotScannerSource(
            chains=("solana",),
            limit=30,
            min_liquidity_usd=20_000.0,
            min_volume_h24_usd=40_000.0,
            min_txns_h1=15,
        )

        # Real-time WebSocket sources (higher priority)
        try:
            self.pumpfun_source = PumpFunSource()
        except Exception as exc:
            logger.warning(f"PumpFunSource init failed: {exc}")
            self.pumpfun_source = None

        try:
            self.migration_source = MigrationDiscoverySource()
        except Exception as exc:
            logger.warning(f"MigrationDiscoverySource init failed: {exc}")
            self.migration_source = None

        try:
            self.meteora_source = MeteoraScannerSource()
        except Exception as exc:
            logger.warning(f"MeteoraScannerSource init failed: {exc}")
            self.meteora_source = None

        try:
            self.event_proxy_source = EventProxySource()
        except Exception as exc:
            logger.warning(f"EventProxySource init failed: {exc}")
            self.event_proxy_source = None

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
        """Discover tokens from all sources including DexScreener HotScanner."""
        all_tokens = []
        seen_addresses = set()

        logger.info(f"Starting token discovery (HotScanner + {len(self.sources)} sources)...")

        # --- Step 0: Real-time WebSocket sources (highest priority) ---
        for src_name, src_obj, priority in [
            ("event_proxy",        self.event_proxy_source,  25),
            ("migration_monitor",  self.migration_source,    20),
            ("meteora_scanner",    self.meteora_source,      18),
            ("pumpfun_ws",         self.pumpfun_source,      15),
        ]:
            if src_obj is None:
                continue
            try:
                ws_tokens = src_obj.fetch()
                added = 0
                for token in ws_tokens:
                    address = token.get('address', '').lower()
                    if address and address not in seen_addresses:
                        seen_addresses.add(address)
                        token.setdefault('source_priority', priority)
                        token.setdefault('discovered_at', datetime.now().isoformat())
                        all_tokens.append(token)
                        added += 1
                if added:
                    logger.info(f"✓ {src_name}: {added} tokens (priority: {priority})")
            except Exception as exc:
                logger.error(f"✗ {src_name} failed: {exc}")

        # --- Step 1: DexScreener HotScanner (primary REST source) ---
        try:
            hot_tokens = self.dex_hot_scanner.fetch()
            for token in hot_tokens:
                address = token.get('address', '').lower()
                if address and address not in seen_addresses:
                    seen_addresses.add(address)
                    all_tokens.append(token)
            logger.info(f"✓ dex_hot_scanner: {len(hot_tokens)} tokens (priority: 10)")
        except Exception as exc:
            logger.error(f"✗ dex_hot_scanner failed: {exc}")

        # --- Step 2: Supplemental sources via thread pool ---
        sorted_sources = sorted(
            self.sources.items(),
            key=lambda x: x[1].priority,
            reverse=True,
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

        # Sort: HotScanner tokens first (by dex_hotness_score), then by source priority + volume
        all_tokens.sort(key=lambda x: (
            -x.get('dex_hotness_score', 0),      # Primary: DexScreener hotness (0-100)
            -x.get('source_priority', 0),          # Secondary: source priority
            -x.get('memecoin_score', 0),           # Tertiary: memecoin score
            -x.get('daily_volume_usd', 0),         # Last resort: volume
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

                txns_h1 = pair.get('txns', {}).get('h1', {})
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
                    'source_raw': 'dexscreener',
                    'buys_1h': int(txns_h1.get('buys', 0)),
                    'sells_1h': int(txns_h1.get('sells', 0)),
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
