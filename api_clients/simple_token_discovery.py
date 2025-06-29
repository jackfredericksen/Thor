# simple_token_discovery.py - Simplified version using known working APIs

import requests
import time
import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class SimpleTokenDiscovery:
    """Simplified token discovery using verified working APIs"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; TradingBot/1.0)',
            'Accept': 'application/json'
        })
    
    def discover_all_tokens(self) -> List[Dict[str, Any]]:
        """Discover tokens from working sources"""
        all_tokens = []
        
        # Source 1: Jupiter token list (comprehensive Solana tokens)
        jupiter_tokens = self._get_jupiter_tokens()
        all_tokens.extend(jupiter_tokens)
        logger.info(f"Got {len(jupiter_tokens)} tokens from Jupiter")
        
        # Source 2: CoinGecko Solana ecosystem
        coingecko_tokens = self._get_coingecko_solana_tokens()
        all_tokens.extend(coingecko_tokens)
        logger.info(f"Got {len(coingecko_tokens)} tokens from CoinGecko")
        
        # Source 3: DexScreener search for active tokens
        dex_tokens = self._get_dexscreener_active_tokens()
        all_tokens.extend(dex_tokens)
        logger.info(f"Got {len(dex_tokens)} tokens from DexScreener")
        
        # Deduplicate by address
        seen_addresses = set()
        unique_tokens = []
        for token in all_tokens:
            address = token.get('address', '').lower()
            if address and address not in seen_addresses:
                seen_addresses.add(address)
                unique_tokens.append(token)
        
        logger.info(f"Total unique tokens: {len(unique_tokens)}")
        return unique_tokens
    
    def _get_jupiter_tokens(self) -> List[Dict[str, Any]]:
        """Get tokens from Jupiter token list"""
        try:
            response = self.session.get("https://token.jup.ag/all", timeout=10)
            response.raise_for_status()
            
            jupiter_tokens = response.json()
            tokens = []
            
            for token in jupiter_tokens:
                symbol = token.get('symbol', '')
                
                # Filter for likely memecoins/smaller tokens
                if (symbol and 
                    symbol.upper() not in ['USDC', 'USDT', 'SOL', 'WSOL', 'BTC', 'ETH', 'WETH', 'WBTC'] and
                    len(symbol) <= 15):  # Reasonable symbol length
                    
                    tokens.append({
                        'address': token.get('address'),
                        'symbol': symbol,
                        'name': token.get('name', symbol),
                        'daily_volume_usd': 0,  # Jupiter doesn't provide volume
                        'price_change_24h': 0,  # Jupiter doesn't provide price change
                        'liquidity_usd': 0,
                        'market_cap': 0,
                        'price_usd': 0,
                        'age_hours': 48,  # Default to 2 days
                        'discovery_source': 'jupiter_tokens',
                        'source_raw': 'jupiter',
                        'discovered_at': datetime.now().isoformat()
                    })
            
            # Return a sample of interesting tokens
            return tokens[:100]  # Limit to 100 to avoid overwhelming
            
        except Exception as e:
            logger.error(f"Error fetching Jupiter tokens: {e}")
            return []
    
    def _get_coingecko_solana_tokens(self) -> List[Dict[str, Any]]:
        """Get Solana ecosystem tokens from CoinGecko"""
        try:
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                'vs_currency': 'usd',
                'category': 'solana-ecosystem',
                'order': 'volume_desc',
                'per_page': 100,
                'page': 1,
                'sparkline': 'false'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            coingecko_data = response.json()
            tokens = []
            
            for coin in coingecko_data:
                # Skip major tokens
                symbol = coin.get('symbol', '').upper()
                if symbol in ['SOL', 'USDC', 'USDT', 'BTC', 'ETH']:
                    continue
                
                # Skip tokens with very high market cap (already established)
                market_cap = coin.get('market_cap') or 0
                if market_cap > 1_000_000_000:  # Over $1B
                    continue
                
                tokens.append({
                    'address': '',  # CoinGecko doesn't always provide contract address
                    'symbol': coin.get('symbol', ''),
                    'name': coin.get('name', ''),
                    'daily_volume_usd': float(coin.get('total_volume') or 0),
                    'price_change_24h': float(coin.get('price_change_percentage_24h') or 0),
                    'liquidity_usd': 0,  # Not available from CoinGecko
                    'market_cap': float(market_cap),
                    'price_usd': float(coin.get('current_price') or 0),
                    'age_hours': 168,  # Default to 1 week
                    'coingecko_id': coin.get('id'),
                    'discovery_source': 'coingecko_solana',
                    'source_raw': 'coingecko',
                    'discovered_at': datetime.now().isoformat()
                })
            
            return tokens
            
        except Exception as e:
            logger.error(f"Error fetching CoinGecko tokens: {e}")
            return []
    
    def _get_dexscreener_active_tokens(self) -> List[Dict[str, Any]]:
        """Get active tokens from DexScreener search"""
        try:
            # Search for tokens with recent activity
            search_terms = ['meme', 'dog', 'cat', 'moon', 'pump']
            all_tokens = []
            
            for term in search_terms:
                try:
                    url = f"https://api.dexscreener.com/latest/dex/search/?q={term}"
                    response = self.session.get(url, timeout=10)
                    response.raise_for_status()
                    
                    data = response.json()
                    pairs = data.get('pairs', [])
                    
                    for pair in pairs:
                        if pair.get('chainId') != 'solana':
                            continue
                        
                        base_token = pair.get('baseToken', {})
                        volume_24h = float(pair.get('volume', {}).get('h24', 0))
                        
                        # Only include tokens with some activity
                        if volume_24h < 100:  # At least $100 daily volume
                            continue
                        
                        # Skip obvious stablecoins and major tokens
                        symbol = base_token.get('symbol', '').upper()
                        if symbol in ['USDC', 'USDT', 'SOL', 'WSOL', 'BTC', 'ETH']:
                            continue
                        
                        all_tokens.append({
                            'address': base_token.get('address'),
                            'symbol': base_token.get('symbol'),
                            'name': base_token.get('name'),
                            'daily_volume_usd': volume_24h,
                            'price_change_24h': float(pair.get('priceChange', {}).get('h24', 0)),
                            'liquidity_usd': float(pair.get('liquidity', {}).get('usd', 0)),
                            'market_cap': float(pair.get('fdv', 0)),
                            'price_usd': float(pair.get('priceUsd', 0)),
                            'age_hours': 24,  # Default
                            'discovery_source': f'dexscreener_{term}',
                            'source_raw': 'dexscreener',
                            'discovered_at': datetime.now().isoformat()
                        })
                    
                    time.sleep(0.5)  # Rate limiting between searches
                    
                except Exception as e:
                    logger.warning(f"Error searching DexScreener for '{term}': {e}")
                    continue
            
            return all_tokens
            
        except Exception as e:
            logger.error(f"Error fetching DexScreener tokens: {e}")
            return []

# Test the simplified discovery
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    discovery = SimpleTokenDiscovery()
    tokens = discovery.discover_all_tokens()
    
    print(f"\nDiscovered {len(tokens)} total tokens")
    
    # Show some examples
    for i, token in enumerate(tokens[:10]):
        print(f"{i+1}. {token.get('symbol')} - {token.get('name')} "
              f"(Volume: ${token.get('daily_volume_usd', 0):,.0f}, "
              f"Source: {token.get('discovery_source')})")