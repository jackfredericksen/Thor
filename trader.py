# trader.py - Live Trading with Solana
import logging
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from risk_management import RiskManager
from api_clients.solana_trader import SolanaTrader
from config import TradingConfig

logger = logging.getLogger(__name__)


class Trader:
    """Live trading executor using Solana blockchain"""

    def __init__(self, storage):
        self.storage = storage
        self.risk_manager = RiskManager(storage)

        # Initialize Solana client for LIVE TRADING
        if not TradingConfig.WALLET_PRIVATE_KEY or not TradingConfig.WALLET_ADDRESS:
            logger.error("CRITICAL: Wallet credentials not configured!")
            logger.error("Set THOR_WALLET_PRIVATE_KEY and THOR_WALLET_ADDRESS in .env")
            raise ValueError("Wallet credentials required for live trading")

        self.solana_client = SolanaTrader(
            private_key=TradingConfig.WALLET_PRIVATE_KEY,
            rpc_url=TradingConfig.RPC_ENDPOINT
        )

        # Trading statistics
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0

        logger.info("🔴 Trader initialized - LIVE TRADING ENABLED")
        logger.warning(f"Wallet: {TradingConfig.WALLET_ADDRESS}")

    def execute_trade(
        self,
        token_address: str,
        rating: str,
        token_info: Dict = None,
        confidence_score: float = 1.0,
        max_slippage: float = 0.02,
    ) -> bool:
        """Execute live trade with comprehensive validation and risk management"""
        try:
            symbol = (
                token_info.get("symbol", token_address[:8])
                if token_info
                else token_address[:8]
            )
            current_price = token_info.get("price", 1.0) if token_info else 1.0

            if current_price <= 0:
                logger.warning(f"Invalid price for {symbol}, skipping trade")
                return False

            logger.info(
                f"Evaluating trade: {symbol} - {rating} (confidence: {confidence_score:.2f})"
            )

            if rating == "bullish":
                return self._execute_buy(
                    token_address,
                    symbol,
                    current_price,
                    confidence_score,
                    token_info or {},
                )
            elif rating == "bearish":
                return self._execute_sell(
                    token_address, symbol, current_price, "signal_based"
                )
            else:  # neutral
                logger.info(f"Neutral rating for {symbol}, no action taken")
                return True

        except Exception as e:
            logger.error(f"Error executing trade for {token_address}: {str(e)}")
            self.failed_trades += 1
            return False

    def _execute_buy(
        self,
        token_address: str,
        symbol: str,
        price: float,
        confidence_score: float,
        token_info: Dict,
    ) -> bool:
        """Execute LIVE buy order via Solana"""
        try:
            # Calculate position size
            position_size_usd = self.risk_manager.calculate_position_size(
                token_address, price, confidence_score
            )

            if position_size_usd <= 0:
                logger.info(f"Position size calculation returned 0 for {symbol}")
                return False

            # Validate trade with risk manager
            is_valid, reason = self.risk_manager.validate_trade(
                token_address, "buy", position_size_usd, price
            )

            if not is_valid:
                logger.warning(f"Trade validation failed for {symbol}: {reason}")
                return False

            # Convert USD to SOL (simplified - should use real-time SOL price)
            # Assuming SOL = $100 for calculation
            sol_amount = position_size_usd / 100.0

            logger.info(
                f"🚀 Executing LIVE BUY: {symbol}"
            )
            logger.info(f"   Amount: {sol_amount:.4f} SOL (~${position_size_usd:.2f})")
            logger.info(f"   Token: {token_address}")
            logger.info(f"   Slippage: {TradingConfig.DEFAULT_SLIPPAGE * 100:.1f}%")

            # Execute swap on Solana using Jupiter
            tx_signature = asyncio.run(
                self.solana_client.swap_sol_for_token(
                    token_address=token_address,
                    amount_sol=sol_amount,
                    slippage=TradingConfig.DEFAULT_SLIPPAGE
                )
            )

            if tx_signature:
                logger.info(f"✅ BUY ORDER FILLED: {symbol}")
                logger.info(f"   Transaction: {tx_signature}")

                # Add position to risk manager
                # Note: We don't know exact quantity yet - need to query blockchain
                self.risk_manager.add_position(
                    token_address, symbol, position_size_usd / price, price
                )

                # Record in storage
                self.storage.save_order_status(tx_signature, "filled")

                self.successful_trades += 1
                self.total_trades += 1
                return True
            else:
                logger.error(f"❌ BUY ORDER FAILED: {symbol}")
                self.failed_trades += 1
                self.total_trades += 1
                return False

        except Exception as e:
            logger.error(f"Error in live buy execution for {symbol}: {str(e)}")
            self.failed_trades += 1
            return False

    def _execute_sell(
        self,
        token_address: str,
        symbol: str,
        price: float,
        reason: str = "signal_based",
    ) -> bool:
        """Execute LIVE sell order via Solana"""
        try:
            # Check if we have a position
            position = self.risk_manager.positions.get(token_address)
            if not position:
                logger.debug(f"No position to sell for {symbol}")
                return True  # Not an error

            quantity = position.quantity

            logger.info(f"🔻 Executing LIVE SELL: {symbol}")
            logger.info(f"   Quantity: {quantity:.4f} tokens")
            logger.info(f"   Reason: {reason}")
            logger.info(f"   Entry price: ${position.entry_price:.6f}")
            logger.info(f"   Current price: ${price:.6f}")

            # Execute swap on Solana using Jupiter
            tx_signature = asyncio.run(
                self.solana_client.swap_token_for_sol(
                    token_address=token_address,
                    amount_tokens=quantity,
                    slippage=TradingConfig.DEFAULT_SLIPPAGE
                )
            )

            if tx_signature:
                # Calculate realized P&L
                realized_pnl = self.risk_manager.reduce_position(
                    token_address, quantity, price
                )

                logger.info(f"✅ SELL ORDER FILLED: {symbol}")
                logger.info(f"   Transaction: {tx_signature}")
                logger.info(f"   P&L: ${realized_pnl:.2f} ({(realized_pnl / (quantity * position.entry_price) * 100):+.1f}%)")

                # Record in storage
                self.storage.save_order_status(tx_signature, "filled")

                self.successful_trades += 1
                self.total_trades += 1
                return True
            else:
                logger.error(f"❌ SELL ORDER FAILED: {symbol}")
                self.failed_trades += 1
                self.total_trades += 1
                return False

        except Exception as e:
            logger.error(f"Error in live sell execution for {symbol}: {str(e)}")
            self.failed_trades += 1
            return False

    def update_all_positions(self, price_updates: Dict[str, float]) -> None:
        """Update prices for all positions and check triggers"""
        try:
            self.risk_manager.update_prices(price_updates)
        except Exception as e:
            logger.error(f"Error updating positions: {str(e)}")

    def get_portfolio_summary(self) -> Dict:
        """Get comprehensive portfolio summary"""
        try:
            risk_metrics = self.risk_manager.get_risk_metrics()

            return {
                "portfolio_value": risk_metrics.total_portfolio_value,
                "total_exposure": risk_metrics.total_exposure,
                "number_of_positions": risk_metrics.number_of_positions,
                "unrealized_pnl": risk_metrics.total_unrealized_pnl,
                "total_trades": self.total_trades,
                "successful_trades": self.successful_trades,
                "failed_trades": self.failed_trades,
                "success_rate": self.successful_trades / self.total_trades
                if self.total_trades > 0
                else 0,
                "live_trading": True,
            }

        except Exception as e:
            logger.error(f"Error getting portfolio summary: {str(e)}")
            return {}

    def emergency_stop(self) -> bool:
        """Emergency stop - close all positions immediately"""
        try:
            logger.critical("🚨 EMERGENCY STOP INITIATED - CLOSING ALL POSITIONS")

            positions_to_close = list(self.risk_manager.positions.items())

            for token_address, position in positions_to_close:
                try:
                    logger.warning(f"Emergency closing position: {position.symbol}")

                    # Get current price (simplified - should fetch real price)
                    current_price = position.current_price

                    # Execute sell
                    self._execute_sell(
                        token_address,
                        position.symbol,
                        current_price,
                        "emergency_stop"
                    )

                except Exception as e:
                    logger.error(f"Failed to close position {position.symbol}: {e}")

            logger.critical("🚨 EMERGENCY STOP COMPLETED")
            return True

        except Exception as e:
            logger.critical(f"🚨 EMERGENCY STOP FAILED: {str(e)}")
            return False

    def health_check(self) -> Dict:
        """Check trader health status"""
        try:
            # Get SOL balance
            sol_balance = asyncio.run(self.solana_client.get_sol_balance())

            return {
                "overall_healthy": True,
                "live_trading": True,
                "wallet_address": TradingConfig.WALLET_ADDRESS,
                "sol_balance": sol_balance,
                "total_trades": self.total_trades,
                "success_rate": self.successful_trades / self.total_trades
                if self.total_trades > 0
                else 0,
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "overall_healthy": False,
                "live_trading": True,
                "error": str(e)
            }
