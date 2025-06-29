# api_clients/dexscreener.py
from typing import Dict, List, Optional, Any
import logging
from utils.base_client import BaseAPIClient
from utils.error_handling import safe_float, safe_int, validate_token_address
from config import config

logger = logging.getLogger(__name__)

class DexscreenerClient(BaseAPIClient):
    """Enhanced DexScreener API client"""
    
    def __init__(self):
        super().__init__(
            base_url="https://api.dexscreener.com",  # Correct base URL
            api_key=config.API_KEYS.get("dexscreener"),
            service_name="dexscreener",
            requests_per_minute=config.RATE_LIMITS["dexscreener"]
        )
    
    def fetch_trending_tokens(self, chain: str = "solana", limit: int = 50) -> List[Dict]:
        """
        Fetch actual new/trending tokens from DexScreener
        Since DexScreener doesn't have a direct trending API, we'll use a different approach
        """
        try:
            # Strategy: Use search functionality with popular terms to find new tokens
            # This mimics how users would discover new tokens
            
            all_tokens = []
            
            # Search for recently active Solana pairs using different strategies
            search_terms = ["sol", "pump", "meme", "doge", "shib", "pepe"]
            
            for term in search_terms[:3]:  # Limit to avoid rate limits
                try:
                    search_results = self.search_tokens(term, chain)
                    # Filter for recent tokens (created in last 7 days)
                    recent_tokens = [
                        token for token in search_results 
                        if token.get('age_hours', 9999) < 168  # 7 days
                    ]
                    all_tokens.extend(recent_tokens)
                    
                    if len(all_tokens) >= limit:
                        break
                        
                except Exception as e:
                    logger.warning(f"Search failed for term '{term}': {str(e)}")
                    continue
            
            # Remove duplicates and sort by age (newest first)
            unique_tokens = {}
            for token in all_tokens:
                address = token.get('address')
                if address and address not in unique_tokens:
                    unique_tokens[address] = token
            
            result = list(unique_tokens.values())
            result.sort(key=lambda x: x.get('age_hours', 9999))  # Newest first
            
            logger.info(f"Found {len(result)} unique trending tokens")
            return result[:limit]
            
        except Exception as e:
            logger.error(f"Failed to fetch trending tokens: {str(e)}")
            return []
    
    def search_tokens(self, query: str, chain: str = "solana") -> List[Dict]:
        """Search for tokens by name or symbol using DexScreener's search"""
        try:
            # DexScreener search endpoint (undocumented but exists)
            # This is based on observing their website behavior
            endpoint = "latest/dex/search"
            params = {'q': query}
            
            response = self.get(endpoint, params)
            pairs = response.get('pairs', [])
            
            processed_results = []
            for pair in pairs:
                # Only include Solana pairs
                if pair.get('chainId') == chain:
                    processed_pair = self._process_token_data(pair)
                    if processed_pair:
                        processed_results.append(processed_pair)
            
            logger.debug(f"Search for '{query}' returned {len(processed_results)} results")
            return processed_results
            
        except Exception as e:
            logger.warning(f"Search failed for '{query}': {str(e)}")
            return []
    
    def fetch_new_pairs(self, chain: str = "solana", limit: int = 50) -> List[Dict]:
        """
        Alternative method: Try to get pairs sorted by creation time
        """
        try:
            # Try multiple token addresses to get variety of recent pairs
            recent_token_samples = [
                # Add some known active token addresses as starting points
                "So11111111111111111111111111111111111111112",  # SOL
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                # We could add more diverse token addresses here
            ]
            
            all_pairs = []
            for token_address in recent_token_samples:
                try:
                    pairs = self.get_pairs_for_token(token_address)
                    # Filter for newer pairs (less than 30 days old)
                    recent_pairs = [
                        pair for pair in pairs 
                        if pair.get('age_hours', 9999) < 720  # 30 days
                    ]
                    all_pairs.extend(recent_pairs)
                    
                except Exception as e:
                    logger.warning(f"Failed to get pairs for {token_address}: {str(e)}")
                    continue
            
            # Sort by age and remove duplicates
            unique_pairs = {}
            for pair in all_pairs:
                address = pair.get('address')
                if address and address not in unique_pairs:
                    unique_pairs[address] = pair
            
            result = list(unique_pairs.values())
            result.sort(key=lambda x: x.get('age_hours', 9999))
            
            return result[:limit]
            
        except Exception as e:
            logger.error(f"Failed to fetch new pairs: {str(e)}")
            return []
    
    def get_pairs_for_token(self, token_address: str) -> List[Dict]:
        """Get pairs for a specific token using the correct DexScreener API"""
        try:
            # Use the correct DexScreener endpoint
            endpoint = f"latest/dex/tokens/{token_address}"
            response = self.get(endpoint)
            
            pairs = response.get('pairs', [])
            processed_pairs = []
            
            for pair in pairs:
                processed_pair = self._process_token_data(pair)
                if processed_pair:
                    processed_pairs.append(processed_pair)
            
            logger.info(f"Fetched {len(processed_pairs)} pairs for token {token_address}")
            return processed_pairs
            
        except Exception as e:
            logger.error(f"Failed to get pairs for token {token_address}: {str(e)}")
            return []
    
    def fetch_token_details(self, token_address: str, chain: str = "solana") -> Optional[Dict]:
        """Get detailed information for a specific token"""
        if not validate_token_address(token_address):
            logger.error(f"Invalid token address: {token_address}")
            return None
        
        try:
            endpoint = f"tokens/{token_address}"
            response = self.get(endpoint)
            
            pairs = response.get('pairs', [])
            if not pairs:
                logger.warning(f"No pairs found for token {token_address}")
                return None
            
            # Get the most liquid pair
            best_pair = max(pairs, key=lambda p: safe_float(p.get('liquidity', {}).get('usd', 0)))
            
            return self._process_token_data(best_pair)
            
        except Exception as e:
            logger.error(f"Failed to fetch token details for {token_address}: {str(e)}")
            return None
    
    def search_tokens(self, query: str, chain: str = "solana") -> List[Dict]:
        """Search for tokens by name or symbol"""
        try:
            endpoint = "search"
            params = {
                'q': query,
                'chain': chain
            }
            
            response = self.get(endpoint, params)
            pairs = response.get('pairs', [])
            
            processed_results = []
            for pair in pairs:
                processed_pair = self._process_token_data(pair)
                if processed_pair:
                    processed_results.append(processed_pair)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Failed to search tokens for '{query}': {str(e)}")
            return []
    
    def get_token_price_history(self, token_address: str, 
                               timeframe: str = "1h") -> List[Dict]:
        """Get price history for a token"""
        try:
            endpoint = f"tokens/{token_address}/ohlcv/{timeframe}"
            response = self.get(endpoint)
            
            return response.get('ohlcv', [])
            
        except Exception as e:
            logger.error(f"Failed to get price history for {token_address}: {str(e)}")
            return []
    
    def _process_token_data(self, raw_data: Dict) -> Optional[Dict]:
        """Process and normalize raw token data from DexScreener"""
        try:
            base_token = raw_data.get('baseToken', {})
            quote_token = raw_data.get('quoteToken', {})
            
            if not base_token.get('address'):
                return None
            
            # Calculate age in hours
            created_at = raw_data.get('pairCreatedAt')
            age_hours = 9999  # Default to very old if no creation time
            if created_at:
                import datetime
                created_time = datetime.datetime.fromtimestamp(created_at / 1000)
                age_hours = (datetime.datetime.now() - created_time).total_seconds() / 3600
            
            # Process liquidity data
            liquidity = raw_data.get('liquidity', {})
            liquidity_usd = safe_float(liquidity.get('usd', 0))
            
            # Process volume data
            volume = raw_data.get('volume', {})
            volume_24h = safe_float(volume.get('h24', 0))
            
            # Process price data
            price_usd = safe_float(raw_data.get('priceUsd', 0))
            price_change_24h = safe_float(raw_data.get('priceChange', {}).get('h24', 0))
            
            # Process transaction data
            txns = raw_data.get('txns', {})
            txns_24h = safe_int(txns.get('h24', {}).get('buys', 0)) + safe_int(txns.get('h24', {}).get('sells', 0))
            
            # Process market cap
            fdv = safe_float(raw_data.get('fdv', 0))
            market_cap = safe_float(raw_data.get('marketCap', fdv))
            
            # Get additional metadata
            info = raw_data.get('info', {})
            websites = info.get('websites', [])
            socials = info.get('socials', [])
            
            processed_data = {
                # Basic token info
                'address': base_token.get('address'),
                'symbol': base_token.get('symbol', ''),
                'name': base_token.get('name', ''),
                'chain': raw_data.get('chainId', 'solana'),
                
                # Pair info
                'pair_address': raw_data.get('pairAddress'),
                'dex_id': raw_data.get('dexId'),
                'quote_token': quote_token.get('symbol', 'SOL'),
                
                # Price and market data
                'price_usd': price_usd,
                'price_change_24h': price_change_24h,
                'market_cap': market_cap,
                'fdv': fdv,
                'liquidity_usd': liquidity_usd,
                
                # Volume and activity
                'daily_volume_usd': volume_24h,
                'volume_24h': volume_24h,
                'txns_24h': txns_24h,
                'buys_24h': safe_int(txns.get('h24', {}).get('buys', 0)),
                'sells_24h': safe_int(txns.get('h24', {}).get('sells', 0)),
                
                # Age and timing
                'age_hours': age_hours,
                'created_at': created_at,
                
                # Additional metadata
                'websites': websites,
                'socials': socials,
                'url': raw_data.get('url'),
                
                # DexScreener specific
                'dexscreener_url': f"https://dexscreener.com/{raw_data.get('chainId', 'solana')}/{raw_data.get('pairAddress')}",
                
                # Calculated metrics
                'holder_count': self._estimate_holder_count(txns_24h, age_hours),
                'liquidity_to_mcap_ratio': liquidity_usd / market_cap if market_cap > 0 else 0,
                'volume_to_liquidity_ratio': volume_24h / liquidity_usd if liquidity_usd > 0 else 0,
            }
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Failed to process token data: {str(e)}")
            return None
    
    def _estimate_holder_count(self, txns_24h: int, age_hours: float) -> int:
        """
        Estimate holder count based on transaction volume and age
        This is a rough approximation since DexScreener doesn't provide holder data
        """
        if age_hours <= 0:
            return 0
        
        # Rough estimation: assume average 2 txns per holder per day for active tokens
        # Scale by age to account for accumulation over time
        base_holders = max(1, txns_24h // 2)
        
        # Age factor: older tokens tend to have more holders
        age_factor = min(age_hours / 24, 30)  # Cap at 30 days worth
        
        estimated_holders = int(base_holders * (1 + age_factor * 0.1))
        
        return max(estimated_holders, 1)
    
    def health_check(self) -> bool:
        """Check DexScreener API health"""
        try:
            # DexScreener doesn't have a specific health endpoint
            # Try fetching a small amount of data
            self.fetch_trending_tokens(limit=1)
            return True
        except Exception:
            return False