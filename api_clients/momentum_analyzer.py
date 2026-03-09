# momentum_analyzer.py - Buy/Sell Pressure & Momentum Analysis
"""
Analyzes trading momentum and buy/sell pressure for memecoins:
- Buy vs Sell ratio (recent activity)
- Consecutive buy/sell streaks (FOMO detection)
- Average trade sizes
- Unique buyer/seller counts
"""

import logging
import requests
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager
from datetime import datetime, timezone
from collections import deque

logger = logging.getLogger(__name__)


class MomentumAnalyzer:
    """Analyze buy/sell pressure and trading momentum"""

    _CACHE_MAX_SIZE = 200

    def __init__(self):
        self.dexscreener_base = "https://api.dexscreener.com/latest/dex"
        self.cache = {}  # Cache momentum data
        self.cache_ttl = 60  # 1 minute cache

    @contextmanager
    def _get_session(self):
        """Context manager for session - ensures cleanup"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        })
        try:
            yield session
        finally:
            session.close()

    def analyze_momentum(self, token_address: str) -> Dict:
        """
        Comprehensive momentum analysis

        Returns dict with:
        - buy_sell_ratio: float (>1 = more buying, <1 = more selling)
        - momentum_score: float (0-1, higher = stronger bullish momentum)
        - momentum_direction: str ("BULLISH", "BEARISH", "NEUTRAL")
        - consecutive_buys: int
        - consecutive_sells: int
        - unique_buyers_15m: int
        - unique_sellers_15m: int
        - fomo_detected: bool
        - dump_detected: bool
        """
        try:
            # Check cache
            cache_key = f"momentum_{token_address}"
            if cache_key in self.cache:
                cached = self.cache[cache_key]
                if (datetime.now().timestamp() - cached['timestamp']) < self.cache_ttl:
                    return cached['data']

            # Get transaction data
            txn_data = self._get_transaction_data(token_address)

            if not txn_data:
                return self._empty_momentum()

            # Calculate metrics
            result = {
                'buy_sell_ratio': txn_data['buy_sell_ratio'],
                'momentum_score': txn_data['momentum_score'],
                'momentum_direction': txn_data['direction'],
                'consecutive_buys': txn_data['consecutive_buys'],
                'consecutive_sells': txn_data['consecutive_sells'],
                'unique_buyers_15m': txn_data['unique_buyers'],
                'unique_sellers_15m': txn_data['unique_sellers'],
                'fomo_detected': txn_data['fomo_detected'],
                'dump_detected': txn_data['dump_detected'],
                'buy_volume_15m': txn_data['buy_volume'],
                'sell_volume_15m': txn_data['sell_volume'],
                'total_trades_15m': txn_data['total_trades'],
                'avg_buy_size': txn_data['avg_buy_size'],
                'avg_sell_size': txn_data['avg_sell_size']
            }

            # Cache result (evict oldest entries if over limit)
            self.cache[cache_key] = {
                'timestamp': datetime.now().timestamp(),
                'data': result
            }
            if len(self.cache) > self._CACHE_MAX_SIZE:
                oldest = min(self.cache, key=lambda k: self.cache[k]['timestamp'])
                del self.cache[oldest]

            return result

        except Exception as e:
            logger.error(f"Error analyzing momentum for {token_address}: {e}")
            return self._empty_momentum()

    def _get_transaction_data(self, token_address: str) -> Optional[Dict]:
        """Get recent transaction data from DexScreener"""
        try:
            with self._get_session() as session:
                # Get token pairs first
                url = f"{self.dexscreener_base}/tokens/{token_address}"
                response = session.get(url, timeout=10)

                if response.status_code != 200:
                    logger.debug(f"DexScreener returned {response.status_code}")
                    return None

                data = response.json()
                pairs = data.get('pairs', [])

                if not pairs:
                    logger.debug(f"No pairs found for {token_address}")
                    return None

                # Get the most liquid pair
                best_pair = max(pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0)))
                pair_address = best_pair.get('pairAddress')

                # Get transaction data for this pair
                txns = best_pair.get('txns', {})

                # Parse transaction counts
                buys_1h = txns.get('h1', {}).get('buys', 0)
                sells_1h = txns.get('h1', {}).get('sells', 0)
                buys_5m = txns.get('m5', {}).get('buys', 0)
                sells_5m = txns.get('m5', {}).get('sells', 0)

                # Get volume data
                volume = best_pair.get('volume', {})
                volume_5m = float(volume.get('m5', 0))
                volume_1h = float(volume.get('h1', 0))

                # Calculate buy/sell volumes (approximate)
                total_5m_txns = buys_5m + sells_5m
                if total_5m_txns > 0:
                    buy_ratio_5m = buys_5m / total_5m_txns
                    buy_volume = volume_5m * buy_ratio_5m
                    sell_volume = volume_5m * (1 - buy_ratio_5m)
                else:
                    buy_volume = 0
                    sell_volume = 0

                # Calculate buy/sell ratio
                if sells_5m > 0:
                    buy_sell_ratio = buys_5m / sells_5m
                else:
                    buy_sell_ratio = 999 if buys_5m > 0 else 1.0

                # Detect consecutive buys (FOMO indicator)
                # This is an approximation - real impl would parse actual tx history
                consecutive_buys = 0
                consecutive_sells = 0

                if buys_5m > sells_5m * 3:  # 3x more buys
                    consecutive_buys = min(buys_5m, 10)  # Cap at 10
                if sells_5m > buys_5m * 3:  # 3x more sells
                    consecutive_sells = min(sells_5m, 10)

                # FOMO detection: Many buys, increasing volume
                fomo_detected = (
                    buy_sell_ratio > 3 and
                    buys_5m >= 10 and
                    consecutive_buys >= 5
                )

                # Dump detection: Many sells, decreasing price
                price_change_5m = float(best_pair.get('priceChange', {}).get('m5', 0))
                dump_detected = (
                    buy_sell_ratio < 0.5 and
                    sells_5m >= 10 and
                    price_change_5m < -10
                )

                # Calculate momentum score (0-1)
                momentum_score = self._calculate_momentum_score(
                    buy_sell_ratio,
                    buys_5m,
                    sells_5m,
                    price_change_5m,
                    volume_5m
                )

                # Determine direction
                if momentum_score >= 0.7:
                    direction = "BULLISH"
                elif momentum_score <= 0.3:
                    direction = "BEARISH"
                else:
                    direction = "NEUTRAL"

                # Average trade sizes (approximate)
                avg_buy_size = (buy_volume / buys_5m) if buys_5m > 0 else 0
                avg_sell_size = (sell_volume / sells_5m) if sells_5m > 0 else 0

                return {
                    'buy_sell_ratio': buy_sell_ratio,
                    'momentum_score': momentum_score,
                    'direction': direction,
                    'consecutive_buys': consecutive_buys,
                    'consecutive_sells': consecutive_sells,
                    'unique_buyers': buys_5m,  # Approximation
                    'unique_sellers': sells_5m,  # Approximation
                    'fomo_detected': fomo_detected,
                    'dump_detected': dump_detected,
                    'buy_volume': buy_volume,
                    'sell_volume': sell_volume,
                    'total_trades': buys_5m + sells_5m,
                    'avg_buy_size': avg_buy_size,
                    'avg_sell_size': avg_sell_size
                }

        except Exception as e:
            logger.error(f"Error getting transaction data: {e}")
            return None

    def _calculate_momentum_score(
        self,
        buy_sell_ratio: float,
        buys: int,
        sells: int,
        price_change: float,
        volume: float
    ) -> float:
        """
        Calculate momentum score (0-1)

        Factors:
        - Buy/sell ratio (40%)
        - Price change (30%)
        - Trade count (20%)
        - Volume (10%)
        """
        score = 0.5  # Neutral baseline

        # Buy/sell ratio contribution (0-0.4)
        if buy_sell_ratio >= 3:
            ratio_score = 0.4
        elif buy_sell_ratio >= 2:
            ratio_score = 0.3
        elif buy_sell_ratio >= 1.5:
            ratio_score = 0.2
        elif buy_sell_ratio >= 1:
            ratio_score = 0.1
        elif buy_sell_ratio >= 0.5:
            ratio_score = -0.1
        else:
            ratio_score = -0.4

        score += ratio_score

        # Price change contribution (0-0.3)
        if price_change > 20:
            price_score = 0.3
        elif price_change > 10:
            price_score = 0.2
        elif price_change > 5:
            price_score = 0.1
        elif price_change > -5:
            price_score = 0
        elif price_change > -10:
            price_score = -0.1
        else:
            price_score = -0.3

        score += price_score

        # Trade count contribution (0-0.2)
        total_trades = buys + sells
        if total_trades >= 50:
            trade_score = 0.2
        elif total_trades >= 30:
            trade_score = 0.15
        elif total_trades >= 20:
            trade_score = 0.1
        elif total_trades >= 10:
            trade_score = 0.05
        else:
            trade_score = 0

        score += trade_score

        # Volume contribution (0-0.1)
        if volume >= 100000:  # $100k+ in 5min
            volume_score = 0.1
        elif volume >= 50000:
            volume_score = 0.05
        else:
            volume_score = 0

        score += volume_score

        # Clamp to 0-1
        return max(0, min(1, score))

    def _empty_momentum(self) -> Dict:
        """Return empty momentum data"""
        return {
            'buy_sell_ratio': 1.0,
            'momentum_score': 0.5,
            'momentum_direction': "UNKNOWN",
            'consecutive_buys': 0,
            'consecutive_sells': 0,
            'unique_buyers_15m': 0,
            'unique_sellers_15m': 0,
            'fomo_detected': False,
            'dump_detected': False,
            'buy_volume_15m': 0,
            'sell_volume_15m': 0,
            'total_trades_15m': 0,
            'avg_buy_size': 0,
            'avg_sell_size': 0
        }

    def get_momentum_signal(self, token_address: str) -> Tuple[str, float, str]:
        """
        Get simple momentum signal

        Returns:
            (signal: "BUY"|"SELL"|"HOLD", confidence: 0-1, reason: str)
        """
        momentum = self.analyze_momentum(token_address)

        if momentum['fomo_detected']:
            return "BUY", 0.9, f"FOMO detected: {momentum['consecutive_buys']} consecutive buys, ratio {momentum['buy_sell_ratio']:.1f}x"

        if momentum['dump_detected']:
            return "SELL", 0.9, f"Dump detected: {momentum['consecutive_sells']} consecutive sells"

        if momentum['momentum_score'] >= 0.75:
            return "BUY", momentum['momentum_score'], f"Strong bullish momentum (score: {momentum['momentum_score']:.2f})"

        if momentum['momentum_score'] <= 0.25:
            return "SELL", (1 - momentum['momentum_score']), f"Strong bearish momentum (score: {momentum['momentum_score']:.2f})"

        return "HOLD", 0.5, f"Neutral momentum (score: {momentum['momentum_score']:.2f})"
