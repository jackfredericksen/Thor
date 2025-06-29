# main.py

import time
import json
import pandas as pd
import logging
from typing import List, Dict

from config import DB_PATH, FETCH_INTERVAL, API_KEYS, validate_config
from storage import Storage
from filters import passes_filters
from technicals import Technicals
from trader import Trader
from smart_money import SmartMoneyTracker
from api_clients.gmgn import GMGNClient
from api_clients.token_discovery import TokenDiscoveryClient, TokenDiscoveryError


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TradingBot:
    def __init__(self):
        # Validate configuration on startup
        config_warnings = validate_config()
        if config_warnings:
            logger.warning("Configuration issues found:")
            for warning in config_warnings:
                logger.warning(f"  ⚠️ {warning}")
        
        # Initialize components
        self.storage = Storage(DB_PATH)
        self.gmgn = GMGNClient()
        self.token_discovery = TokenDiscoveryClient()
        self.smart_tracker = SmartMoneyTracker(self.gmgn, self.storage)
        self.technicals = Technicals()
        self.trader = Trader(self.gmgn, self.storage)
        
        # Track statistics
        self.stats = {
            'tokens_processed': 0,
            'tokens_filtered': 0,
            'trades_executed': 0,
            'api_errors': 0,
            'start_time': time.time()
        }
        
        # Initialize authentication (if API keys are available)
        self._setup_authentication()
        
        logger.info("🚀 Trading Bot initialized successfully")
    
    def _setup_authentication(self):
        """Set up authentication for APIs that require it"""
        try:
            if API_KEYS["telegram_token"] != "YOUR_TELEGRAM_BOT_TOKEN":
                self.gmgn.authenticate_telegram(API_KEYS["telegram_token"])
                logger.info("✅ Telegram authentication configured")
            
            if API_KEYS["wallet_address"] != "YOUR_WALLET_ADDRESS":
                self.gmgn.authenticate_wallet(API_KEYS["wallet_address"])
                logger.info("✅ Wallet authentication configured")
                
        except Exception as e:
            logger.warning(f"Authentication setup failed: {e}")
    
    def discover_tokens(self) -> List[Dict]:
        """Discover new tokens using the robust token discovery client"""
        try:
            logger.info("🔍 Discovering new tokens...")
            tokens = self.token_discovery.discover_new_tokens()
            
            if not tokens:
                logger.warning("No tokens discovered, using fallback data")
                return self._get_fallback_tokens()
            
            logger.info(f"✅ Discovered {len(tokens)} tokens from various sources")
            return tokens
            
        except TokenDiscoveryError as e:
            logger.error(f"Token discovery error: {e}")
            self.stats['api_errors'] += 1
            return self._get_fallback_tokens()
        
        except Exception as e:
            logger.error(f"Unexpected error in token discovery: {e}")
            self.stats['api_errors'] += 1
            return self._get_fallback_tokens()
    
    def _get_fallback_tokens(self) -> List[Dict]:
        """Return fallback tokens when discovery fails"""
        logger.info("Using fallback token data for testing")
        return [
            {
                'address': 'So11111111111111111111111111111111111112',
                'symbol': 'SOL',
                'name': 'Solana',
                'price': 100.50,
                'volume': 50000000,
                'market_cap': 40000000000,
                'source': 'fallback'
            },
            {
                'address': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                'symbol': 'USDC',
                'name': 'USD Coin',
                'price': 1.00,
                'volume': 100000000,
                'market_cap': 25000000000,
                'source': 'fallback'
            }
        ]
    
    def process_token(self, token_data: Dict) -> bool:
        """Process a single token through the trading pipeline"""
        try:
            token_address = token_data.get('address')
            if not token_address:
                logger.warning("Token missing address, skipping")
                return False
            
            # Convert discovered token data to the format expected by filters
            token_info = {
                'daily_volume_usd': token_data.get('volume', 0),
                'age_hours': 24,  # Assume recent for discovered tokens
                'holder_count': 8000,  # Mock data - would need real holder count API
                'price_history': self._generate_mock_price_history(token_data.get('price', 1.0))
            }
            
            # Apply filters
            if not passes_filters(token_info):
                logger.debug(f"Token {token_data.get('symbol', token_address[:8])} failed filters")
                self.stats['tokens_filtered'] += 1
                return False
            
            logger.info(f"✅ Token {token_data.get('symbol', token_address[:8])} passed filters")
            
            # Save token data
            self.storage.save_token_data(
                token_address, 
                json.dumps(token_data), 
                token_data.get('source', 'discovery')
            )
            
            # Perform technical analysis
            prices = token_info['price_history']
            rsi = self.technicals.compute_rsi(prices)
            slope = self.technicals.compute_ema_slope(prices)
            upper_band, lower_band = self.technicals.compute_volatility_band(prices)
            rating = self.technicals.classify_trend(rsi, slope, prices, upper_band, lower_band)
            
            logger.info(f"📊 Technical analysis for {token_data.get('symbol', token_address[:8])}: {rating} (RSI: {rsi:.2f})")
            
            # Execute trade based on rating
            if rating != "neutral":
                self.trader.execute_trade(token_address, rating)
                self.stats['trades_executed'] += 1
            
            self.stats['tokens_processed'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error processing token {token_data.get('address', 'unknown')}: {e}")
            return False
    
    def _generate_mock_price_history(self, current_price: float) -> pd.Series:
        """Generate mock price history for technical analysis"""
        import random
        
        # Generate 15 price points with some volatility
        prices = []
        price = current_price * 0.8  # Start 20% lower
        
        for i in range(15):
            # Add some random walk with slight upward bias
            change = random.uniform(-0.05, 0.07)  # -5% to +7% change
            price *= (1 + change)
            prices.append(price)
        
        return pd.Series(prices)
    
    def monitor_smart_money(self):
        """Monitor smart money activities"""
        try:
            logger.debug("👥 Monitoring smart money activities...")
            self.smart_tracker.monitor_smart_trades()
        except Exception as e:
            logger.error(f"Smart money monitoring error: {e}")
            self.stats['api_errors'] += 1
    
    def print_statistics(self):
        """Print bot statistics"""
        runtime = time.time() - self.stats['start_time']
        runtime_hours = runtime / 3600
        
        logger.info("📈 Bot Statistics:")
        logger.info(f"  Runtime: {runtime_hours:.2f} hours")
        logger.info(f"  Tokens processed: {self.stats['tokens_processed']}")
        logger.info(f"  Tokens filtered out: {self.stats['tokens_filtered']}")
        logger.info(f"  Trades executed: {self.stats['trades_executed']}")
        logger.info(f"  API errors: {self.stats['api_errors']}")
        
        if self.stats['tokens_processed'] > 0:
            filter_rate = (self.stats['tokens_filtered'] / (self.stats['tokens_processed'] + self.stats['tokens_filtered'])) * 100
            logger.info(f"  Filter rate: {filter_rate:.1f}%")
    
    def run(self):
        """Main bot loop"""
        logger.info("🤖 Starting trading bot main loop...")
        logger.info(f"Fetch interval: {FETCH_INTERVAL} seconds")
        
        cycle_count = 0
        
        try:
            while True:
                cycle_start = time.time()
                cycle_count += 1
                
                logger.info(f"\n🔄 Starting cycle #{cycle_count}")
                
                # Discover new tokens
                discovered_tokens = self.discover_tokens()
                
                # Process each token
                processed_count = 0
                for token_data in discovered_tokens:
                    if self.process_token(token_data):
                        processed_count += 1
                
                logger.info(f"📊 Processed {processed_count}/{len(discovered_tokens)} tokens in cycle #{cycle_count}")
                
                # Monitor smart money
                self.monitor_smart_money()
                
                # Print statistics every 10 cycles
                if cycle_count % 10 == 0:
                    self.print_statistics()
                
                # Wait for next cycle
                cycle_time = time.time() - cycle_start
                sleep_time = max(0, FETCH_INTERVAL - cycle_time)
                
                if sleep_time > 0:
                    logger.info(f"💤 Cycle completed in {cycle_time:.2f}s, sleeping for {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                else:
                    logger.warning(f"⚠️ Cycle took {cycle_time:.2f}s, longer than {FETCH_INTERVAL}s interval!")
                
        except KeyboardInterrupt:
            logger.info("\n⏹️ Bot stopped by user")
        except Exception as e:
            logger.error(f"💥 Fatal error in main loop: {e}")
            raise
        finally:
            self.print_statistics()
            logger.info("🏁 Trading bot shutdown complete")


def main():
    """Main entry point"""
    try:
        bot = TradingBot()
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise


if __name__ == "__main__":
    main()