# bonding_curve_analyzer.py - Pump.fun Bonding Curve Analysis
"""
Analyzes Pump.fun token bonding curves for optimal entry/exit:
- Bonding curve progress (% to Raydium graduation)
- Buy/sell pressure on curve
- Graduation likelihood prediction
- Optimal entry timing
- Rug detection (curve manipulation)

Pump.fun tokens start on a bonding curve and "graduate" to Raydium
when the curve fills up (hits market cap target). This analyzer
helps identify tokens likely to graduate successfully.
"""

import logging
import requests
import time
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BondingCurveMetrics:
    """Bonding curve analysis for Pump.fun token"""
    is_pumpfun: bool
    curve_progress: float  # 0-100% progress to graduation
    curve_position: str  # "EARLY", "MID", "LATE", "GRADUATED"
    market_cap_current: float
    market_cap_target: float  # Target for Raydium graduation
    liquidity_sol: float
    holders_count: int
    graduation_likelihood: str  # "VERY_HIGH", "HIGH", "MEDIUM", "LOW", "VERY_LOW"
    graduation_time_estimate: Optional[float]  # Hours until estimated graduation
    buy_pressure: float  # 0-1 score
    sell_pressure: float  # 0-1 score
    dev_holdings_percent: float
    king_of_hill: bool  # Is this currently trending on Pump.fun
    rug_risk: str  # "NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"
    rug_indicators: List[str]
    strengths: List[str]
    warnings: List[str]


class BondingCurveAnalyzer:
    """
    Analyze Pump.fun bonding curves for trading decisions

    Pump.fun mechanics:
    - Tokens launch on bonding curve
    - As people buy, price increases along curve
    - When market cap hits ~$69k, graduates to Raydium
    - Post-graduation often sees 2-5x pump from liquidity
    """

    # Pump.fun constants
    GRADUATION_TARGET_SOL = 85  # ~85 SOL in curve = graduation
    GRADUATION_TARGET_MCAP = 69000  # ~$69k market cap
    OPTIMAL_ENTRY_MIN_PROGRESS = 30  # 30% curve progress
    OPTIMAL_ENTRY_MAX_PROGRESS = 75  # 75% curve progress
    HIGH_GRADUATION_THRESHOLD = 60  # 60%+ = likely to graduate

    _CACHE_MAX_SIZE = 200

    def __init__(self):
        self.cache = {}  # Token -> (timestamp, metrics)
        self.cache_ttl = 60  # 1 minute cache (bonding curves move fast)

        # PumpPortal API endpoint
        self.pumpportal_base = "https://pumpportal.fun/api"

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1  # 1 second between requests

    @contextmanager
    def _get_session(self):
        """Context manager for requests session"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
        try:
            yield session
        finally:
            session.close()

    def analyze_bonding_curve(
        self,
        token_address: str,
        token_data: Dict = None
    ) -> BondingCurveMetrics:
        """
        Analyze bonding curve metrics for a Pump.fun token

        Args:
            token_address: Solana token address
            token_data: Optional token data from discovery

        Returns:
            BondingCurveMetrics with comprehensive analysis
        """
        try:
            # Check cache
            if token_address in self.cache:
                timestamp, metrics = self.cache[token_address]
                if time.time() - timestamp < self.cache_ttl:
                    return metrics

            # Check if this is a Pump.fun token
            is_pumpfun = self._is_pumpfun_token(token_address, token_data)

            if not is_pumpfun:
                return self._non_pumpfun_metrics()

            # Get bonding curve data
            curve_data = self._get_curve_data(token_address)

            if not curve_data:
                return self._empty_metrics()

            # Calculate curve progress
            curve_progress = self._calculate_curve_progress(curve_data)

            # Determine curve position
            curve_position = self._get_curve_position(curve_progress)

            # Get current metrics
            market_cap_current = curve_data.get('market_cap', 0)
            market_cap_target = self.GRADUATION_TARGET_MCAP
            liquidity_sol = curve_data.get('liquidity_sol', 0)
            holders_count = curve_data.get('holders', 0)

            # Calculate graduation likelihood
            graduation_likelihood = self._calculate_graduation_likelihood(
                curve_progress, curve_data
            )

            # Estimate time to graduation
            graduation_time = self._estimate_graduation_time(curve_data)

            # Analyze buy/sell pressure
            buy_pressure = curve_data.get('buy_pressure', 0.5)
            sell_pressure = curve_data.get('sell_pressure', 0.5)

            # Check dev holdings
            dev_holdings = curve_data.get('dev_holdings_percent', 0)

            # Check if trending (King of the Hill)
            king_of_hill = curve_data.get('trending', False)

            # Analyze rug risk
            rug_risk, rug_indicators = self._analyze_rug_risk(curve_data)

            # Compile strengths and warnings
            strengths = []
            warnings = []

            # Curve position analysis
            if 30 <= curve_progress <= 75:
                strengths.append(f"🎯 Optimal entry zone ({curve_progress:.0f}% curve)")
            elif curve_progress > 90:
                strengths.append(f"🚀 Near graduation ({curve_progress:.0f}% curve)")
            elif curve_progress < 10:
                warnings.append(f"⚠️ Very early ({curve_progress:.0f}% curve)")

            # Graduation likelihood
            if graduation_likelihood in ["VERY_HIGH", "HIGH"]:
                strengths.append(f"✅ {graduation_likelihood} graduation chance")
            elif graduation_likelihood in ["VERY_LOW", "LOW"]:
                warnings.append(f"⚠️ {graduation_likelihood} graduation chance")

            # Buy pressure
            if buy_pressure > 0.7:
                strengths.append(f"🔥 Strong buy pressure ({buy_pressure:.2f})")
            elif sell_pressure > 0.7:
                warnings.append(f"⚠️ High sell pressure ({sell_pressure:.2f})")

            # Trending
            if king_of_hill:
                strengths.append("👑 Trending on Pump.fun (King of Hill)")

            # Dev holdings
            if dev_holdings > 20:
                warnings.append(f"⚠️ Dev holds {dev_holdings:.0f}% of supply")

            # Rug risk
            if rug_risk in ["HIGH", "CRITICAL"]:
                warnings.extend(rug_indicators)

            metrics = BondingCurveMetrics(
                is_pumpfun=True,
                curve_progress=curve_progress,
                curve_position=curve_position,
                market_cap_current=market_cap_current,
                market_cap_target=market_cap_target,
                liquidity_sol=liquidity_sol,
                holders_count=holders_count,
                graduation_likelihood=graduation_likelihood,
                graduation_time_estimate=graduation_time,
                buy_pressure=buy_pressure,
                sell_pressure=sell_pressure,
                dev_holdings_percent=dev_holdings,
                king_of_hill=king_of_hill,
                rug_risk=rug_risk,
                rug_indicators=rug_indicators,
                strengths=strengths,
                warnings=warnings
            )

            # Cache result (evict oldest if over limit)
            self.cache[token_address] = (time.time(), metrics)
            if len(self.cache) > self._CACHE_MAX_SIZE:
                oldest = min(self.cache, key=lambda k: self.cache[k][0])
                del self.cache[oldest]

            return metrics

        except Exception as e:
            logger.error(f"Error analyzing bonding curve for {token_address[:8]}: {e}")
            return self._empty_metrics()

    def _is_pumpfun_token(self, token_address: str, token_data: Dict = None) -> bool:
        """Check if token is from Pump.fun"""
        try:
            # Check token data for Pump.fun indicators
            if token_data:
                # Check source
                if 'source' in token_data and 'pump' in token_data['source'].lower():
                    return True

                # Check if bonding curve info present
                if 'bonding_curve' in token_data or 'curve_progress' in token_data:
                    return True

                # Check DEX - Pump.fun tokens start on Pump.fun DEX
                if 'dex_id' in token_data and token_data['dex_id'] == 'pump':
                    return True

            # Try to fetch from PumpPortal
            try:
                self._rate_limit()

                with self._get_session() as session:
                    url = f"{self.pumpportal_base}/data/{token_address}"
                    response = session.get(url, timeout=5)

                    if response.status_code == 200:
                        data = response.json()
                        # If we get valid data back, it's a Pump.fun token
                        return data is not None and isinstance(data, dict)

            except Exception as e:
                logger.debug(f"PumpPortal check failed: {e}")

            return False

        except Exception as e:
            logger.debug(f"Error checking if Pump.fun token: {e}")
            return False

    def _get_curve_data(self, token_address: str) -> Optional[Dict]:
        """Get bonding curve data from PumpPortal"""
        try:
            self._rate_limit()

            with self._get_session() as session:
                # Get token data from PumpPortal
                url = f"{self.pumpportal_base}/data/{token_address}"
                response = session.get(url, timeout=10)

                if response.status_code != 200:
                    logger.debug(f"PumpPortal returned {response.status_code}")
                    return None

                data = response.json()

                if not data:
                    return None

                # Extract relevant metrics
                curve_data = {
                    'market_cap': float(data.get('market_cap', 0)),
                    'liquidity_sol': float(data.get('liquidity', 0)),
                    'holders': int(data.get('holder_count', 0)),
                    'volume_24h': float(data.get('volume_24h', 0)),
                    'buys_24h': int(data.get('buys', 0)),
                    'sells_24h': int(data.get('sells', 0)),
                    'price_change_24h': float(data.get('price_change_24h', 0)),
                    'dev_holdings_percent': float(data.get('dev_wallet_pct', 0)) * 100,
                    'complete': data.get('complete', False),  # Graduated?
                    'trending': data.get('king_of_the_hill', False),
                    'created_timestamp': data.get('created_timestamp', 0),
                }

                # Calculate buy/sell pressure
                total_trades = curve_data['buys_24h'] + curve_data['sells_24h']
                if total_trades > 0:
                    curve_data['buy_pressure'] = curve_data['buys_24h'] / total_trades
                    curve_data['sell_pressure'] = curve_data['sells_24h'] / total_trades
                else:
                    curve_data['buy_pressure'] = 0.5
                    curve_data['sell_pressure'] = 0.5

                return curve_data

        except Exception as e:
            logger.debug(f"Error fetching curve data: {e}")
            return None

    def _calculate_curve_progress(self, curve_data: Dict) -> float:
        """Calculate percentage progress along bonding curve"""
        try:
            # If already graduated, return 100%
            if curve_data.get('complete', False):
                return 100.0

            # Calculate based on market cap
            market_cap = curve_data.get('market_cap', 0)
            progress = (market_cap / self.GRADUATION_TARGET_MCAP) * 100

            # Clamp to 0-100
            return max(0.0, min(100.0, progress))

        except Exception as e:
            logger.debug(f"Error calculating curve progress: {e}")
            return 0.0

    def _get_curve_position(self, curve_progress: float) -> str:
        """Determine curve position category"""
        if curve_progress >= 100:
            return "GRADUATED"
        elif curve_progress >= 75:
            return "LATE"
        elif curve_progress >= 30:
            return "MID"
        else:
            return "EARLY"

    def _calculate_graduation_likelihood(self, curve_progress: float, curve_data: Dict) -> str:
        """
        Calculate likelihood of graduating to Raydium

        Factors:
        - Curve progress
        - Holder count
        - Buy pressure
        - Volume trend
        """
        try:
            score = 0

            # Curve progress (40% weight)
            if curve_progress >= 80:
                score += 4
            elif curve_progress >= 60:
                score += 3
            elif curve_progress >= 40:
                score += 2
            elif curve_progress >= 20:
                score += 1

            # Holder count (20% weight)
            holders = curve_data.get('holders', 0)
            if holders >= 500:
                score += 2
            elif holders >= 200:
                score += 1.5
            elif holders >= 100:
                score += 1

            # Buy pressure (20% weight)
            buy_pressure = curve_data.get('buy_pressure', 0.5)
            if buy_pressure >= 0.8:
                score += 2
            elif buy_pressure >= 0.6:
                score += 1.5
            elif buy_pressure >= 0.5:
                score += 1

            # Volume (20% weight)
            volume_24h = curve_data.get('volume_24h', 0)
            if volume_24h >= 100000:  # $100k+
                score += 2
            elif volume_24h >= 50000:
                score += 1.5
            elif volume_24h >= 10000:
                score += 1

            # Total score: 0-10
            if score >= 8:
                return "VERY_HIGH"
            elif score >= 6:
                return "HIGH"
            elif score >= 4:
                return "MEDIUM"
            elif score >= 2:
                return "LOW"
            else:
                return "VERY_LOW"

        except Exception as e:
            logger.debug(f"Error calculating graduation likelihood: {e}")
            return "MEDIUM"

    def _estimate_graduation_time(self, curve_data: Dict) -> Optional[float]:
        """
        Estimate hours until graduation based on current velocity

        Returns hours, or None if can't estimate
        """
        try:
            # If already graduated, return 0
            if curve_data.get('complete', False):
                return 0.0

            market_cap_current = curve_data.get('market_cap', 0)
            remaining = self.GRADUATION_TARGET_MCAP - market_cap_current

            if remaining <= 0:
                return 0.0

            # Calculate velocity based on recent volume
            volume_24h = curve_data.get('volume_24h', 0)

            if volume_24h == 0:
                return None  # Can't estimate

            # Assume 50% of volume contributes to mcap growth (rough estimate)
            mcap_growth_per_hour = (volume_24h * 0.5) / 24

            if mcap_growth_per_hour == 0:
                return None

            hours_to_graduation = remaining / mcap_growth_per_hour

            # Clamp to reasonable range
            if hours_to_graduation > 168:  # 1 week
                return None  # Too far out, unreliable

            return hours_to_graduation

        except Exception as e:
            logger.debug(f"Error estimating graduation time: {e}")
            return None

    def _analyze_rug_risk(self, curve_data: Dict) -> Tuple[str, List[str]]:
        """
        Analyze rug pull risk for bonding curve token

        Returns:
            (risk_level, indicators)
        """
        try:
            indicators = []
            risk_score = 0

            # Dev holdings too high
            dev_holdings = curve_data.get('dev_holdings_percent', 0)
            if dev_holdings > 30:
                indicators.append(f"🚨 Dev holds {dev_holdings:.0f}% (rug risk)")
                risk_score += 3
            elif dev_holdings > 20:
                indicators.append(f"⚠️ Dev holds {dev_holdings:.0f}%")
                risk_score += 2

            # High sell pressure
            sell_pressure = curve_data.get('sell_pressure', 0)
            if sell_pressure > 0.8:
                indicators.append("🚨 Very high sell pressure")
                risk_score += 2

            # Low holder count relative to progress
            market_cap = curve_data.get('market_cap', 0)
            holders = curve_data.get('holders', 0)

            if market_cap > 30000 and holders < 50:
                indicators.append("⚠️ Low holder count for market cap")
                risk_score += 1

            # Very fast price movement (potential pump & dump)
            price_change = curve_data.get('price_change_24h', 0)
            if price_change > 500:  # 500%+ in 24h
                indicators.append(f"⚠️ Extreme price pump (+{price_change:.0f}%)")
                risk_score += 1

            # Determine risk level
            if risk_score >= 5:
                risk_level = "CRITICAL"
            elif risk_score >= 3:
                risk_level = "HIGH"
            elif risk_score >= 1:
                risk_level = "MEDIUM"
            elif risk_score > 0:
                risk_level = "LOW"
            else:
                risk_level = "NONE"

            return risk_level, indicators

        except Exception as e:
            logger.debug(f"Error analyzing rug risk: {e}")
            return "MEDIUM", ["Risk analysis unavailable"]

    def should_trade_based_on_curve(self, metrics: BondingCurveMetrics) -> Tuple[bool, str]:
        """
        Determine if token should be traded based on bonding curve

        Returns:
            (should_trade: bool, reason: str)
        """
        try:
            # Not a Pump.fun token - defer to other analyzers
            if not metrics.is_pumpfun:
                return True, "Not a Pump.fun token"

            # Already graduated - different strategy
            if metrics.curve_position == "GRADUATED":
                return True, "Already graduated to Raydium"

            # Critical rug risk - reject
            if metrics.rug_risk == "CRITICAL":
                return False, f"CRITICAL rug risk: {', '.join(metrics.rug_indicators)}"

            # High rug risk - reject
            if metrics.rug_risk == "HIGH":
                return False, f"HIGH rug risk: {', '.join(metrics.rug_indicators)}"

            # Very low graduation chance - reject
            if metrics.graduation_likelihood == "VERY_LOW":
                return False, f"Very low graduation chance ({metrics.curve_progress:.0f}% curve)"

            # Optimal entry zone with good metrics
            if (self.OPTIMAL_ENTRY_MIN_PROGRESS <= metrics.curve_progress <= self.OPTIMAL_ENTRY_MAX_PROGRESS
                and metrics.graduation_likelihood in ["HIGH", "VERY_HIGH"]
                and metrics.buy_pressure > 0.5):
                return True, f"Optimal entry: {metrics.curve_progress:.0f}% curve, {metrics.graduation_likelihood} graduation chance"

            # Near graduation with strong momentum
            if (metrics.curve_progress > 80
                and metrics.buy_pressure > 0.6
                and metrics.graduation_likelihood in ["HIGH", "VERY_HIGH"]):
                return True, f"Near graduation: {metrics.curve_progress:.0f}% curve, strong momentum"

            # Trending + good progress
            if (metrics.king_of_hill
                and metrics.curve_progress > 40
                and metrics.buy_pressure > 0.5):
                return True, f"Trending on Pump.fun: {metrics.curve_progress:.0f}% curve"

            # Default: needs more analysis
            return False, f"Curve metrics unclear: {metrics.curve_progress:.0f}% progress, {metrics.graduation_likelihood} graduation chance"

        except Exception as e:
            logger.debug(f"Error evaluating curve metrics: {e}")
            return True, "Curve analysis unavailable - proceeding"

    def _rate_limit(self):
        """Simple rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _empty_metrics(self) -> BondingCurveMetrics:
        """Return empty metrics when data unavailable"""
        return BondingCurveMetrics(
            is_pumpfun=True,
            curve_progress=0.0,
            curve_position="UNKNOWN",
            market_cap_current=0.0,
            market_cap_target=self.GRADUATION_TARGET_MCAP,
            liquidity_sol=0.0,
            holders_count=0,
            graduation_likelihood="MEDIUM",
            graduation_time_estimate=None,
            buy_pressure=0.5,
            sell_pressure=0.5,
            dev_holdings_percent=0.0,
            king_of_hill=False,
            rug_risk="MEDIUM",
            rug_indicators=["Data unavailable"],
            strengths=[],
            warnings=["⚠️ Bonding curve data unavailable"]
        )

    def _non_pumpfun_metrics(self) -> BondingCurveMetrics:
        """Return metrics indicating token is not from Pump.fun"""
        return BondingCurveMetrics(
            is_pumpfun=False,
            curve_progress=0.0,
            curve_position="N/A",
            market_cap_current=0.0,
            market_cap_target=0.0,
            liquidity_sol=0.0,
            holders_count=0,
            graduation_likelihood="N/A",
            graduation_time_estimate=None,
            buy_pressure=0.5,
            sell_pressure=0.5,
            dev_holdings_percent=0.0,
            king_of_hill=False,
            rug_risk="NONE",
            rug_indicators=[],
            strengths=[],
            warnings=[]
        )


# Quick helper function
def quick_curve_check(token_address: str, token_data: Dict = None) -> bool:
    """
    Quick bonding curve check

    Returns True if should trade, False if should reject
    """
    try:
        analyzer = BondingCurveAnalyzer()
        metrics = analyzer.analyze_bonding_curve(token_address, token_data)

        # Not Pump.fun - allow other analyzers to decide
        if not metrics.is_pumpfun:
            return True

        should_trade, _ = analyzer.should_trade_based_on_curve(metrics)
        return should_trade

    except Exception:
        return True  # On error, don't block trade
