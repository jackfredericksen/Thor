# trader.py
import time
from typing import Dict, Optional, List
import logging
from datetime import datetime
from risk_management import RiskManager

logger = logging.getLogger(__name__)

class Trader:
    """Simplified trader for getting the bot running"""
    
    def __init__(self, gmgn_client, storage):
        self.gmgn = gmgn_client
        self.storage = storage
        self.risk_manager = RiskManager(storage)
        self.paper_trading = True  # Always use paper trading for now
        self.open_orders: Dict[str, Dict] = {}
        
        # Trading statistics
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        
        logger.info(f"Trader initialized - Paper trading: {self.paper_trading}")
    
    def execute_trade(self, token_address: str, rating: str, token_info: Dict = None,
                     confidence_score: float = 1.0, max_slippage: float = 0.02) -> bool:
        """Execute trade with comprehensive validation and risk management"""
        try:
            symbol = token_info.get('symbol', token_address[:8]) if token_info else token_address[:8]
            current_price = token_info.get('price', 1.0) if token_info else 1.0
            
            if current_price <= 0:
                current_price = 1.0  # Default price for testing
            
            logger.info(f"Evaluating trade: {symbol} - {rating} (confidence: {confidence_score:.2f})")
            
            if rating == "bullish":
                return self._execute_buy(token_address, symbol, current_price, confidence_score, token_info or {})
            elif rating == "bearish":
                return self._execute_sell(token_address, symbol, current_price, "signal_based")
            else:  # neutral
                logger.info(f"Neutral rating for {symbol}, no action taken")
                return True
                
        except Exception as e:
            logger.error(f"Error executing trade for {token_address}: {str(e)}")
            self.failed_trades += 1
            return False
    
    def _execute_buy(self, token_address: str, symbol: str, price: float,
                    confidence_score: float, token_info: Dict) -> bool:
        """Execute buy order with risk management"""
        try:
            # Calculate position size
            quantity = self.risk_manager.calculate_position_size(
                token_address, price, confidence_score
            )
            
            if quantity <= 0:
                logger.info(f"Position size calculation returned 0 for {symbol}")
                return False
            
            # Validate trade with risk manager
            is_valid, reason = self.risk_manager.validate_trade(
                token_address, "buy", quantity, price
            )
            
            if not is_valid:
                logger.warning(f"Trade validation failed for {symbol}: {reason}")
                return False
            
            trade_value = quantity * price
            logger.info(f"Executing BUY: {quantity:.6f} {symbol} @ ${price:.6f} (${trade_value:.2f})")
            
            return self._paper_trade_buy(token_address, symbol, quantity, price, token_info)
                
        except Exception as e:
            logger.error(f"Error in buy execution for {symbol}: {str(e)}")
            return False
    
    def _execute_sell(self, token_address: str, symbol: str, price: float, reason: str = "signal_based") -> bool:
        """Execute sell order"""
        try:
            # Check if we have a position
            position = self.risk_manager.positions.get(token_address)
            if not position:
                logger.debug(f"No position to sell for {symbol}")
                return True  # Not an error
            
            quantity = position.quantity
            logger.info(f"Executing SELL: {quantity:.6f} {symbol} @ ${price:.6f} ({reason})")
            
            return self._paper_trade_sell(token_address, symbol, quantity, price, reason)
                
        except Exception as e:
            logger.error(f"Error in sell execution for {symbol}: {str(e)}")
            return False
    
    def _paper_trade_buy(self, token_address: str, symbol: str, quantity: float,
                        price: float, token_info: Dict) -> bool:
        """Execute paper trade buy"""
        try:
            # Simulate order execution
            order_id = f"paper_{int(time.time())}_{token_address[:8]}"
            
            # Add position to risk manager
            self.risk_manager.add_position(token_address, symbol, quantity, price)
            
            # Record in storage
            self.storage.save_order_status(order_id, "filled")
            
            self.successful_trades += 1
            self.total_trades += 1
            
            logger.info(f"Paper trade BUY completed: {quantity:.6f} {symbol} @ ${price:.6f}")
            return True
            
        except Exception as e:
            logger.error(f"Paper trade buy failed for {symbol}: {str(e)}")
            return False
    
    def _paper_trade_sell(self, token_address: str, symbol: str, quantity: float,
                         price: float, reason: str) -> bool:
        """Execute paper trade sell"""
        try:
            # Calculate realized PnL
            realized_pnl = self.risk_manager.reduce_position(token_address, quantity, price)
            
            order_id = f"paper_{int(time.time())}_{token_address[:8]}"
            
            # Record in storage
            self.storage.save_order_status(order_id, "filled")
            
            self.successful_trades += 1
            self.total_trades += 1
            
            logger.info(
                f"Paper trade SELL completed: {quantity:.6f} {symbol} @ ${price:.6f} "
                f"(PnL: ${realized_pnl:.2f}, {reason})"
            )
            return True
            
        except Exception as e:
            logger.error(f"Paper trade sell failed for {symbol}: {str(e)}")
            return False
    
    def monitor_order(self, order_id: str, symbol: str = "Unknown", timeout: int = 300) -> bool:
        """Monitor order execution (simplified for paper trading)"""
        # For paper trading, orders are always filled immediately
        return True
    
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
                'portfolio_value': risk_metrics.total_portfolio_value,
                'total_exposure': risk_metrics.total_exposure,
                'number_of_positions': risk_metrics.number_of_positions,
                'unrealized_pnl': risk_metrics.total_unrealized_pnl,
                'total_trades': self.total_trades,
                'successful_trades': self.successful_trades,
                'failed_trades': self.failed_trades,
                'success_rate': self.successful_trades / self.total_trades if self.total_trades > 0 else 0,
                'paper_trading': self.paper_trading
            }
            
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {str(e)}")
            return {}
    
    def emergency_stop(self) -> bool:
        """Emergency stop all trading and close positions"""
        try:
            logger.critical("EMERGENCY STOP INITIATED")
            # For paper trading, just clear positions
            self.risk_manager.positions.clear()
            logger.critical("EMERGENCY STOP COMPLETED")
            return True
            
        except Exception as e:
            logger.critical(f"EMERGENCY STOP FAILED: {str(e)}")
            return False
    
    def health_check(self) -> Dict:
        """Check trader health status"""
        return {
            'overall_healthy': True,
            'paper_trading': self.paper_trading,
            'total_trades': self.total_trades
        }