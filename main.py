# main.py - Thor with Terminal UI

import time
import json
import logging
import threading
from datetime import datetime
from typing import List, Dict, Any
from rich.live import Live

# Core imports
from config import DB_PATH, FETCH_INTERVAL, API_KEYS
from storage import Storage
from filters import filter_tokens_batch, get_filter_stats
from technicals import Technicals
from trader import Trader
from smart_money import SmartMoneyTracker
from api_clients.token_discovery import EnhancedTokenDiscovery as TokenDiscovery
from api_clients.gmgn import GMGNClient

# UI imports
from ui.dashboard import Dashboard
from ui.keyboard import KeyboardHandler
from ui.log_handler import DashboardLogHandler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
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
        self.trader = Trader(self.storage)  # Live trading with Solana
        self.token_discovery = TokenDiscovery(config=None)

        # Performance tracking
        self.cycle_count = 0
        self.total_tokens_discovered = 0
        self.total_tokens_filtered = 0
        self.total_trades_executed = 0
        self.start_time = time.time()

        # UI data tracking
        self.latest_filtered_tokens = []
        self.trade_history = []

        # Restore persisted open positions from DB into RiskManager
        self._restore_positions()

        # Start background position monitor
        self._running = True
        self._start_position_monitor()

        logger.info("Trading bot initialized successfully")

    def _restore_positions(self):
        """Load persisted positions from SQLite into RiskManager on startup."""
        try:
            rows = self.storage.load_positions()
            for row in rows:
                from risk_management import Position
                pos = Position(
                    symbol=row["symbol"],
                    quantity=row["quantity"],
                    entry_price=row["entry_price"],
                    current_price=row["current_price"],
                    peak_price=row["peak_price"],
                    partial_sold=row["partial_sold"],
                    entry_tx=row["entry_tx"],
                )
                self.trader.risk_manager.positions[row["token_address"]] = pos
            if rows:
                logger.info(f"Restored {len(rows)} open position(s) from database")
        except Exception as exc:
            logger.warning(f"Could not restore positions: {exc}")

    def _start_position_monitor(self):
        """Start the background thread that monitors open positions."""
        self._pos_thread = threading.Thread(
            target=self._position_monitor_loop,
            daemon=True,
            name="position-monitor",
        )
        self._pos_thread.start()
        logger.info("Position monitor started (10s interval)")

    def _position_monitor_loop(self):
        """Background loop: check open positions for TP/SL triggers every 10s."""
        while self._running:
            try:
                self._check_all_positions()
            except Exception as exc:
                logger.error(f"Position monitor error: {exc}")
            time.sleep(10)

    def _get_current_price(self, token_address: str) -> float:
        """Fetch current token price from DexScreener."""
        try:
            import requests as _req
            url = (
                f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            )
            resp = _req.get(url, timeout=5)
            if resp.status_code == 200:
                pairs = resp.json().get("pairs") or []
                # Pick highest-liquidity Solana pair
                sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
                if sol_pairs:
                    best = max(
                        sol_pairs,
                        key=lambda p: float((p.get("liquidity") or {}).get("usd", 0))
                    )
                    return float(best.get("priceUsd", 0) or 0)
        except Exception:
            pass
        return 0.0

    def _check_all_positions(self):
        """Check every open position for TP/trailing-stop/SL triggers."""
        from config import TradingConfig
        positions = self.trader.risk_manager.positions
        if not positions:
            return

        for token_address, position in list(positions.items()):
            price = self._get_current_price(token_address)
            if not price:
                continue

            position.current_price = price
            if price > position.peak_price:
                position.peak_price = price
                self.storage.update_position(
                    token_address, current_price=price, peak_price=price
                )
            else:
                self.storage.update_position(token_address, current_price=price)

            profit_pct = (price - position.entry_price) / position.entry_price

            # TP1: sell 50% at 2x
            if (
                profit_pct >= TradingConfig.TP1_MULTIPLIER - 1
                and not (position.partial_sold & 1)
            ):
                logger.info(
                    f"🎯 TP1 triggered for {position.symbol} "
                    f"(+{profit_pct:.0%})"
                )
                self.trader._execute_partial_sell(
                    token_address, 0.5, price, reason="TP1 2x"
                )
                position.partial_sold |= 1
                self.storage.update_position(
                    token_address, partial_sold=position.partial_sold
                )

            # TP2: sell 50% of remainder (25% original) at 5x
            elif (
                profit_pct >= TradingConfig.TP2_MULTIPLIER - 1
                and not (position.partial_sold & 2)
            ):
                logger.info(
                    f"🎯 TP2 triggered for {position.symbol} "
                    f"(+{profit_pct:.0%})"
                )
                self.trader._execute_partial_sell(
                    token_address, 0.5, price, reason="TP2 5x"
                )
                position.partial_sold |= 2
                self.storage.update_position(
                    token_address, partial_sold=position.partial_sold
                )

            # Trailing stop (active once profit >= activation threshold)
            elif profit_pct >= TradingConfig.TRAILING_STOP_ACTIVATION:
                trail_trigger = position.peak_price * (
                    1 - TradingConfig.TRAILING_STOP_DISTANCE
                )
                if price <= trail_trigger:
                    logger.info(
                        f"📉 Trailing stop for {position.symbol}: "
                        f"${price:.6f} <= trigger ${trail_trigger:.6f}"
                    )
                    self.trader._execute_sell(
                        token_address,
                        position.symbol,
                        price,
                        reason=f"Trailing stop (peak=${position.peak_price:.4f})",
                    )

            # Hard stop-loss
            elif self.trader.risk_manager.should_stop_loss(
                price, position.entry_price
            ):
                logger.info(
                    f"🛑 Stop-loss for {position.symbol}: "
                    f"-{(1-price/position.entry_price):.0%}"
                )
                self.trader._execute_sell(
                    token_address,
                    position.symbol,
                    price,
                    reason="Stop-loss 15%",
                )

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
        logger.info(f"Discovery complete: {len(all_discovered_tokens)} tokens in {discovery_time:.1f}s")
        
        # STEP 2: Apply comprehensive filtering
        start_time = time.time()
        filtered_tokens = filter_tokens_batch(
            tokens=all_discovered_tokens,
            max_tokens=200,  # Process top 200 tokens
            min_score=0.25   # Minimum quality score
        )
        filter_time = time.time() - start_time
        
        self.total_tokens_filtered += len(filtered_tokens)
        logger.info(f"Filtering complete: {len(filtered_tokens)} tokens passed in {filter_time:.1f}s")
        
        # STEP 3: Display filter statistics
        if filtered_tokens:
            stats = get_filter_stats(filtered_tokens)
            logger.info(f"Filter Stats:")
            logger.info(f"   Average Score: {stats['score_stats']['average']:.3f}")
            logger.info(f"   Average Age: {stats['age_stats']['average_hours']:.1f} hours")
            logger.info(f"   Total Volume: ${stats['volume_stats']['total_volume']:,.0f}")
            logger.info(f"   Sources: {stats['source_breakdown']}")

        # Store for dashboard
        self.latest_filtered_tokens = filtered_tokens

        return filtered_tokens
    
    def analyze_token_technicals(self, token_data: Dict[str, Any]) -> str:
        """Analyze token technicals and return rating"""
        try:
            # Use price history if available
            if 'price_history' in token_data and token_data['price_history']:
                prices = token_data['price_history']  # Already a list
                if len(prices) >= 14:  # Need enough data for RSI
                    rsi = self.technicals.compute_rsi(prices)
                    slope = self.technicals.compute_ema_slope(prices)
                    upper_band, lower_band = self.technicals.compute_volatility_band(prices)
                    rating = self.technicals.classify_trend(rsi, slope, prices, upper_band, lower_band)
                    return rating
            
            # Fallback to simple price change analysis
            price_change = float(token_data.get('price_change_24h', 0))
            volume = float(token_data.get('daily_volume_usd', 0))
            filter_score = float(token_data.get('filter_score', 0))
            
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
        logger.info(f"Processing {len(filtered_tokens)} filtered tokens...")
        
        processed_count = 0
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        
        for i, token_data in enumerate(filtered_tokens):
            try:
                token_address = token_data.get('address')
                symbol = token_data.get('symbol', 'Unknown')
                source = token_data.get('discovery_source', 'unknown')
                score = token_data.get('filter_score', 0)
                
                if not token_address:
                    continue
                
                logger.info(f"Token {i+1}/{len(filtered_tokens)}: {symbol}")
                logger.info(f"   Address: {token_address}")
                logger.info(f"   Source: {source}")
                logger.info(f"   Filter Score: {score:.3f}")
                
                # Save token data to database
                self.storage.save_token_data(
                    token_address, 
                    json.dumps(token_data), 
                    source
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
                volume = token_data.get('daily_volume_usd', 0)
                price_change = token_data.get('price_change_24h', 0)
                age_hours = token_data.get('age_hours', 'Unknown')
                
                logger.info(f"   Volume: ${volume:,.0f} | Change: {price_change:+.1f}% | Age: {age_hours}h")
                
                # Execute trading decision
                if rating in ["bullish", "bearish"]:
                    try:
                        # ✅ CRITICAL: Check if trade actually succeeded
                        trade_success = self.trader.execute_trade(
                            token_address,
                            rating,
                            token_info=token_data,
                            confidence_score=score
                        )

                        if trade_success:
                            self.total_trades_executed += 1

                            # Record trade for dashboard
                            trade_record = {
                                'timestamp': datetime.now(),
                                'action': rating,
                                'symbol': symbol,
                                'address': token_address,
                                'quantity': 1000,  # Placeholder
                                'price': token_data.get('price_usd', 0),
                                'confidence': score
                            }
                            self.trade_history.append(trade_record)

                            logger.info(f"   ✅ Trade SUCCESSFULLY executed: {rating}")
                        else:
                            logger.info(f"   ❌ Trade NOT executed (failed validation)")

                    except Exception as e:
                        logger.error(f"   ❌ Trade failed with exception: {str(e)}")
                else:
                    logger.debug(f"   No trade: neutral rating")
                
                processed_count += 1
                
                # Add small delay to avoid overwhelming APIs
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error processing token {token_data.get('symbol', 'unknown')}: {str(e)}")
        
                logger.info(f"Processing complete:")
        logger.info(f"   Processed: {processed_count} tokens")
        logger.info(f"   Bullish: {bullish_count} | Bearish: {bearish_count} | Neutral: {neutral_count}")
        logger.info(f"   Trades executed: {self.total_trades_executed}")
    
    def monitor_smart_money(self):
        """Monitor smart money activity using enhanced tracker"""
        try:
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
            filter_rate = (self.total_tokens_filtered / max(self.total_tokens_discovered, 1)) * 100
            
            logger.info(f"Average tokens per cycle: {avg_discovered:.0f} discovered, {avg_filtered:.0f} filtered")
            logger.info(f"Filter success rate: {filter_rate:.1f}%")
        
        logger.info("=" * 60)

    def get_dashboard_stats(self) -> Dict:
        """Get all stats for dashboard display"""
        return {
            'status': 'running',
            'cycle_count': self.cycle_count,
            'total_discovered': self.total_tokens_discovered,
            'total_filtered': self.total_tokens_filtered,
            'total_trades': self.total_trades_executed,
            'uptime': time.time() - self.start_time,
        }

    def get_latest_tokens(self, limit: int = 10) -> List[Dict]:
        """Get most recent filtered tokens for display"""
        return self.latest_filtered_tokens[:limit]

    def get_recent_trades(self, limit: int = 20) -> List[Dict]:
        """Get recent trade history"""
        return self.trade_history[-limit:]

    def run_single_cycle(self):
        """Run one complete discovery and trading cycle"""
        cycle_start = time.time()
        
        try:
            # 1. Discover and filter tokens
            filtered_tokens = self.discover_and_filter_tokens()
            
            if not filtered_tokens:
                logger.warning("No tokens passed filtering this cycle")
                return
            
            # 2. Process tokens for trading
            self.process_tokens(filtered_tokens)
            
            # 3. Monitor smart money
            self.monitor_smart_money()
            
            # 4. Cycle complete
            cycle_time = time.time() - cycle_start
            self.cycle_count += 1
            
            logger.info(f"Cycle {self.cycle_count} complete in {cycle_time:.1f}s")
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {str(e)}")
            raise
    
    def run(self):
        """Main bot loop with terminal UI"""
        logger.info("Starting Thor Memecoin Sniping Bot with Terminal UI")
        logger.info(f"   Fetch interval: {FETCH_INTERVAL} seconds")
        logger.info(f"   Database: {DB_PATH}")
        logger.info(f"   Mode: LIVE TRADING")

        # Create dashboard and keyboard handler
        dashboard = Dashboard(self)
        keyboard_handler = KeyboardHandler()

        # Setup logging to dashboard
        dashboard_log_handler = DashboardLogHandler(dashboard.log_buffer)
        dashboard_log_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(dashboard_log_handler)

        # Create layout
        layout = dashboard.create_layout()

        # Keyboard callback
        def on_key(key):
            return keyboard_handler.handle_key(key, self, dashboard)

        keyboard_handler.on_key_press = on_key
        keyboard_handler.start()

        try:
            with Live(layout, refresh_per_second=4, screen=True) as live:
                while dashboard.running:
                    if not keyboard_handler.paused:
                        # Run trading cycle
                        self.run_single_cycle()

                        # Update dashboard
                        dashboard.update_layout(layout)
                        live.update(layout)

                        # Sleep until next cycle
                        time.sleep(FETCH_INTERVAL)
                    else:
                        # Paused - just update display
                        dashboard.update_layout(layout)
                        live.update(layout)
                        time.sleep(0.5)

        except KeyboardInterrupt:
            logger.info("\n🛑 Bot stopped by user")
            self.print_session_stats()
        except Exception as e:
            logger.error(f"💥 Bot crashed: {str(e)}")
            self.print_session_stats()
            raise
        finally:
            self._running = False
            keyboard_handler.stop()

def main():
    """Entry point"""
    bot = TradingBot()
    bot.run()

if __name__ == "__main__":
    main()