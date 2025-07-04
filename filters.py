# filters.py - Enhanced Memecoin Filtering System

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

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
    Quick filter for memecoin discovery - VERY INCLUSIVE for initial testing
    """
    try:
        # Must have basic required fields
        address = token_info.get("address", "")
        symbol = token_info.get("symbol", "")
        
        # Skip if no address or symbol
        if not address or not symbol or symbol in [None, "", "None"]:
            return False
        
        # Skip obvious pool pairs or LP tokens
        name = token_info.get("name", "")
        if "/" in name or "-" in name or "LP" in name.upper():
            return False
        
        # Skip well-known tokens and stablecoins
        skip_symbols = ['SOL', 'WSOL', 'USDC', 'USDT', 'BTC', 'ETH', 'WETH']
        if symbol.upper() in skip_symbols:
            return False
        
        # Skip test tokens
        test_keywords = ['TEST', 'FAKE', 'NULL', 'DEMO']
        if any(keyword in symbol.upper() for keyword in test_keywords):
            return False
        
        # For now, accept everything else that has basic data
        # We'll add more filters once we get proper data flowing
        
        return True
        
    except (ValueError, TypeError, KeyError):
        return False

class TokenFilter:
    """Advanced filtering system for comprehensive token analysis"""
    
    def __init__(self):
        # Comprehensive filter categories
        self.filters = {
            'age_and_timing': self._check_age_and_timing,
            'activity_and_momentum': self._check_activity_and_momentum,
            'liquidity_and_tradability': self._check_liquidity_and_tradability,
            'size_and_valuation': self._check_size_and_valuation,
            'source_and_discovery': self._check_source_and_discovery,
            'risk_and_safety': self._check_risk_and_safety,
        }
        
        # Adjusted weights for memecoin trading
        self.filter_weights = {
            'age_and_timing': 0.25,           # When was it created/discovered
            'activity_and_momentum': 0.30,    # Volume, price action, buzz
            'liquidity_and_tradability': 0.15, # Can we actually trade it
            'size_and_valuation': 0.10,       # Market cap considerations
            'source_and_discovery': 0.15,     # Where did we find it
            'risk_and_safety': 0.05,          # Basic safety checks
        }
    
    def filter_token(self, token_info: Dict[str, Any], 
                    strict_mode: bool = False) -> FilterResult:
        """Comprehensive token filtering with detailed scoring"""
        reasons = []
        warnings = []
        scores = {}
        
        # Run all filter categories
        for filter_name, filter_func in self.filters.items():
            try:
                result = filter_func(token_info)
                scores[filter_name] = result['score']
                
                if not result['passed']:
                    reasons.append(f"{filter_name}: {result['reason']}")
                    if strict_mode:
                        return FilterResult(
                            passed=False,
                            reasons=reasons,
                            score=0.0,
                            warnings=warnings
                        )
                
                if result.get('warning'):
                    warnings.append(f"{filter_name}: {result['warning']}")
                    
            except Exception as e:
                logger.error(f"Error in filter {filter_name}: {str(e)}")
                scores[filter_name] = 0.0
        
        # Calculate weighted total score
        total_score = sum(
            scores.get(name, 0) * weight 
            for name, weight in self.filter_weights.items()
        )
        
        # Memecoin-friendly passing criteria
        min_score = 0.35 if strict_mode else 0.25  # Lower threshold for inclusivity
        passed = len(reasons) == 0 and total_score >= min_score
        
        return FilterResult(
            passed=passed,
            reasons=reasons,
            score=total_score,
            warnings=warnings
        )
    
    def _check_age_and_timing(self, token_info: Dict) -> Dict:
        """Check token age and timing factors - much more lenient"""
        age_hours = float(token_info.get("age_hours", 9999))
        
        # Much more lenient age scoring for broader token coverage
        if age_hours < 24:  # Less than 1 day
            score = 1.0
            reason = f"Very fresh: {age_hours:.1f}h old"
        elif age_hours < 168:  # Less than 1 week
            score = 0.9
            reason = f"Fresh: {age_hours:.1f}h old"
        elif age_hours < 720:  # Less than 1 month
            score = 0.8
            reason = f"Recent: {age_hours:.1f}h old"
        elif age_hours < 8760:  # Less than 1 year - MUCH more lenient
            score = 0.6
            reason = f"Established: {age_hours:.1f}h old"
        else:
            score = 0.3  # Still give old tokens a chance
            reason = f"Old but potentially valuable: {age_hours:.1f}h old"
        
        # Bonus for discovery timing
        discovery_time = token_info.get('discovered_at')
        if discovery_time:
            try:
                discovered = datetime.fromisoformat(discovery_time.replace('Z', ''))
                time_since_discovery = (datetime.now() - discovered).total_seconds() / 60
                if time_since_discovery < 5:  # Discovered in last 5 minutes
                    score *= 1.1  # 10% bonus
            except:
                pass
        
        return {
            'passed': True,  # Accept all ages now
            'reason': reason,
            'score': min(score, 1.0)
        }
    
    def _check_activity_and_momentum(self, token_info: Dict) -> Dict:
        """Check trading activity and price momentum - Jupiter-friendly"""
        volume = float(token_info.get("daily_volume_usd", 0))
        price_change = float(token_info.get("price_change_24h", 0))
        source = token_info.get("discovery_source", "")
        
        score = 0.0
        signals = []
        
        # Calculate abs_change for all paths
        abs_change = abs(price_change)
        
        # Special handling for Jupiter tokens (no market data)
        if "jupiter" in source:
            score = 0.5  # Give Jupiter tokens a base score
            signals.append("Jupiter token (comprehensive source)")
            
            # Bonus for interesting symbols
            symbol = token_info.get('symbol', '').upper()
            if any(keyword in symbol for keyword in ['MEME', 'DOG', 'CAT', 'MOON', 'PUMP']):
                score += 0.2
                signals.append("Interesting symbol")
        else:
            # Volume scoring for tokens with market data
            if volume > 100000:  # $100k+ volume
                score += 0.5
                signals.append(f"High volume: ${volume:,.0f}")
            elif volume > 10000:  # $10k+ volume
                score += 0.3
                signals.append(f"Good volume: ${volume:,.0f}")
            elif volume > 1000:  # $1k+ volume
                score += 0.2
                signals.append(f"Moderate volume: ${volume:,.0f}")
            elif volume > 100:  # $100+ volume
                score += 0.1
                signals.append(f"Low volume: ${volume:,.0f}")
            else:
                signals.append("Very low volume")
            
            # Price movement component
            if abs_change > 50:  # 50%+ movement
                score += 0.5
                signals.append(f"High volatility: {price_change:+.1f}%")
            elif abs_change > 20:  # 20%+ movement
                score += 0.3
                signals.append(f"Good volatility: {price_change:+.1f}%")
            elif abs_change > 10:  # 10%+ movement
                score += 0.2
                signals.append(f"Some movement: {price_change:+.1f}%")
            elif abs_change > 5:  # 5%+ movement
                score += 0.1
                signals.append(f"Slight movement: {price_change:+.1f}%")
        
        # Bonus for positive momentum (for all tokens)
        if price_change > 0:
            score *= 1.1
        
        # Much more lenient activity requirement
        has_activity = volume > 10 or abs_change > 1 or "jupiter" in source
        
        return {
            'passed': has_activity,
            'reason': "; ".join(signals),
            'score': min(score, 1.0)
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
        
        result = {
            'passed': min_tradable,
            'reason': reason,
            'score': score
        }
        
        if 'warning' in locals():
            result['warning'] = warning
            
        return result
    
    def _check_size_and_valuation(self, token_info: Dict) -> Dict:
        """Check market cap and valuation metrics - more lenient"""
        market_cap = float(token_info.get("market_cap", 0))
        volume = float(token_info.get("daily_volume_usd", 0))
        source = token_info.get("discovery_source", "")
        
        if market_cap == 0:
            # Unknown market cap - give benefit of doubt, especially for Jupiter
            if "jupiter" in source:
                score = 0.7  # Higher score for Jupiter unknowns
                reason = "Unknown market cap (Jupiter source)"
            else:
                score = 0.5
                reason = "Unknown market cap"
            passed = True
        else:
            # Much more lenient market cap ranges
            if 1_000 <= market_cap <= 10_000_000:  # $1k - $10M sweet spot
                score = 1.0
                reason = f"Good size: ${market_cap:,.0f}"
            elif 10_000_000 < market_cap <= 100_000_000:  # $10M - $100M
                score = 0.8
                reason = f"Large but acceptable: ${market_cap:,.0f}"
            elif 100_000_000 < market_cap <= 1_000_000_000:  # $100M - $1B
                score = 0.5
                reason = f"Very large: ${market_cap:,.0f}"
            elif market_cap < 1_000:  # Under $1k
                score = 0.4
                reason = f"Very small: ${market_cap:,.0f}"
            else:  # Over $1B
                score = 0.2  # Still give mega-caps a chance
                reason = f"Mega cap: ${market_cap:,.0f}"
            
            passed = market_cap < 10_000_000_000  # Under $10B (very lenient)
        
        # Volume/Market Cap ratio check (only for known market caps)
        if market_cap > 0 and volume > 0:
            vol_mcap_ratio = volume / market_cap
            if vol_mcap_ratio > 2.0:  # Daily volume > 2x market cap
                result_warning = "Very high volume/mcap ratio - may be manipulated"
                score *= 0.8  # Reduce but don't eliminate
            elif vol_mcap_ratio > 0.5:
                score *= 1.1  # Bonus for high activity
        
        result = {
            'passed': passed,
            'reason': reason,
            'score': score
        }
        
        if 'result_warning' in locals():
            result['warning'] = result_warning
            
        return result
    
    def _check_source_and_discovery(self, token_info: Dict) -> Dict:
        """Check discovery source and context"""
        source = token_info.get('discovery_source', '').lower()
        
        # Source reliability scoring
        if 'pumpfun' in source and 'new' in source:
            score = 1.0
            reason = "From Pump.fun new tokens - excellent"
        elif 'pumpfun' in source:
            score = 0.9
            reason = "From Pump.fun - very good"
        elif 'dexscreener' in source and 'new' in source:
            score = 0.8
            reason = "From Dexscreener new - good"
        elif 'trending' in source:
            score = 0.7
            reason = "From trending source - decent"
        elif 'birdeye' in source or 'jupiter' in source:
            score = 0.6
            reason = "From price aggregator - okay"
        elif 'raydium' in source:
            score = 0.8
            reason = "From Raydium pools - good"
        else:
            score = 0.4
            reason = f"Unknown source: {source}"
        
        # Bonus for multiple discovery sources
        if token_info.get('seen_in_multiple_sources'):
            score *= 1.2
            reason += " (multiple sources)"
        
        return {
            'passed': True,  # All sources are acceptable
            'reason': reason,
            'score': min(score, 1.0)
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
        symbol = token_info.get('symbol', '').upper()
        name = token_info.get('name', '').lower()
        
        # Avoid obvious scam patterns
        scam_patterns = ['SCAM', 'TEST', 'FAKE', 'RUGPULL', 'PONZI']
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
        
        return {
            'passed': passed,
            'reason': reason,
            'score': max(score, 0.0)
        }


def filter_tokens_batch(tokens: List[Dict[str, Any]], 
                       max_tokens: int = 500,
                       min_score: float = 0.25) -> List[Dict[str, Any]]:
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
                token['filter_score'] = filter_result.score
                token['filter_warnings'] = filter_result.warnings
                token['filter_reasons'] = filter_result.reasons
                results.append(token)
                
        except Exception as e:
            logger.error(f"Error filtering token {token.get('symbol', 'unknown')}: {str(e)}")
    
    # Sort by multiple criteria
    def sort_key(token):
        score = token.get('filter_score', 0)
        age_hours = float(token.get('age_hours', 9999))
        volume = float(token.get('daily_volume_usd', 0))
        
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
    
    scores = [t.get('filter_score', 0) for t in tokens]
    ages = [float(t.get('age_hours', 0)) for t in tokens if t.get('age_hours')]
    volumes = [float(t.get('daily_volume_usd', 0)) for t in tokens]
    sources = [t.get('discovery_source', 'unknown') for t in tokens]
    
    from collections import Counter
    
    return {
        'total_tokens': len(tokens),
        'score_stats': {
            'average': sum(scores) / len(scores) if scores else 0,
            'highest': max(scores) if scores else 0,
            'lowest': min(scores) if scores else 0
        },
        'age_stats': {
            'average_hours': sum(ages) / len(ages) if ages else 0,
            'newest_hours': min(ages) if ages else 0,
            'oldest_hours': max(ages) if ages else 0
        },
        'volume_stats': {
            'total_volume': sum(volumes),
            'average_volume': sum(volumes) / len(volumes) if volumes else 0,
            'highest_volume': max(volumes) if volumes else 0
        },
        'source_breakdown': dict(Counter(sources)),
        'top_tokens': [
            {
                'symbol': t.get('symbol', 'Unknown'),
                'score': t.get('filter_score', 0),
                'age_hours': t.get('age_hours', 'Unknown'),
                'source': t.get('discovery_source', 'Unknown')
            }
            for t in tokens[:10]
        ]
    }