# main.py - Updated with comprehensive Solana memecoin discovery

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
from token_discovery import TokenDiscovery

from api_clients.gmgn import GMGNClient

# Your existing imports
from config import API_KEYS, DB_PATH, FETCH_INTERVAL
from filters import filter_tokens_batch, get_filter_stats
from smart_money import SmartMoneyTracker
from storage import Storage
from technicals import Technicals
from trader import Trader

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("trading_bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class TradingBot:
    """Main trading bot with comprehensive Solana memecoin discovery"""

    def __init__(self):
        # Initialize all components
        self.storage = Storage(DB_PATH)
        self.gmgn = GMGNClient()
        self.smart_tracker = SmartMoneyTracker(self.gmgn, self.storage)
        self.technicals = Technicals()
        self.trader = Trader(self.gmgn, self.storage)
        self.token_discovery = TokenDiscovery(config=None)  # Pass your config here

        # Performance tracking
        self.cycle_count = 0
        self.total_tokens_discovered = 0
        self.total_tokens_filtered = 0
        self.total_trades_executed = 0

        logger.info("Trading bot initialized successfully")

    def authenticate(self):
        """Authenticate with all services"""
        try:
            self.gmgn.authenticate_telegram(API_KEYS["telegram_token"])
            self.gmgn.authenticate_wallet(API_KEYS["wallet_address"])
            logger.info("Authentication completed")
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            raise

    def discover_and_filter_tokens(self) -> List[Dict[str, Any]]:
        """Comprehensive token discovery and filtering"""
        logger.info("=" * 60)
        logger.info(f"CYCLE {self.cycle_count + 1} - Starting token discovery")
        logger.info("=" * 60)

        # STEP 1: Discover tokens from all sources
        start_time = time.time()
        all_discovered_tokens = self.token_discovery.discover_all_tokens(max_workers=6)
        discovery_time = time.time() - start_time

        self.total_tokens_discovered += len(all_discovered_tokens)
        logger.info(
            f"✅ Discovery complete: {len(all_discovered_tokens)} tokens in {discovery_time:.1f}s"
        )

        # STEP 2: Apply comprehensive filtering
        start_time = time.time()
        filtered_tokens = filter_tokens_batch(
            tokens=all_discovered_tokens,
            max_tokens=200,  # Process top 200 tokens
            min_score=0.25,  # Minimum quality score
        )
        filter_time = time.time() - start_time

        self.total_tokens_filtered += len(filtered_tokens)
        logger.info(
            f"✅ Filtering complete: {len(filtered_tokens)} tokens passed in {filter_time:.1f}s"
        )

        # STEP 3: Display filter statistics
        if filtered_tokens:
            stats = get_filter_stats(filtered_tokens)
            logger.info(f"📊 Filter Stats:")
            logger.info(f"   Average Score: {stats['score_stats']['average']:.3f}")
            logger.info(
                f"   Average Age: {stats['age_stats']['average_hours']:.1f} hours"
            )
            logger.info(
                f"   Total Volume: ${stats['volume_stats']['total_volume']:,.0f}"
            )
            logger.info(f"   Sources: {stats['source_breakdown']}")

        return filtered_tokens

    def analyze_token_technicals(self, token_data: Dict[str, Any]) -> str:
        """Analyze token technicals and return rating"""
        try:
            # Use price history if available
            if "price_history" in token_data and token_data["price_history"]:
                prices = pd.Series(token_data["price_history"])
                if len(prices) >= 14:  # Need enough data for RSI
                    rsi = self.technicals.compute_rsi(prices)
                    slope = self.technicals.compute_ema_slope(prices)
                    upper_band, lower_band = self.technicals.compute_volatility_band(
                        prices
                    )
                    rating = self.technicals.classify_trend(
                        rsi, slope, prices, upper_band, lower_band
                    )
                    return rating

            # Fallback to simple price change analysis
            price_change = float(token_data.get("price_change_24h", 0))
            volume = float(token_data.get("daily_volume_usd", 0))
            filter_score = float(token_data.get("filter_score", 0))

            # Multi-factor rating system
            if price_change > 20 and volume > 50000 and filter_score > 0.6:
                return "bullish"
            elif price_change < -15 and volume > 10000:
                return "bearish"
            elif price_change > 10 and filter_score > 0.5:
                return "bullish"
            elif price_change > 5 and volume > 100000:
                return "bullish"
            else:
                return "neutral"

        except Exception as e:
            logger.error(f"Error in technical analysis: {str(e)}")
            return "neutral"

    def process_tokens(self, filtered_tokens: List[Dict[str, Any]]):
        """Process filtered tokens for trading opportunities"""
        logger.info(f"🔍 Processing {len(filtered_tokens)} filtered tokens...")

        processed_count = 0
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0

        for i, token_data in enumerate(filtered_tokens):
            try:
                token_address = token_data.get("address")
                symbol = token_data.get("symbol", "Unknown")
                source = token_data.get("discovery_source", "unknown")
                score = token_data.get("filter_score", 0)

                if not token_address:
                    continue

                logger.info(f"📈 Token {i+1}/{len(filtered_tokens)}: {symbol}")
                logger.info(f"   Address: {token_address}")
                logger.info(f"   Source: {source}")
                logger.info(f"   Filter Score: {score:.3f}")

                # Save token data to database
                self.storage.save_token_data(
                    token_address, json.dumps(token_data), source
                )

                # Technical analysis
                rating = self.analyze_token_technicals(token_data)

                # Update counters
                if rating == "bullish":
                    bullish_count += 1
                elif rating == "bearish":
                    bearish_count += 1
                else:
                    neutral_count += 1

                logger.info(f"   Rating: {rating.upper()}")

                # Additional context
                volume = token_data.get("daily_volume_usd", 0)
                price_change = token_data.get("price_change_24h", 0)
                age_hours = token_data.get("age_hours", "Unknown")

                logger.info(
                    f"   Volume: ${volume:,.0f} | Change: {price_change:+.1f}% | Age: {age_hours}h"
                )

                # Execute trading decision
                if rating in ["bullish", "bearish"]:
                    try:
                        self.trader.execute_trade(token_address, rating)
                        self.total_trades_executed += 1
                        logger.info(f"   ✅ Trade executed: {rating}")
                    except Exception as e:
                        logger.error(f"   ❌ Trade failed: {str(e)}")
                else:
                    logger.info(f"   ⏸️  No trade: neutral rating")

                processed_count += 1

                # Add small delay to avoid overwhelming APIs
                time.sleep(0.1)

            except Exception as e:
                logger.error(
                    f"Error processing token {token_data.get('symbol', 'unknown')}: {str(e)}"
                )

        logger.info(f"✅ Processing complete:")
        logger.info(f"   Processed: {processed_count} tokens")
        logger.info(
            f"   Bullish: {bullish_count} | Bearish: {bearish_count} | Neutral: {neutral_count}"
        )
        logger.info(f"   Trades executed: {self.total_trades_executed}")

    def monitor_smart_money(self):
        """Monitor smart money activity"""
        try:
            logger.info("🧠 Monitoring smart money activity...")
            self.smart_tracker.monitor_smart_trades()
        except Exception as e:
            logger.error(f"Smart money monitoring failed: {str(e)}")

    def print_session_stats(self):
        """Print overall session statistics"""
        logger.info("=" * 60)
        logger.info("SESSION STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Cycles completed: {self.cycle_count}")
        logger.info(f"Total tokens discovered: {self.total_tokens_discovered:,}")
        logger.info(f"Total tokens filtered: {self.total_tokens_filtered:,}")
        logger.info(f"Total trades executed: {self.total_trades_executed}")

        if self.cycle_count > 0:
            avg_discovered = self.total_tokens_discovered / self.cycle_count
            avg_filtered = self.total_tokens_filtered / self.cycle_count
            filter_rate = (
                self.total_tokens_filtered / max(self.total_tokens_discovered, 1)
            ) * 100

            logger.info(
                f"Average tokens per cycle: {avg_discovered:.0f} discovered, {avg_filtered:.0f} filtered"
            )
            logger.info(f"Filter success rate: {filter_rate:.1f}%")

        logger.info("=" * 60)

    def run_single_cycle(self):
        """Run one complete discovery and trading cycle"""
        cycle_start = time.time()

        try:
            # 1. Discover and filter tokens
            filtered_tokens = self.discover_and_filter_tokens()

            if not filtered_tokens:
                logger.warning("⚠️  No tokens passed filtering this cycle")
                return

            # 2. Process tokens for trading
            self.process_tokens(filtered_tokens)

            # 3. Monitor smart money
            self.monitor_smart_money()

            # 4. Cycle complete
            cycle_time = time.time() - cycle_start
            self.cycle_count += 1

            logger.info(f"🎯 Cycle {self.cycle_count} complete in {cycle_time:.1f}s")

        except Exception as e:
            logger.error(f"Error in trading cycle: {str(e)}")
            raise

    def run(self):
        """Main bot loop"""
        logger.info("🚀 Starting Solana Memecoin Trading Bot")
        logger.info(f"   Fetch interval: {FETCH_INTERVAL} seconds")
        logger.info(f"   Database: {DB_PATH}")

        # Authenticate
        self.authenticate()

        try:
            while True:
                # Run trading cycle
                self.run_single_cycle()

                # Print stats every 10 cycles
                if self.cycle_count % 10 == 0:
                    self.print_session_stats()

                # Sleep until next cycle
                logger.info(
                    f"😴 Sleeping for {FETCH_INTERVAL} seconds until next cycle..."
                )
                time.sleep(FETCH_INTERVAL)

        except KeyboardInterrupt:
            logger.info("\n🛑 Bot stopped by user")
            self.print_session_stats()
        except Exception as e:
            logger.error(f"💥 Bot crashed: {str(e)}")
            self.print_session_stats()
            raise


def main():
    """Entry point"""
    bot = TradingBot()
    bot.run()


if __name__ == "__main__":
    main()
