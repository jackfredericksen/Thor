# volume_verification.py - Add real-time volume checking

import requests
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class VolumeVerifier:
    """Verify real-time volume data for tokens before trading"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.cache = {}  # Cache volume data to avoid repeated calls
    
    def get_token_volume(self, token_address: str) -> Dict:
        """Get real-time volume data for a token"""
        if token_address in self.cache:
            cached_data = self.cache[token_address]
            # Use cache if less than 5 minutes old
            if time.time() - cached_data['timestamp'] < 300:
                return cached_data['data']
        
        # Try multiple sources for volume data
        volume_data = (
            self._get_dexscreener_volume(token_address) or
            self._get_birdeye_volume(token_address) or
            self._get_fallback_volume(token_address)
        )
        
        # Cache the result
        self.cache[token_address] = {
            'data': volume_data,
            'timestamp': time.time()
        }
        
        return volume_data
    
    def _get_dexscreener_volume(self, token_address: str) -> Optional[Dict]:
        """Get volume from DexScreener (most reliable)"""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                pairs = data.get('pairs', [])
                
                if pairs:
                    # Use the pair with highest volume
                    best_pair = max(pairs, key=lambda p: float(p.get('volume', {}).get('h24', 0)))
                    
                    volume_24h = float(best_pair.get('volume', {}).get('h24', 0))
                    liquidity = float(best_pair.get('liquidity', {}).get('usd', 0))
                    price_change = float(best_pair.get('priceChange', {}).get('h24', 0))
                    price = float(best_pair.get('priceUsd', 0))
                    
                    return {
                        'volume_24h': volume_24h,
                        'liquidity_usd': liquidity,
                        'price_change_24h': price_change,
                        'price_usd': price,
                        'source': 'dexscreener',
                        'pairs_count': len(pairs),
                        'has_trading': volume_24h > 0
                    }
        except Exception as e:
            logger.debug(f"DexScreener volume check failed for {token_address}: {e}")
        
        return None
    
    def _get_birdeye_volume(self, token_address: str) -> Optional[Dict]:
        """Get volume from Birdeye (backup)"""
        try:
            # Birdeye public endpoint (if available)
            url = f"https://public-api.birdeye.so/public/price/{token_address}"
            response = self.session.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                volume_24h = float(data.get('volume24h', 0))
                
                return {
                    'volume_24h': volume_24h,
                    'liquidity_usd': 0,  # Not available
                    'price_change_24h': float(data.get('priceChange24h', 0)),
                    'price_usd': float(data.get('value', 0)),
                    'source': 'birdeye',
                    'pairs_count': 1,
                    'has_trading': volume_24h > 0
                }
        except Exception as e:
            logger.debug(f"Birdeye volume check failed for {token_address}: {e}")
        
        return None
    
    def _get_fallback_volume(self, token_address: str) -> Dict:
        """Fallback - return default data"""
        return {
            'volume_24h': 0,
            'liquidity_usd': 0,
            'price_change_24h': 0,
            'price_usd': 0,
            'source': 'none',
            'pairs_count': 0,
            'has_trading': False
        }
    
    def verify_trading_viability(self, token_address: str, min_volume: float = 50000, 
                                min_liquidity: float = 20000) -> tuple[bool, str, Dict]:
        """Check if token meets minimum trading requirements"""
        try:
            volume_data = self.get_token_volume(token_address)
            
            volume_24h = volume_data.get('volume_24h', 0)
            liquidity = volume_data.get('liquidity_usd', 0)
            has_trading = volume_data.get('has_trading', False)
            pairs_count = volume_data.get('pairs_count', 0)
            
            # Check trading viability
            if not has_trading:
                return False, "No active trading detected", volume_data
            
            if volume_24h < min_volume:
                return False, f"Volume too low: ${volume_24h:,.0f} < ${min_volume:,.0f}", volume_data
            
            if liquidity > 0 and liquidity < min_liquidity:
                return False, f"Liquidity too low: ${liquidity:,.0f} < ${min_liquidity:,.0f}", volume_data
            
            if pairs_count == 0:
                return False, "No trading pairs found", volume_data
            
            return True, f"Trading viable: ${volume_24h:,.0f} volume, {pairs_count} pairs", volume_data
            
        except Exception as e:
            logger.error(f"Error verifying trading viability: {e}")
            return False, f"Verification error: {e}", {}

# Enhanced filters with volume verification
def verify_token_for_trading(token_data: Dict, min_volume: float = 50000) -> tuple[bool, str, Dict]:
    """Verify token has sufficient volume for safe trading"""
    
    verifier = VolumeVerifier()
    token_address = token_data.get('address', '')
    
    if not token_address:
        return False, "No token address", {}
    
    # Check real-time volume
    viable, reason, volume_data = verifier.verify_trading_viability(
        token_address, 
        min_volume=min_volume,
        min_liquidity=10000  # $10k minimum liquidity
    )
    
    return viable, reason, volume_data