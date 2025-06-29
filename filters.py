# filters.py
from typing import Dict, List, Optional, Any, Callable
import logging
from dataclasses import dataclass
from utils.error_handling import safe_float, safe_int

# Import config properly - this is the fix!
try:
    from config import config
except ImportError:
    # Fallback config if import fails
    class FallbackConfig:
        FILTERS = {
            "max_volume_usd": 1_500_000,
            "max_age_hours": 72,
            "min_holders": 7_500,
            "min_market_cap": 100_000,
            "max_market_cap": 10_000_000,
        }
        TRADING = {
            "min_liquidity_usd": 50_000,
        }
    config = FallbackConfig()

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

class TokenFilter:
    """Comprehensive token filtering system"""
    
    def __init__(self):
        self.filters = {
            'volume': self._check_volume,
            'age': self._check_age,
            'holders': self._check_holders,
            'liquidity': self._check_liquidity,
            'market_cap': self._check_market_cap,
            'price_stability': self._check_price_stability,
            'transaction_activity': self._check_transaction_activity,
            'liquidity_ratios': self._check_liquidity_ratios,
            'honeypot_indicators': self._check_honeypot_indicators,
        }
        
        # Filter weights for scoring
        self.filter_weights = {
            'volume': 0.2,
            'age': 0.15,
            'holders': 0.15,
            'liquidity': 0.2,
            'market_cap': 0.1,
            'price_stability': 0.1,
            'transaction_activity': 0.05,
            'liquidity_ratios': 0.03,
            'honeypot_indicators': 0.02,
        }
    
    def filter_token(self, token_info: Dict[str, Any], 
                    strict_mode: bool = False) -> FilterResult:
        """
        Comprehensive token filtering with scoring
        
        Args:
            token_info: Token data dictionary
            strict_mode: If True, fails on any filter violation
            
        Returns:
            FilterResult with pass/fail status, reasons, and score
        """
        reasons = []
        warnings = []
        scores = {}
        
        # Run all filters
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
                if strict_mode:
                    reasons.append(f"{filter_name}: filter error")
        
        # Calculate weighted score
        total_score = sum(
            scores.get(name, 0) * weight 
            for name, weight in self.filter_weights.items()
        )
        
        # Token passes if no strict failures and reasonable score
        passed = len(reasons) == 0 and total_score >= 0.6
        
        return FilterResult(
            passed=passed,
            reasons=reasons,
            score=total_score,
            warnings=warnings
        )
    
    def _check_volume(self, token_info: Dict) -> Dict:
        """Check daily volume constraints"""
        volume = safe_float(token_info.get("daily_volume_usd", 0))
        max_volume = config.FILTERS["max_volume_usd"]
        
        if volume == 0:
            return {
                'passed': False,
                'reason': 'No volume data available',
                'score': 0.0
            }
        
        if volume > max_volume:
            return {
                'passed': False,
                'reason': f'Volume too high: ${volume:,.0f} > ${max_volume:,.0f}',
                'score': 0.0
            }
        
        # Score based on volume relative to max (higher is better up to a point)
        score = min(volume / (max_volume * 0.5), 1.0)
        
        warning = None
        if volume < 10000:
            warning = f'Low volume: ${volume:,.0f}'
        
        return {
            'passed': True,
            'reason': f'Volume acceptable: ${volume:,.0f}',
            'score': score,
            'warning': warning
        }
    
    def _check_age(self, token_info: Dict) -> Dict:
        """Check token age constraints"""
        age_hours = safe_float(token_info.get("age_hours", 9999))
        max_age = config.FILTERS["max_age_hours"]
        
        if age_hours > max_age:
            return {
                'passed': False,
                'reason': f'Too old: {age_hours:.1f}h > {max_age}h',
                'score': 0.0
            }
        
        # Score: newer tokens get higher scores, but not too new
        if age_hours < 1:
            score = 0.3  # Very new tokens are risky
            warning = f'Very new token: {age_hours:.1f}h'
        elif age_hours < 6:
            score = 0.7
            warning = None
        else:
            score = 1.0 - (age_hours / max_age) * 0.3
            warning = None
        
        return {
            'passed': True,
            'reason': f'Age acceptable: {age_hours:.1f}h',
            'score': score,
            'warning': warning
        }
    
    def _check_holders(self, token_info: Dict) -> Dict:
        """Check holder count constraints"""
        holders = safe_int(token_info.get("holder_count", 0))
        min_holders = config.FILTERS["min_holders"]
        
        if holders < min_holders:
            return {
                'passed': False,
                'reason': f'Too few holders: {holders:,} < {min_holders:,}',
                'score': 0.0
            }
        
        # Score based on holder count (more holders = better, up to a point)
        score = min(holders / (min_holders * 2), 1.0)
        
        warning = None
        if holders < min_holders * 1.5:
            warning = f'Low holder count: {holders:,}'
        
        return {
            'passed': True,
            'reason': f'Holder count acceptable: {holders:,}',
            'score': score,
            'warning': warning
        }
    
    def _check_liquidity(self, token_info: Dict) -> Dict:
        """Check liquidity constraints"""
        liquidity = safe_float(token_info.get("liquidity_usd", 0))
        min_liquidity = config.TRADING["min_liquidity_usd"]
        
        if liquidity < min_liquidity:
            return {
                'passed': False,
                'reason': f'Insufficient liquidity: ${liquidity:,.0f} < ${min_liquidity:,.0f}',
                'score': 0.0
            }
        
        # Score based on liquidity (more is better up to a reasonable point)
        target_liquidity = min_liquidity * 5
        score = min(liquidity / target_liquidity, 1.0)
        
        warning = None
        if liquidity < min_liquidity * 2:
            warning = f'Low liquidity: ${liquidity:,.0f}'
        
        return {
            'passed': True,
            'reason': f'Liquidity acceptable: ${liquidity:,.0f}',
            'score': score,
            'warning': warning
        }
    
    def _check_market_cap(self, token_info: Dict) -> Dict:
        """Check market cap constraints"""
        market_cap = safe_float(token_info.get("market_cap", 0))
        min_mcap = config.FILTERS["min_market_cap"]
        max_mcap = config.FILTERS["max_market_cap"]
        
        if market_cap < min_mcap:
            return {
                'passed': False,
                'reason': f'Market cap too low: ${market_cap:,.0f} < ${min_mcap:,.0f}',
                'score': 0.0
            }
        
        if market_cap > max_mcap:
            return {
                'passed': False,
                'reason': f'Market cap too high: ${market_cap:,.0f} > ${max_mcap:,.0f}',
                'score': 0.0
            }
        
        # Score based on position within range
        range_position = (market_cap - min_mcap) / (max_mcap - min_mcap)
        score = 1.0 - abs(range_position - 0.5) * 0.4  # Best score in middle of range
        
        return {
            'passed': True,
            'reason': f'Market cap acceptable: ${market_cap:,.0f}',
            'score': score
        }
    
    def _check_price_stability(self, token_info: Dict) -> Dict:
        """Check price stability/volatility"""
        price_change = safe_float(token_info.get("price_change_24h", 0))
        
        # Extreme price movements are red flags
        if abs(price_change) > 500:  # 500% change
            return {
                'passed': False,
                'reason': f'Extreme price movement: {price_change:+.1f}%',
                'score': 0.0
            }
        
        # Score based on reasonable volatility
        abs_change = abs(price_change)
        if abs_change > 100:
            score = 0.3
            warning = f'High volatility: {price_change:+.1f}%'
        elif abs_change > 50:
            score = 0.6
            warning = f'Moderate volatility: {price_change:+.1f}%'
        else:
            score = 1.0
            warning = None
        
        return {
            'passed': True,
            'reason': f'Price change acceptable: {price_change:+.1f}%',
            'score': score,
            'warning': warning
        }
    
    def _check_transaction_activity(self, token_info: Dict) -> Dict:
        """Check transaction activity patterns"""
        buys_24h = safe_int(token_info.get("buys_24h", 0))
        sells_24h = safe_int(token_info.get("sells_24h", 0))
        total_txns = buys_24h + sells_24h
        
        if total_txns == 0:
            return {
                'passed': False,
                'reason': 'No transaction activity',
                'score': 0.0
            }
        
        # Check buy/sell ratio
        buy_ratio = buys_24h / total_txns if total_txns > 0 else 0
        
        # Healthy tokens should have reasonable buy/sell balance
        if buy_ratio < 0.2 or buy_ratio > 0.8:
            warning = f'Unbalanced trading: {buy_ratio:.1%} buys'
            score = 0.5
        else:
            warning = None
            score = 1.0
        
        # Very low activity is concerning
        if total_txns < 10:
            warning = f'Low activity: {total_txns} transactions'
            score = min(score, 0.4)
        
        return {
            'passed': True,
            'reason': f'Transaction activity: {total_txns} txns ({buy_ratio:.1%} buys)',
            'score': score,
            'warning': warning
        }
    
    def _check_liquidity_ratios(self, token_info: Dict) -> Dict:
        """Check liquidity-related ratios"""
        liquidity_usd = safe_float(token_info.get("liquidity_usd", 0))
        market_cap = safe_float(token_info.get("market_cap", 0))
        volume_24h = safe_float(token_info.get("volume_24h", 0))
        
        warnings = []
        score = 1.0
        
        # Liquidity to market cap ratio
        if market_cap > 0:
            liq_mcap_ratio = liquidity_usd / market_cap
            if liq_mcap_ratio < 0.05:  # Less than 5%
                warnings.append(f'Low liquidity/mcap ratio: {liq_mcap_ratio:.1%}')
                score = min(score, 0.6)
        
        # Volume to liquidity ratio
        if liquidity_usd > 0:
            vol_liq_ratio = volume_24h / liquidity_usd
            if vol_liq_ratio > 5:  # More than 5x daily turnover
                warnings.append(f'High volume/liquidity ratio: {vol_liq_ratio:.1f}x')
                score = min(score, 0.7)
            elif vol_liq_ratio < 0.1:  # Less than 10% daily turnover
                warnings.append(f'Low volume/liquidity ratio: {vol_liq_ratio:.1f}x')
                score = min(score, 0.8)
        
        return {
            'passed': True,
            'reason': 'Liquidity ratios checked',
            'score': score,
            'warning': '; '.join(warnings) if warnings else None
        }
    
    def _check_honeypot_indicators(self, token_info: Dict) -> Dict:
        """Check for potential honeypot indicators"""
        warnings = []
        score = 1.0
        
        # Very high buy/sell imbalance could indicate honeypot
        buys_24h = safe_int(token_info.get("buys_24h", 0))
        sells_24h = safe_int(token_info.get("sells_24h", 0))
        total_txns = buys_24h + sells_24h
        
        if total_txns > 0:
            buy_ratio = buys_24h / total_txns
            if buy_ratio > 0.95:  # More than 95% buys
                warnings.append('Extremely high buy ratio - potential honeypot')
                score = 0.2
            elif buy_ratio < 0.05:  # Less than 5% buys
                warnings.append('Extremely low buy ratio - potential dump')
                score = 0.3
        
        # Check for suspicious price movements
        price_change = safe_float(token_info.get("price_change_24h", 0))
        if price_change > 1000:  # More than 1000% gain
            warnings.append('Suspicious price pump - potential honeypot')
            score = min(score, 0.3)
        
        # Very new tokens with high volume are suspicious
        age_hours = safe_float(token_info.get("age_hours", 9999))
        volume_24h = safe_float(token_info.get("volume_24h", 0))
        if age_hours < 1 and volume_24h > 100000:
            warnings.append('New token with high volume - high risk')
            score = min(score, 0.4)
        
        return {
            'passed': score > 0.5,
            'reason': 'Honeypot indicators checked',
            'score': score,
            'warning': '; '.join(warnings) if warnings else None
        }

def passes_filters(token_info: Dict[str, Any], strict_mode: bool = False) -> bool:
    """
    Legacy function for backward compatibility
    Returns True if token passes basic filters
    """
    filter_system = TokenFilter()
    result = filter_system.filter_token(token_info, strict_mode)
    return result.passed

def filter_tokens(tokens: List[Dict[str, Any]], 
                 strict_mode: bool = False,
                 min_score: float = 0.6) -> List[Dict[str, Any]]:
    """
    Filter a list of tokens and return those that pass
    
    Args:
        tokens: List of token data dictionaries
        strict_mode: If True, fails on any filter violation
        min_score: Minimum score required to pass
        
    Returns:
        List of tokens that passed filtering with scores added
    """
    filter_system = TokenFilter()
    filtered_tokens = []
    
    for token in tokens:
        try:
            result = filter_system.filter_token(token, strict_mode)
            
            if result.passed and result.score >= min_score:
                # Add filter results to token data
                token['filter_score'] = result.score
                token['filter_warnings'] = result.warnings
                filtered_tokens.append(token)
            else:
                logger.debug(
                    f"Token {token.get('address', 'unknown')} filtered out: "
                    f"score={result.score:.2f}, reasons={result.reasons}"
                )
                
        except Exception as e:
            logger.error(f"Error filtering token {token.get('address', 'unknown')}: {str(e)}")
    
    # Sort by filter score (highest first)
    filtered_tokens.sort(key=lambda t: t.get('filter_score', 0), reverse=True)
    
    logger.info(f"Filtered {len(tokens)} tokens down to {len(filtered_tokens)}")
    return filtered_tokens

def get_filter_stats(tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Get statistics about filtering results"""
    filter_system = TokenFilter()
    
    results = []
    for token in tokens:
        try:
            result = filter_system.filter_token(token)
            results.append(result)
        except Exception:
            continue
    
    if not results:
        return {}
    
    passed_count = sum(1 for r in results if r.passed)
    avg_score = sum(r.score for r in results) / len(results)
    
    # Count most common failure reasons
    all_reasons = []
    for r in results:
        all_reasons.extend(r.reasons)
    
    reason_counts = {}
    for reason in all_reasons:
        filter_name = reason.split(':')[0]
        reason_counts[filter_name] = reason_counts.get(filter_name, 0) + 1
    
    return {
        'total_tokens': len(results),
        'passed_tokens': passed_count,
        'pass_rate': passed_count / len(results),
        'average_score': avg_score,
        'common_failures': dict(sorted(reason_counts.items(), key=lambda x: x[1], reverse=True))
    }