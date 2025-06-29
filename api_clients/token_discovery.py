# api_clients/token_discovery.py
import time
from typing import List, Dict, Optional
import logging
from utils.base_client import BaseAPIClient
from utils.error_handling import safe_float, safe_int
from config import config

logger = logging.getLogger(__name__)

class TokenDiscoveryClient(BaseAPIClient):
    """
    Multi-source token discovery client
    Aggregates new tokens from GMGN, Pump.fun, and other sources
    """
    
    def __init__(self):
        # Use a generic base URL since we'll call multiple APIs
        super().__init__(
            base_url="https://gmgn.ai",  # Primary source
            api_key=None,  # No key needed for discovery
            service_name="token_discovery",
            requests_per_minute=60  # Conservative rate limit
        )
    
    def discover_new_tokens(self, limit: int = 50) -> List[Dict]:
        """
        Discover new tokens from multiple sources
        
        Returns:
            List of standardized token dictionaries
        """
        logger.info("Starting multi-source token discovery...")
        all_tokens = []
        
        # Source 1: GMGN trending tokens
        try:
            gmgn_tokens = self._get_gmgn_trending()
            all_tokens.extend(gmgn_tokens)
            logger.info(f"GMGN: discovered {len(gmgn_tokens)} tokens")
        except Exception as e:
            logger.warning(f"GMGN discovery failed: {str(e)}")
        
        # Source 2: Pump.fun recent tokens
        try:
            pump_tokens = self._get_pumpfun_recent()
            all_tokens.extend(pump_tokens)
            logger.info(f"Pump.fun: discovered {len(pump_tokens)} tokens")
        except Exception as e:
            logger.warning(f"Pump.fun discovery failed: {str(e)}")
        
        # Source 3: GMGN new listings
        try:
            new_tokens = self._get_gmgn_new_listings()
            all_tokens.extend(new_tokens)
            logger.info(f"GMGN new listings: discovered {len(new_tokens)} tokens")
        except Exception as e:
            logger.warning(f"GMGN new listings failed: {str(e)}")
        
        # Remove duplicates and sort by age (newest first)
        unique_tokens = self._deduplicate_tokens(all_tokens)
        unique_tokens.sort(key=lambda x: x.get('age_hours', 9999))
        
        result = unique_tokens[:limit]
        logger.info(f"Token discovery complete: {len(result)} unique tokens found")
        
        return result
    
    def _get_gmgn_trending(self) -> List[Dict]:
        """Get trending tokens from GMGN"""
        try:
            endpoint = "/defi/quotation/v1/tokens/top_pools/sol"
            params = {
                'limit': 20,
                'period': '1h',
                'orderby': 'volume'
            }
            
            response = self.get(endpoint, params)
            tokens = []
            
            for item in response.get('data', {}).get('rank', []):
                token = self._format_gmgn_token(item)
                if token:
                    token['source'] = 'gmgn_trending'
                    tokens.append(token)
            
            return tokens
            
        except Exception as e:
            logger.error(f"GMGN trending API error: {str(e)}")
            return []
    
    def _get_gmgn_new_listings(self) -> List[Dict]:
        """Get new token listings from GMGN"""
        try:
            endpoint = "/defi/quotation/v1/tokens/new_pools/sol"
            params = {
                'limit': 15,
                'period': '24h'
            }
            
            response = self.get(endpoint, params)
            tokens = []
            
            for item in response.get('data', {}).get('rank', []):
                token = self._format_gmgn_token(item)
                if token:
                    token['source'] = 'gmgn_new'
                    tokens.append(token)
            
            return tokens
            
        except Exception as e:
            logger.error(f"GMGN new listings API error: {str(e)}")
            return []
    
    def _get_pumpfun_recent(self) -> List[Dict]:
        """Get recent tokens from Pump.fun"""
        try:
            # Use a different base URL for pump.fun
            import requests
            
            url = "https://frontend-api.pump.fun/coins/king-of-the-hill"
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; TokenBot/1.0)'
            })
            
            if response.status_code == 200:
                data = response.json()
                tokens = []
                
                for item in data[:10]:  # Limit to 10
                    token = self._format_pumpfun_token(item)
                    if token:
                        token['source'] = 'pumpfun'
                        tokens.append(token)
                
                return tokens
            else:
                logger.warning(f"Pump.fun API returned {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Pump.fun API error: {str(e)}")
            return []
    
    def _format_gmgn_token(self, data: Dict) -> Optional[Dict]:
        """Format GMGN token data to standard format"""
        try:
            address = data.get('address') or data.get('token_address')
            if not address:
                return None
            
            return {
                'address': address,
                'symbol': data.get('symbol', ''),
                'name': data.get('name', ''),
                'price_usd': safe_float(data.get('price', 0)),
                'market_cap': safe_float(data.get('market_cap', 0)),
                'liquidity_usd': safe_float(data.get('liquidity', 0)),
                'daily_volume_usd': safe_float(data.get('volume_24h', 0)),
                'volume_24h': safe_float(data.get('volume_24h', 0)),
                'age_hours': self._calculate_age_hours(data.get('created_timestamp')),
                'holder_count': safe_int(data.get('holder_count', 0)),
                'buys_24h': safe_int(data.get('txns', {}).get('h24', {}).get('buys', 0)),
                'sells_24h': safe_int(data.get('txns', {}).get('h24', {}).get('sells', 0)),
                'price_change_24h': safe_float(data.get('price_change_24h', 0)),
            }
        except Exception as e:
            logger.error(f"Error formatting GMGN token: {str(e)}")
            return None
    
    def _format_pumpfun_token(self, data: Dict) -> Optional[Dict]:
        """Format Pump.fun token data to standard format"""
        try:
            address = data.get('mint')
            if not address:
                return None
            
            # Calculate price from market cap and supply
            market_cap = safe_float(data.get('usd_market_cap', 0))
            total_supply = safe_float(data.get('total_supply', 1))
            price = market_cap / max(total_supply, 1) if total_supply > 0 else 0
            
            return {
                'address': address,
                'symbol': data.get('symbol', ''),
                'name': data.get('name', ''),
                'price_usd': price,
                'market_cap': market_cap,
                'liquidity_usd': 50000,  # Pump.fun has bonding curve liquidity
                'daily_volume_usd': 0,  # Not provided
                'volume_24h': 0,
                'age_hours': self._calculate_age_hours(data.get('created_timestamp')),
                'holder_count': safe_int(data.get('holder_count', 0)),
                'buys_24h': 0,  # Not provided
                'sells_24h': 0,
                'price_change_24h': 0,
            }
        except Exception as e:
            logger.error(f"Error formatting Pump.fun token: {str(e)}")
            return None
    
    def _calculate_age_hours(self, timestamp) -> float:
        """Calculate age in hours from timestamp"""
        try:
            if not timestamp:
                return 9999
            
            # Handle different timestamp formats
            if isinstance(timestamp, str):
                timestamp = float(timestamp)
            
            # Convert to seconds if in milliseconds
            if timestamp > 1e12:
                timestamp = timestamp / 1000
            
            age_seconds = time.time() - timestamp
            return max(0, age_seconds / 3600)
            
        except Exception:
            return 9999
    
    def _deduplicate_tokens(self, tokens: List[Dict]) -> List[Dict]:
        """Remove duplicate tokens based on address"""
        unique_tokens = {}
        
        for token in tokens:
            address = token.get('address')
            if address and address not in unique_tokens:
                unique_tokens[address] = token
            elif address and address in unique_tokens:
                # Keep the token with more complete data
                existing = unique_tokens[address]
                if token.get('volume_24h', 0) > existing.get('volume_24h', 0):
                    unique_tokens[address] = token
        
        return list(unique_tokens.values())
    
    def health_check(self) -> bool:
        """Check if token discovery services are healthy"""
        try:
            # Test GMGN endpoint
            response = self.get("/defi/quotation/v1/tokens/top_pools/sol", {'limit': 1})
            return bool(response.get('data'))
        except Exception:
            return False
    
    def get_token_details(self, token_address: str) -> Optional[Dict]:
        """Get detailed information for a specific token"""
        try:
            endpoint = f"/defi/quotation/v1/tokens/{token_address}/kline/sol"
            response = self.get(endpoint)
            
            if response.get('data'):
                return self._format_gmgn_token(response['data'])
            return None
            
        except Exception as e:
            logger.error(f"Failed to get token details for {token_address}: {str(e)}")
            return None