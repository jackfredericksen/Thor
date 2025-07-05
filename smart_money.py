# smart_money.py - Updated with alternative sources

import requests
import time
import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class AlternativeSmartMoneyTracker:
    """Smart money tracking using alternative sources"""
    
    def __init__(self, storage):
        self.storage = storage
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def monitor_smart_trades(self):
        """Monitor smart money from multiple alternative sources"""
        try:
            logger.info("Smart Money: Scanning alternative sources...")
            
            # Source 1: DexScreener large transactions
            dex_trades = self._get_dexscreener_large_trades()
            
            # Source 2: Solscan large transactions 
            solscan_trades = self._get_solscan_large_trades()
            
            # Source 3: Volume spike analysis
            volume_trades = self._get_volume_spike_trades()
            
            all_trades = dex_trades + solscan_trades + volume_trades
            
            if all_trades:
                logger.info(f"Smart Money: Found {len(all_trades)} large transactions")
                for trade in all_trades:
                    self._process_smart_trade(trade)
            else:
                logger.info("Smart Money: No large transactions found this cycle")
                
        except Exception as e:
            logger.error(f"Error in alternative smart money tracking: {e}")
    
    def _get_dexscreener_large_trades(self) -> List[Dict]:
        """Get large trades from DexScreener volume spikes"""
        try:
            # Search for tokens with recent high activity
            search_terms = ['pump', 'moon', 'rocket']  # Common whale target patterns
            large_trades = []
            
            for term in search_terms[:2]:  # Limit API calls
                try:
                    url = f"https://api.dexscreener.com/latest/dex/search/?q={term}"
                    response = self.session.get(url, timeout=10)
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    for pair in data.get('pairs', [])[:5]:  # Top 5 per search
                        if pair.get('chainId') != 'solana':
                            continue
                        
                        volume_24h = float(pair.get('volume', {}).get('h24', 0))
                        volume_5m = float(pair.get('volume', {}).get('m5', 0))
                        price_change = float(pair.get('priceChange', {}).get('h24', 0))
                        
                        # Look for whale activity indicators
                        high_volume = volume_24h > 500000  # $500k+ daily volume
                        recent_spike = volume_5m > 50000   # $50k+ in 5 minutes
                        big_move = abs(price_change) > 50  # 50%+ price movement
                        
                        if high_volume or (recent_spike and big_move):
                            base_token = pair.get('baseToken', {})
                            confidence = "high" if (high_volume and recent_spike) else "medium"
                            
                            trade = {
                                'wallet': 'whale_detected_dex',
                                'token_address': base_token.get('address'),
                                'value_usd': max(volume_24h, volume_5m),
                                'tx_hash': f"dex_{term}_{int(time.time())}",
                                'tags': ['whale_activity', 'volume_spike', confidence, f'search_{term}'],
                                'source': 'dexscreener_whale_hunt',
                                'symbol': base_token.get('symbol'),
                                'price_change': price_change,
                                'timestamp': datetime.now().isoformat()
                            }
                            large_trades.append(trade)
                    
                    time.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    logger.debug(f"Error searching DexScreener for '{term}': {e}")
                    continue
            
            return large_trades
            
        except Exception as e:
            logger.error(f"Error fetching DexScreener whale trades: {e}")
            return []
    
    def _get_solscan_large_trades(self) -> List[Dict]:
        """Get large trades from Solscan trending tokens"""
        try:
            # Solscan trending endpoint (public)
            url = "https://api.solscan.io/account/trending"
            large_trades = []
            
            try:
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    trending = response.json()
                    
                    for account in trending.get('data', [])[:10]:  # Top 10 trending
                        account_address = account.get('account')
                        if not account_address:
                            continue
                        
                        # Look up recent activity for this trending account
                        try:
                            activity_url = f"https://api.solscan.io/account/transactions?account={account_address}&limit=5"
                            activity_response = self.session.get(activity_url, timeout=5)
                            
                            if activity_response.status_code == 200:
                                transactions = activity_response.json()
                                
                                for tx in transactions.get('data', [])[:3]:
                                    # Look for large SOL movements
                                    sol_change = abs(float(tx.get('lamportChange', 0))) / 1e9  # Convert to SOL
                                    
                                    if sol_change > 100:  # 100+ SOL movements
                                        trade = {
                                            'wallet': account_address,
                                            'token_address': 'So11111111111111111111111111111111111111112',  # SOL
                                            'value_usd': sol_change * 200,  # Rough SOL price estimate
                                            'tx_hash': tx.get('txHash'),
                                            'tags': ['large_sol_movement', 'trending_account', 'solscan_detected'],
                                            'source': 'solscan_trending',
                                            'timestamp': tx.get('blockTime')
                                        }
                                        large_trades.append(trade)
                                        
                        except Exception as e:
                            logger.debug(f"Error fetching activity for {account_address}: {e}")
                            continue
                        
                        time.sleep(0.5)  # Rate limiting
                        
            except Exception as e:
                logger.debug(f"Error fetching Solscan trending: {e}")
            
            return large_trades[:5]  # Limit results
            
        except Exception as e:
            logger.error(f"Error fetching Solscan large trades: {e}")
            return []
    
    def _get_volume_spike_trades(self) -> List[Dict]:
        """Get volume spike trades from our own discovered tokens"""
        try:
            # This would analyze tokens we've discovered for volume spikes
            # For now, return empty but structure is ready
            volume_trades = []
            
            # TODO: Implement volume spike detection from discovered tokens
            # This would compare current volume to historical averages
            
            return volume_trades
            
        except Exception as e:
            logger.error(f"Error detecting volume spikes: {e}")
            return []
    
    def _process_smart_trade(self, trade: Dict):
        """Process and store a smart trade"""
        try:
            wallet = trade.get('wallet', 'unknown')
            token_address = trade.get('token_address', '')
            value_usd = trade.get('value_usd', 0)
            tx_hash = trade.get('tx_hash', '')
            tags = trade.get('tags', [])
            
            # Store the trade
            self.storage.save_smart_trade(wallet, token_address, value_usd, tx_hash, tags)
            
            # Check if this indicates smart accumulation
            if self._is_smart_accumulation(trade):
                symbol = trade.get('symbol', token_address[:8] if token_address else 'Unknown')
                source = trade.get('source', 'unknown')
                
                logger.info(f"🐋 Smart Money Alert: {source} detected whale activity in "
                          f"{symbol} - ${value_usd:,.0f} ({', '.join(tags[:3])})")
                
                self.storage.flag_token_smart_accumulation(token_address, wallet, tags)
                
        except Exception as e:
            logger.error(f"Error processing smart trade: {e}")
    
    def _is_smart_accumulation(self, trade: Dict) -> bool:
        """Determine if trade indicates smart money accumulation"""
        try:
            value_usd = trade.get('value_usd', 0)
            tags = trade.get('tags', [])
            confidence = trade.get('confidence', 'medium')
            
            # Criteria for smart accumulation
            large_value = value_usd > 50000  # $50k+ transactions
            whale_indicators = any(tag in ['whale_activity', 'volume_spike', 'large_sol_movement', 'high'] 
                                 for tag in tags)
            high_confidence = 'high' in tags or confidence == 'high'
            
            return (large_value and whale_indicators) or high_confidence
            
        except Exception:
            return False


class SmartMoneyTracker:
    """Enhanced smart money tracker with GMGN + alternatives"""
    
    def __init__(self, gmgn_client, storage):
        self.gmgn = gmgn_client
        self.storage = storage
        self.alternative_tracker = AlternativeSmartMoneyTracker(storage)
        logger.info("Smart money tracker initialized with alternative sources")
    
    def monitor_smart_trades(self):
        """Monitor smart trades with GMGN fallback to alternatives"""
        try:
            # Try GMGN first (will likely fail but worth attempting)
            gmgn_success = False
            
            try:
                smart_trades = self.gmgn.fetch_smart_trades()
                
                if smart_trades and smart_trades.get("trades"):
                    logger.info(f"GMGN: Found {len(smart_trades['trades'])} smart trades")
                    for trade in smart_trades.get("trades", []):
                        self._process_gmgn_trade(trade)
                    gmgn_success = True
                    
            except Exception as e:
                logger.debug(f"GMGN unavailable: {str(e)[:100]}...")
            
            # Always run alternative sources (they provide different insights)
            if not gmgn_success:
                logger.info("Using alternative smart money sources")
            else:
                logger.info("Supplementing GMGN with alternative sources")
                
            self.alternative_tracker.monitor_smart_trades()
                
        except Exception as e:
            logger.error(f"Smart money monitoring error: {e}")
    
    def _process_gmgn_trade(self, trade):
        """Process GMGN trade (original functionality)"""
        try:
            wallet = trade.get("wallet", "")
            token = trade.get("token_address", "")
            value = trade.get("value_usd", 0)
            tx_hash = trade.get("tx_hash", "")
            
            # Get wallet tags if available
            try:
                tags = self.gmgn.fetch_wallet_tags(wallet).get("tags", [])
            except:
                tags = ["gmgn_trade"]
            
            self.storage.save_smart_trade(wallet, token, value, tx_hash, tags)
            
            if self.is_experienced_wallet(tags):
                logger.info(f"🎯 GMGN Smart Money: Experienced wallet {wallet[:8]}... "
                          f"traded {token[:8]}... for ${value:,.0f}")
                self.storage.flag_token_smart_accumulation(token, wallet, tags)
                
        except Exception as e:
            logger.error(f"Error processing GMGN trade: {e}")
    
    def is_experienced_wallet(self, tags):
        """Check if wallet shows experience (original functionality)"""
        try:
            keywords = ["early investor", "insider", "whale", "vc", "dex founder", "smart money"]
            return any(any(k in str(tag).lower() for k in keywords) for tag in tags)
        except:
            return False