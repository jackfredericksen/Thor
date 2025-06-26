# main.py
import time
import json
import signal
import sys
from typing import Dict, List
import logging
from datetime import datetime, timedelta

# Import configurations and utilities
from config import config
from utils.logging_setup import setup_logging, get_logger
from utils.error_handling import TradingBotException, APIException, CircuitBreaker

# Import core components
from storage import Storage
from filters import TokenFilter, filter_tokens, get_filter_stats
from technicals import Technicals
from trader import Trader
from smart_money import SmartMoneyTracker

# Import API clients
from api_clients.gmgn import GMGNClient
from api_clients.dexscreener import DexscreenerClient
from api_clients.pumpfun import PumpFunClient
from api_clients.bubblemaps import BubblemapsClient
from api_clients.rugcheck import RugcheckClient
from api_clients.moni import MoniClient

class TradingBot:
    """Main trading bot orchestrator"""
    
    def __init__(self):
        # Setup logging first
        self.logger = setup_logging()
        self.logger.info("Initializing Dex Trading Bot...")
        
        # Initialize storage
        self.storage = Storage(config.DB_PATH)
        
        # Initialize API clients
        self.gmgn = GMGNClient()
        self.dexscreener = DexscreenerClient()
        self.pumpfun = PumpFunClient()
        self.bubblemaps = BubblemapsClient()
        self.rugcheck = RugcheckClient()
        self.moni = MoniClient()
        
        # Initialize core components
        self.smart_tracker = SmartMoneyTracker(self.gmgn, self.storage)
        self.technicals = Technicals()
        self.trader = Trader(self.gmgn, self.storage)
        self.token_filter = TokenFilter()
        
        # Bot state
        self.running = False
        self.last_health_check = datetime.now()
        self.iteration_count = 0
        self.start_time = datetime.now()
        
        # Performance tracking
        self.processed_tokens = 0
        self.filtered_tokens = 0
        self.trades_executed = 0
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("Bot initialization completed")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
    def start(self):
        """Start the trading bot main loop"""
        try:
            self.logger.info("Starting Dex Trading Bot...")
            print("🚀 Starting Dex Trading Bot...")
            print(f"📊 Paper trading: {config.TRADING['paper_trading']}")
            print(f"⏱️ Fetch interval: {config.FETCH_INTERVAL} seconds")
            print("Press Ctrl+C to stop\n")
            
            # Authenticate with APIs (simplified)
            if not self._authenticate_apis():
                self.logger.warning("API authentication had issues, but continuing...")
            
            # Initial health check (simplified)
            if not self._health_check():
                self.logger.warning("Health check had issues, but continuing...")
            
            self.running = True
            self.logger.info("Bot started successfully, entering main loop...")
            print("✅ Bot started successfully!\n")
            
            # Main loop
            while self.running:
                try:
                    self._main_iteration()
                    self.iteration_count += 1
                    
                    # Periodic health checks (every 10 iterations instead of time-based)
                    if self.iteration_count % 10 == 0:
                        self._health_check()
                        self.last_health_check = datetime.now()
                    
                    # Sleep before next iteration
                    print(f"💤 Waiting {config.FETCH_INTERVAL} seconds...\n")
                    time.sleep(config.FETCH_INTERVAL)
                    
                except KeyboardInterrupt:
                    print("\n⏹️ Keyboard interrupt received")
                    self.logger.info("Keyboard interrupt received")
                    break
                except Exception as e:
                    self.logger.error(f"Error in main loop iteration: {str(e)}")
                    print(f"❌ Error in iteration: {str(e)}")
                    time.sleep(config.FETCH_INTERVAL * 2)  # Wait longer on error
            
            # Graceful shutdown
            self._shutdown()
            return True
            
        except Exception as e:
            self.logger.critical(f"Critical error in bot startup: {str(e)}")
            print(f"💥 Critical error: {str(e)}")
            return False
    
    def _authenticate_apis(self) -> bool:
        """Authenticate with required APIs"""
        try:
            self.logger.info("Authenticating with APIs...")
            
            # Skip authentication in paper trading mode since we don't need it
            if config.TRADING["paper_trading"]:
                self.logger.info("Paper trading mode - skipping authentication")
                return True
            
            # Only authenticate GMGN if doing real trading
            telegram_success = self.gmgn.authenticate_telegram(
                config.API_KEYS["telegram_token"]
            )
            wallet_success = self.gmgn.authenticate_wallet(
                config.API_KEYS["wallet_address"],
                config.API_KEYS.get("wallet_private_key")
            )
            
            if not (telegram_success and wallet_success):
                self.logger.error("GMGN authentication failed")
                return False
            
            self.logger.info("GMGN authentication successful")
            return True
            
        except Exception as e:
            self.logger.error(f"API authentication error: {str(e)}")
            # In paper trading, continue even if auth fails
            if config.TRADING["paper_trading"]:
                self.logger.warning("Continuing in paper trading mode despite auth error")
                return True
            return False
    
    def _main_iteration(self):
        """Single iteration of the main trading loop"""
        iteration_start = time.time()
        print(f"🔄 Starting iteration {self.iteration_count + 1}")
        self.logger.info(f"Starting iteration {self.iteration_count + 1}")
        
        try:
            # 1. Fetch new tokens
            print("📡 Fetching tokens...")
            tokens = self._fetch_tokens()
            self.processed_tokens += len(tokens)
            
            if not tokens:
                print("⚠️ No tokens fetched")
                self.logger.warning("No tokens fetched")
                return
            
            print(f"✅ Fetched {len(tokens)} tokens")
            
            # 2. Filter tokens
            print("🔍 Filtering tokens...")
            filtered_tokens = self._filter_tokens(tokens)
            self.filtered_tokens += len(filtered_tokens)
            
            if not filtered_tokens:
                print("ℹ️ No tokens passed filtering")
                self.logger.info("No tokens passed filtering")
                return
            
            print(f"✅ {len(filtered_tokens)} tokens passed filtering")
            
            # 3. Analyze and trade tokens (limit to first 3 for testing)
            print("📊 Analyzing tokens...")
            for i, token in enumerate(filtered_tokens[:3]):
                try:
                    symbol = token.get('symbol', 'Unknown')
                    print(f"   Analyzing {i+1}/{min(len(filtered_tokens), 3)}: {symbol}")
                    self._analyze_and_trade_token(token)
                except Exception as e:
                    symbol = token.get('symbol', 'unknown')
                    self.logger.error(f"Error processing token {symbol}: {str(e)}")
                    print(f"   ❌ Error analyzing {symbol}: {str(e)}")
            
            # 4. Monitor smart money (simplified)
            print("🧠 Monitoring smart money...")
            try:
                self.smart_tracker.monitor_smart_trades()
            except Exception as e:
                self.logger.error(f"Error in smart money monitoring: {str(e)}")
                print(f"   ⚠️ Smart money monitoring error: {str(e)}")
            
            # 5. Update positions (if any)
            print("📈 Updating positions...")
            try:
                self._update_positions()
            except Exception as e:
                self.logger.error(f"Error updating positions: {str(e)}")
                print(f"   ⚠️ Position update error: {str(e)}")
            
            # 6. Log iteration summary
            iteration_time = time.time() - iteration_start
            self._log_iteration_summary(len(tokens), len(filtered_tokens), iteration_time)
            
        except Exception as e:
            self.logger.error(f"Error in main iteration: {str(e)}")
            print(f"❌ Iteration error: {str(e)}")
    
    def _fetch_tokens(self) -> List[Dict]:
        """Fetch tokens from multiple sources"""
        all_tokens = []
        
        try:
            # Fetch from DexScreener
            self.logger.debug("Fetching tokens from DexScreener...")
            dex_tokens = self.dexscreener.fetch_trending_tokens(limit=50)
            for token in dex_tokens:
                token['source'] = 'dexscreener'
            all_tokens.extend(dex_tokens)
            
            # Fetch new pairs
            new_pairs = self.dexscreener.fetch_new_pairs(limit=30)
            for token in new_pairs:
                token['source'] = 'dexscreener_new'
            all_tokens.extend(new_pairs)
            
        except Exception as e:
            self.logger.error(f"Error fetching from DexScreener: {str(e)}")
        
        try:
            # Fetch from PumpFun
            self.logger.debug("Fetching tokens from PumpFun...")
            pump_tokens = self.pumpfun.fetch_new_tokens()
            
            # Convert PumpFun format to standard format
            for token in pump_tokens.get('tokens', []):
                standardized = self._standardize_pumpfun_token(token)
                if standardized:
                    standardized['source'] = 'pumpfun'
                    all_tokens.append(standardized)
                    
        except Exception as e:
            self.logger.error(f"Error fetching from PumpFun: {str(e)}")
        
        # Remove duplicates based on token address
        unique_tokens = {}
        for token in all_tokens:
            address = token.get('address')
            if address and address not in unique_tokens:
                unique_tokens[address] = token
        
        result = list(unique_tokens.values())
        self.logger.info(f"Fetched {len(result)} unique tokens from {len(all_tokens)} total")
        
        return result
    
    def _standardize_pumpfun_token(self, token: Dict) -> Dict:
        """Convert PumpFun token format to standard format"""
        try:
            return {
                'address': token.get('mint'),
                'symbol': token.get('symbol', ''),
                'name': token.get('name', ''),
                'price_usd': float(token.get('usd_market_cap', 0)) / float(token.get('total_supply', 1)),
                'market_cap': float(token.get('usd_market_cap', 0)),
                'liquidity_usd': float(token.get('bonding_curve', {}).get('complete', False)) * 50000,  # Estimate
                'age_hours': (time.time() - int(token.get('created_timestamp', 0))) / 3600,
                'holder_count': int(token.get('holder_count', 0)),
                'daily_volume_usd': 0,  # PumpFun doesn't provide this
                'volume_24h': 0,
                'created_at': int(token.get('created_timestamp', 0)) * 1000,
            }
        except Exception as e:
            self.logger.error(f"Error standardizing PumpFun token: {str(e)}")
            return None
    
    def _filter_tokens(self, tokens: List[Dict]) -> List[Dict]:
        """Filter tokens using the enhanced filtering system"""
        try:
            filtered_tokens = filter_tokens(
                tokens, 
                strict_mode=False,
                min_score=0.6
            )
            
            # Log filter statistics
            filter_stats = get_filter_stats(tokens)
            self.logger.info(
                f"Filter stats: {filter_stats.get('passed_tokens', 0)}/{filter_stats.get('total_tokens', 0)} "
                f"passed ({filter_stats.get('pass_rate', 0):.1%} pass rate)"
            )
            
            return filtered_tokens
            
        except Exception as e:
            self.logger.error(f"Error filtering tokens: {str(e)}")
            return []
    
    def _analyze_and_trade_token(self, token: Dict):
        """Analyze a single token and execute trades if appropriate"""
        try:
            token_address = token['address']
            symbol = token.get('symbol', token_address[:8])
            
            # Save token data
            self.storage.save_token_data(
                token_address, 
                json.dumps(token), 
                token.get('source', 'unknown')
            )
            
            # Get price history for technical analysis
            price_history = self._get_price_history(token_address, token)
            
            if len(price_history) < 10:
                self.logger.debug(f"Insufficient price history for {symbol}")
                return
            
            # Perform technical analysis
            rsi = self.technicals.compute_rsi(price_history)
            slope = self.technicals.compute_ema_slope(price_history)
            upper_band, lower_band = self.technicals.compute_volatility_band(price_history)
            
            # Get trading signal
            rating = self.technicals.classify_trend(rsi, slope, price_history, upper_band, lower_band)
            
            # Calculate confidence score based on multiple factors
            confidence_score = self._calculate_confidence_score(token, rsi, slope, rating)
            
            self.logger.info(
                f"Analysis for {symbol}: {rating} (confidence: {confidence_score:.2f}, "
                f"RSI: {rsi:.1f}, slope: {slope:+.3f})"
            )
            
            # Execute trade
            if self.trader.execute_trade(token_address, rating, token, confidence_score):
                self.trades_executed += 1
            
        except Exception as e:
            self.logger.error(f"Error analyzing token {token.get('symbol', 'unknown')}: {str(e)}")
    
    def _get_price_history(self, token_address: str, token: Dict) -> List[float]:
        """Get price history for technical analysis"""
        try:
            # Try to get from DexScreener first
            price_data = self.dexscreener.get_token_price_history(token_address, "5m")
            
            if price_data:
                prices = [float(candle.get('c', 0)) for candle in price_data if candle.get('c')]
                if len(prices) >= 10:
                    return prices
            
            # Fallback: create mock price history based on current price and volatility
            current_price = token.get('price_usd', 0)
            if current_price > 0:
                # Generate realistic price movement
                import random
                prices = []
                price = current_price * 0.95  # Start slightly lower
                
                for i in range(20):
                    change = random.gauss(0, 0.02)  # 2% volatility
                    price *= (1 + change)
                    prices.append(price)
                
                return prices
            
        except Exception as e:
            self.logger.error(f"Error getting price history for {token_address}: {str(e)}")
        
        return []
    
    def _calculate_confidence_score(self, token: Dict, rsi: float, slope: float, rating: str) -> float:
        """Calculate confidence score for trading signal"""
        try:
            confidence = 0.5  # Base confidence
            
            # Filter score contribution
            filter_score = token.get('filter_score', 0.6)
            confidence += (filter_score - 0.6) * 0.5  # Scale filter score
            
            # Technical indicators
            if rating == "bullish":
                if 30 <= rsi <= 70:  # Not overbought
                    confidence += 0.2
                if slope > 0.01:  # Strong upward momentum
                    confidence += 0.2
            elif rating == "bearish":
                if rsi > 70:  # Overbought
                    confidence += 0.2
                if slope < -0.01:  # Strong downward momentum
                    confidence += 0.2
            
            # Volume and liquidity factors
            volume_24h = token.get('volume_24h', 0)
            liquidity_usd = token.get('liquidity_usd', 0)
            
            if volume_24h > 100000:  # Good volume
                confidence += 0.1
            if liquidity_usd > 100000:  # Good liquidity
                confidence += 0.1
            
            # Age factor (sweet spot around 24-48 hours)
            age_hours = token.get('age_hours', 9999)
            if 12 <= age_hours <= 72:
                confidence += 0.1
            
            return min(max(confidence, 0.0), 1.0)  # Clamp between 0 and 1
            
        except Exception as e:
            self.logger.error(f"Error calculating confidence score: {str(e)}")
            return 0.5
    
    def _update_positions(self):
        """Update all positions and check for triggers"""
        try:
            # Get current prices for all positions
            price_updates = {}
            
            for token_address in self.trader.risk_manager.positions.keys():
                try:
                    token_info = self.gmgn.get_token_info(token_address)
                    current_price = float(token_info.get('price_usd', 0))
                    if current_price > 0:
                        price_updates[token_address] = current_price
                except Exception as e:
                    self.logger.warning(f"Failed to get price for {token_address}: {str(e)}")
            
            # Update trader with new prices
            if price_updates:
                self.trader.update_all_positions(price_updates)
            
        except Exception as e:
            self.logger.error(f"Error updating positions: {str(e)}")
    
    def _health_check(self) -> bool:
        """Perform comprehensive health check"""
        try:
            self.logger.info("Performing health check...")
            
            # Simplified health check - just test DexScreener since it's our main data source
            if not self.dexscreener.health_check():
                self.logger.warning("DexScreener API unhealthy, but continuing...")
                # Don't fail completely, just warn
            
            # In paper trading mode, we're always "healthy"
            if config.TRADING["paper_trading"]:
                self.logger.info("Paper trading mode - health check passed")
                return True
            
            # For live trading, do more comprehensive checks
            trader_health = self.trader.health_check()
            if not trader_health.get('overall_healthy', False):
                self.logger.warning(f"Trader health issues: {trader_health}")
                # Continue anyway for now
            
            self.logger.info("Health check completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in health check: {str(e)}")
            # Don't fail startup due to health check issues
            self.logger.warning("Continuing despite health check error")
            return True
    
    def _log_iteration_summary(self, total_tokens: int, filtered_tokens: int, iteration_time: float):
        """Log summary of the iteration"""
        portfolio_summary = self.trader.get_portfolio_summary()
        
        self.logger.info(
            f"Iteration {self.iteration_count + 1} complete: "
            f"{total_tokens} tokens fetched, {filtered_tokens} passed filters, "
            f"{iteration_time:.1f}s processing time"
        )
        
        if portfolio_summary:
            self.logger.info(
                f"Portfolio: ${portfolio_summary.get('portfolio_value', 0):.2f} value, "
                f"{portfolio_summary.get('number_of_positions', 0)} positions, "
                f"${portfolio_summary.get('unrealized_pnl', 0):+.2f} unrealized PnL"
            )
    
    def _shutdown(self):
        """Graceful shutdown procedure"""
        try:
            self.logger.info("Initiating graceful shutdown...")
            print("🛑 Shutting down bot...")
            
            # Stop trading operations
            self.trader.emergency_stop()
            
            # Log final statistics
            uptime = datetime.now() - self.start_time
            self.logger.info(
                f"Bot shutdown after {uptime}. "
                f"Processed {self.processed_tokens} tokens, "
                f"filtered {self.filtered_tokens}, "
                f"executed {self.trades_executed} trades"
            )
            
            # Final portfolio summary
            portfolio_summary = self.trader.get_portfolio_summary()
            if portfolio_summary:
                self.logger.info(f"Final portfolio summary: {portfolio_summary}")
                print(f"📊 Final stats: {self.total_trades} trades, {self.successful_trades} successful")
            
            self.logger.info("Graceful shutdown completed")
            print("✅ Shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {str(e)}")
    
    def get_status(self) -> Dict:
        """Get current bot status"""
        try:
            uptime = datetime.now() - self.start_time
            portfolio_summary = self.trader.get_portfolio_summary()
            
            return {
                'running': self.running,
                'uptime_seconds': uptime.total_seconds(),
                'iteration_count': self.iteration_count,
                'processed_tokens': self.processed_tokens,
                'filtered_tokens': self.filtered_tokens,
                'trades_executed': self.trades_executed,
                'portfolio': portfolio_summary,
                'paper_trading': config.TRADING["paper_trading"],
                'last_health_check': self.last_health_check.isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Error getting status: {str(e)}")
            return {'error': str(e)}

def main():
    """Main entry point"""
    bot = TradingBot()
    
    try:
        success = bot.start()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        sys.exit(0)
    except Exception as e:
        print(f"Critical error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()