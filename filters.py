# filters.py - Enhanced Memecoin Filtering System

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Result of token filtering"""

    passed: bool
    reasons: List[str]
    score: float = 0.0
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


def passes_filters(token_info: Dict[str, Any]) -> bool:
    """
    Quick filter for memecoin discovery - designed to be INCLUSIVE
    This is the first-pass filter to catch interesting tokens
    """
    try:
        # Extract basic metrics
        volume = float(token_info.get("daily_volume_usd", 0))
        age_hours = float(token_info.get("age_hours", 9999))
        holders = int(token_info.get("holder_count", 0))
        liquidity = float(token_info.get("liquidity_usd", 0))
        price_change = float(token_info.get("price_change_24h", 0))
        market_cap = float(token_info.get("market_cap", 0))

        # MEMECOIN-OPTIMIZED CRITERIA (very inclusive)

        # 1. AGE: Focus on newer tokens (but not too restrictive)
        age_ok = age_hours < 720  # 30 days (much more inclusive)

        # 2. ACTIVITY: Multiple ways to show activity
        has_volume = volume >= 500  # Very low minimum volume
        has_price_action = abs(price_change) > 5  # 5%+ price movement
        has_decent_volume = volume >= 10000  # $10k+ volume

        # Token shows activity if ANY of these are true
        activity_ok = has_volume or has_price_action or has_decent_volume

        # 3. AVOID OBVIOUS SCAMS/RUGS
        not_suspicious = True

        # Very high volume with very low market cap = suspicious
        if volume > 1000000 and market_cap < 50000 and market_cap > 0:
            not_suspicious = False

        # 4. MINIMUM VIABILITY
        # Either has some liquidity OR is very new (might not have liquidity data yet)
        viable = liquidity >= 1000 or liquidity == 0 or age_hours < 6

        # 5. SIZE FILTERS (very broad range)
        # Avoid tokens that are too big (already mooned) or obvious penny stocks
        size_ok = True
        if market_cap > 100_000_000:  # Over $100M = too big
            size_ok = False
        if volume > 50_000_000:  # Over $50M daily volume = too mainstream
            size_ok = False

        # 6. SOURCE-BASED BONUSES
        source_bonus = False
        source = token_info.get("discovery_source", "").lower()
        if any(keyword in source for keyword in ["new", "trending", "pump"]):
            source_bonus = True

        # PASS CONDITIONS (very inclusive)
        basic_checks = age_ok and not_suspicious and viable and size_ok

        # Pass if basic checks AND (has activity OR source bonus)
        return basic_checks and (activity_ok or source_bonus)

    except (ValueError, TypeError, KeyError):
        # If any data is malformed, be conservative but don't reject
        return token_info.get("discovery_source") in ["pumpfun", "dexscreener_new"]


class TokenFilter:
    """Advanced filtering system for comprehensive token analysis"""

    def __init__(self):
        # Comprehensive filter categories
        self.filters = {
            "age_and_timing": self._check_age_and_timing,
            "activity_and_momentum": self._check_activity_and_momentum,
            "liquidity_and_tradability": self._check_liquidity_and_tradability,
            "size_and_valuation": self._check_size_and_valuation,
            "source_and_discovery": self._check_source_and_discovery,
            "risk_and_safety": self._check_risk_and_safety,
        }

        # Adjusted weights for memecoin trading
        self.filter_weights = {
            "age_and_timing": 0.25,  # When was it created/discovered
            "activity_and_momentum": 0.30,  # Volume, price action, buzz
            "liquidity_and_tradability": 0.15,  # Can we actually trade it
            "size_and_valuation": 0.10,  # Market cap considerations
            "source_and_discovery": 0.15,  # Where did we find it
            "risk_and_safety": 0.05,  # Basic safety checks
        }

    def filter_token(
        self, token_info: Dict[str, Any], strict_mode: bool = False
    ) -> FilterResult:
        """Comprehensive token filtering with detailed scoring"""
        reasons = []
        warnings = []
        scores = {}

        # Run all filter categories
        for filter_name, filter_func in self.filters.items():
            try:
                result = filter_func(token_info)
                scores[filter_name] = result["score"]

                if not result["passed"]:
                    reasons.append(f"{filter_name}: {result['reason']}")
                    if strict_mode:
                        return FilterResult(
                            passed=False, reasons=reasons, score=0.0, warnings=warnings
                        )

                if result.get("warning"):
                    warnings.append(f"{filter_name}: {result['warning']}")

            except Exception as e:
                logger.error(f"Error in filter {filter_name}: {str(e)}")
                scores[filter_name] = 0.0

        # Calculate weighted total score
        total_score = sum(
            scores.get(name, 0) * weight for name, weight in self.filter_weights.items()
        )

        # Memecoin-friendly passing criteria
        min_score = 0.35 if strict_mode else 0.25  # Lower threshold for inclusivity
        passed = len(reasons) == 0 and total_score >= min_score

        return FilterResult(
            passed=passed, reasons=reasons, score=total_score, warnings=warnings
        )

    def _check_age_and_timing(self, token_info: Dict) -> Dict:
        """Check token age and timing factors"""
        age_hours = float(token_info.get("age_hours", 9999))

        # Age scoring - newer is generally better for memecoins
        if age_hours < 1:  # Less than 1 hour
            score = 1.0
            reason = f"Very fresh: {age_hours:.1f}h old"
        elif age_hours < 6:  # Less than 6 hours
            score = 0.9
            reason = f"Fresh: {age_hours:.1f}h old"
        elif age_hours < 24:  # Less than 1 day
            score = 0.8
            reason = f"New: {age_hours:.1f}h old"
        elif age_hours < 72:  # Less than 3 days
            score = 0.6
            reason = f"Recent: {age_hours:.1f}h old"
        elif age_hours < 168:  # Less than 1 week
            score = 0.4
            reason = f"Week old: {age_hours:.1f}h old"
        elif age_hours < 720:  # Less than 1 month
            score = 0.2
            reason = f"Month old: {age_hours:.1f}h old"
        else:
            score = 0.0
            reason = f"Too old: {age_hours:.1f}h old"

        # Bonus for discovery timing
        discovery_time = token_info.get("discovered_at")
        if discovery_time:
            try:
                discovered = datetime.fromisoformat(discovery_time.replace("Z", ""))
                time_since_discovery = (
                    datetime.now() - discovered
                ).total_seconds() / 60
                if time_since_discovery < 5:  # Discovered in last 5 minutes
                    score *= 1.1  # 10% bonus
            except:
                pass

        return {
            "passed": age_hours < 720,  # 30 days max
            "reason": reason,
            "score": min(score, 1.0),
        }

    def _check_activity_and_momentum(self, token_info: Dict) -> Dict:
        """Check trading activity and price momentum"""
        volume = float(token_info.get("daily_volume_usd", 0))
        price_change = float(token_info.get("price_change_24h", 0))

        score = 0.0
        signals = []

        # Volume scoring
        if volume > 1_000_000:  # $1M+ volume
            score += 0.4
            signals.append(f"High volume: ${volume:,.0f}")
        elif volume > 100_000:  # $100k+ volume
            score += 0.3
            signals.append(f"Good volume: ${volume:,.0f}")
        elif volume > 10_000:  # $10k+ volume
            score += 0.2
            signals.append(f"Moderate volume: ${volume:,.0f}")
        elif volume > 1_000:  # $1k+ volume
            score += 0.1
            signals.append(f"Low volume: ${volume:,.0f}")
        else:
            signals.append("Very low volume")

        # Price momentum scoring
        abs_change = abs(price_change)
        if abs_change > 100:  # 100%+ movement
            score += 0.5
            signals.append(f"Explosive move: {price_change:+.1f}%")
        elif abs_change > 50:  # 50%+ movement
            score += 0.4
            signals.append(f"Strong move: {price_change:+.1f}%")
        elif abs_change > 20:  # 20%+ movement
            score += 0.3
            signals.append(f"Good move: {price_change:+.1f}%")
        elif abs_change > 10:  # 10%+ movement
            score += 0.2
            signals.append(f"Some move: {price_change:+.1f}%")
        elif abs_change > 5:  # 5%+ movement
            score += 0.1
            signals.append(f"Slight move: {price_change:+.1f}%")

        # Bonus for positive momentum
        if price_change > 0:
            score *= 1.1

        # Minimum activity requirement
        has_activity = volume > 500 or abs_change > 5

        return {
            "passed": has_activity,
            "reason": "; ".join(signals),
            "score": min(score, 1.0),
        }

    def _check_liquidity_and_tradability(self, token_info: Dict) -> Dict:
        """Check if token can be traded effectively"""
        liquidity = float(token_info.get("liquidity_usd", 0))
        volume = float(token_info.get("daily_volume_usd", 0))

        # Liquidity scoring
        if liquidity == 0:
            # Unknown liquidity - use volume as proxy
            if volume > 50000:  # High volume suggests good liquidity
                score = 0.7
                reason = "Unknown liquidity, high volume"
                warning = "Liquidity data missing"
            elif volume > 5000:
                score = 0.5
                reason = "Unknown liquidity, moderate volume"
                warning = "Liquidity data missing"
            else:
                score = 0.3
                reason = "Unknown liquidity, low volume"
                warning = "Liquidity and volume both low"
        else:
            # Known liquidity
            if liquidity > 500000:  # $500k+
                score = 1.0
                reason = f"Excellent liquidity: ${liquidity:,.0f}"
            elif liquidity > 100000:  # $100k+
                score = 0.8
                reason = f"Good liquidity: ${liquidity:,.0f}"
            elif liquidity > 20000:  # $20k+
                score = 0.6
                reason = f"Adequate liquidity: ${liquidity:,.0f}"
            elif liquidity > 5000:  # $5k+
                score = 0.4
                reason = f"Low liquidity: ${liquidity:,.0f}"
                warning = "Low liquidity may cause slippage"
            else:
                score = 0.2
                reason = f"Very low liquidity: ${liquidity:,.0f}"
                warning = "Very low liquidity - high slippage risk"

        # Minimum tradability check
        min_tradable = liquidity > 2000 or (liquidity == 0 and volume > 5000)

        result = {"passed": min_tradable, "reason": reason, "score": score}

        if "warning" in locals():
            result["warning"] = warning

        return result

    def _check_size_and_valuation(self, token_info: Dict) -> Dict:
        """Check market cap and valuation metrics"""
        market_cap = float(token_info.get("market_cap", 0))
        volume = float(token_info.get("daily_volume_usd", 0))

        if market_cap == 0:
            # Unknown market cap - use volume to estimate
            score = 0.5
            reason = "Unknown market cap"
            passed = True
        else:
            # Known market cap scoring
            if 10_000 <= market_cap <= 1_000_000:  # $10k - $1M sweet spot
                score = 1.0
                reason = f"Perfect size: ${market_cap:,.0f}"
            elif 1_000_000 < market_cap <= 10_000_000:  # $1M - $10M
                score = 0.8
                reason = f"Good size: ${market_cap:,.0f}"
            elif 10_000_000 < market_cap <= 50_000_000:  # $10M - $50M
                score = 0.5
                reason = f"Large size: ${market_cap:,.0f}"
            elif market_cap < 10_000:  # Under $10k
                score = 0.3
                reason = f"Very small: ${market_cap:,.0f}"
            else:  # Over $50M
                score = 0.1
                reason = f"Too large: ${market_cap:,.0f}"

            passed = market_cap < 100_000_000  # Under $100M

        # Volume/Market Cap ratio check
        if market_cap > 0 and volume > 0:
            vol_mcap_ratio = volume / market_cap
            if vol_mcap_ratio > 1.0:  # Daily volume > market cap
                result_warning = "Extremely high volume/mcap ratio - may be manipulated"
            elif vol_mcap_ratio > 0.5:
                score *= 1.1  # Bonus for high activity

        result = {"passed": passed, "reason": reason, "score": score}

        if "result_warning" in locals():
            result["warning"] = result_warning

        return result

    def _check_source_and_discovery(self, token_info: Dict) -> Dict:
        """Check discovery source and context"""
        source = token_info.get("discovery_source", "").lower()

        # Source reliability scoring
        if "pumpfun" in source and "new" in source:
            score = 1.0
            reason = "From Pump.fun new tokens - excellent"
        elif "pumpfun" in source:
            score = 0.9
            reason = "From Pump.fun - very good"
        elif "dexscreener" in source and "new" in source:
            score = 0.8
            reason = "From Dexscreener new - good"
        elif "trending" in source:
            score = 0.7
            reason = "From trending source - decent"
        elif "birdeye" in source or "jupiter" in source:
            score = 0.6
            reason = "From price aggregator - okay"
        elif "raydium" in source:
            score = 0.8
            reason = "From Raydium pools - good"
        else:
            score = 0.4
            reason = f"Unknown source: {source}"

        # Bonus for multiple discovery sources
        if token_info.get("seen_in_multiple_sources"):
            score *= 1.2
            reason += " (multiple sources)"

        return {
            "passed": True,  # All sources are acceptable
            "reason": reason,
            "score": min(score, 1.0),
        }

    def _check_risk_and_safety(self, token_info: Dict) -> Dict:
        """Basic safety and risk checks"""
        volume = float(token_info.get("daily_volume_usd", 0))
        market_cap = float(token_info.get("market_cap", 0))
        age_hours = float(token_info.get("age_hours", 9999))

        risk_flags = []
        score = 1.0  # Start with perfect score, deduct for risks

        # Volume/Market Cap manipulation check
        if market_cap > 0 and volume > 0:
            vol_mcap_ratio = volume / market_cap
            if vol_mcap_ratio > 2.0:  # Volume > 2x market cap
                risk_flags.append("Extremely high vol/mcap ratio")
                score -= 0.3
            elif vol_mcap_ratio > 1.0:
                risk_flags.append("High vol/mcap ratio")
                score -= 0.1

        # Age vs activity mismatch
        if age_hours < 1 and volume > 1_000_000:
            risk_flags.append("Suspicious volume for age")
            score -= 0.2

        # Token name/symbol checks
        symbol = token_info.get("symbol", "").upper()
        name = token_info.get("name", "").lower()

        # Avoid obvious scam patterns
        scam_patterns = ["SCAM", "TEST", "FAKE", "RUGPULL", "PONZI"]
        if any(pattern in symbol for pattern in scam_patterns):
            risk_flags.append("Suspicious symbol")
            score -= 0.5

        if any(pattern in name for pattern in scam_patterns):
            risk_flags.append("Suspicious name")
            score -= 0.5

        # Very low scores indicate high risk
        passed = score > 0.3

        if risk_flags:
            reason = f"Risk flags: {'; '.join(risk_flags)}"
        else:
            reason = "No major risk flags detected"

        return {"passed": passed, "reason": reason, "score": max(score, 0.0)}


def filter_tokens_batch(
    tokens: List[Dict[str, Any]], max_tokens: int = 500, min_score: float = 0.25
) -> List[Dict[str, Any]]:
    """
    Batch filter tokens with intelligent prioritization
    Designed to handle thousands of tokens efficiently
    """
    filter_system = TokenFilter()
    results = []

    logger.info(f"Starting batch filtering of {len(tokens)} tokens...")

    # First pass: Quick filter to reduce volume
    quick_filtered = []
    for token in tokens:
        if passes_filters(token):
            quick_filtered.append(token)

    logger.info(f"Quick filter passed: {len(quick_filtered)} tokens")

    # Second pass: Detailed filtering with scoring
    for token in quick_filtered:
        try:
            filter_result = filter_system.filter_token(token)

            if filter_result.passed and filter_result.score >= min_score:
                token["filter_score"] = filter_result.score
                token["filter_warnings"] = filter_result.warnings
                token["filter_reasons"] = filter_result.reasons
                results.append(token)

        except Exception as e:
            logger.error(
                f"Error filtering token {token.get('symbol', 'unknown')}: {str(e)}"
            )

    # Sort by multiple criteria
    def sort_key(token):
        score = token.get("filter_score", 0)
        age_hours = float(token.get("age_hours", 9999))
        volume = float(token.get("daily_volume_usd", 0))

        # Prioritize: high score, young age, decent volume
        age_bonus = max(0, (168 - age_hours) / 168)  # Newer = higher bonus
        volume_bonus = min(1, volume / 100000)  # Up to 100% bonus for volume

        return score + (age_bonus * 0.2) + (volume_bonus * 0.1)

    results.sort(key=sort_key, reverse=True)

    logger.info(f"Final filtered tokens: {len(results[:max_tokens])}")

    return results[:max_tokens]


def get_filter_stats(tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Get statistics about filtered tokens"""
    if not tokens:
        return {}

    scores = [t.get("filter_score", 0) for t in tokens]
    ages = [float(t.get("age_hours", 0)) for t in tokens if t.get("age_hours")]
    volumes = [float(t.get("daily_volume_usd", 0)) for t in tokens]
    sources = [t.get("discovery_source", "unknown") for t in tokens]

    from collections import Counter

    return {
        "total_tokens": len(tokens),
        "score_stats": {
            "average": sum(scores) / len(scores) if scores else 0,
            "highest": max(scores) if scores else 0,
            "lowest": min(scores) if scores else 0,
        },
        "age_stats": {
            "average_hours": sum(ages) / len(ages) if ages else 0,
            "newest_hours": min(ages) if ages else 0,
            "oldest_hours": max(ages) if ages else 0,
        },
        "volume_stats": {
            "total_volume": sum(volumes),
            "average_volume": sum(volumes) / len(volumes) if volumes else 0,
            "highest_volume": max(volumes) if volumes else 0,
        },
        "source_breakdown": dict(Counter(sources)),
        "top_tokens": [
            {
                "symbol": t.get("symbol", "Unknown"),
                "score": t.get("filter_score", 0),
                "age_hours": t.get("age_hours", "Unknown"),
                "source": t.get("discovery_source", "Unknown"),
            }
            for t in tokens[:10]
        ],
    }
