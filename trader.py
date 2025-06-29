# trader.py
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

from risk_management import RiskManager
from utils.error_handling import (APIException, InsufficientFundsException,
                                  InvalidTokenException, exponential_backoff)

# Import config properly - this is the fix!
try:
    # Import config properly - this is the fix!
try:
    from config import config
except ImportError:
    # Fallback config if import fails
    class FallbackConfig:
        API_URLS = {}
        API_KEYS = {}
        RATE_LIMITS = {}
        TRADING = {"paper_trading": True}
        FILTERS = {}
    config = FallbackConfig()
except ImportError:
    # Fallback config if import fails
    class FallbackConfig:
        TRADING = {
            "paper_trading": True,
            "default_slippage": 0.02,
        }
    config = FallbackConfig()

logger = logging.getLogger(__name__)
trading_logger = logging.getLogger('trading')

class Trader:
    """Enhanced trader with comprehensive risk management and error handling"""
    
    def __init__(self, gmgn_client, storage):
        self.gmgn = gmgn_client
        self.storage = storage
        self.risk_manager = RiskManager(storage)
        self.paper_trading = config.TRADING["paper_trading"]
        self.open_orders: Dict[str, Dict] = {}
        
        # Trading statistics
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        
        logger.info(f"Trader initialized - Paper trading: {self.paper_trading}")
    
    def execute_trade(self, token_address: str, rating: str, token_info: Dict,
                     confidence_score: float = 1.0, max_slippage: float = None) -> bool:
        """
        Execute trade with comprehensive validation and risk management
        
        Args:
            token_address: Token contract address
            rating: Trading signal (bullish/bearish/neutral)
            token_info: Token information dictionary
            confidence_score: Signal confidence (0.0 to 1.0)
            max_slippage: Maximum slippage tolerance
            
        Returns:
            True if trade executed successfully, False otherwise
        """
        if max_slippage is None:
            max_slippage = config.TRADING["default_slippage"]
        
        try:
            symbol = token_info.get('symbol', token_address[:8])
            current_price = token_info.get('price_usd', 0)
            
            if current_price <= 0:
                logger.warning(f"Invalid price for {symbol}: ${current_price}")
                return False
            
            logger.info(f"Evaluating trade: {symbol} - {rating} (confidence: {confidence_score:.2f})")
            
            if rating == "bullish":
                return self._execute_buy(token_address, symbol, current_price, 
                                       confidence_score, max_slippage, token_info)
            
            elif rating == "bearish":
                return self._execute_sell(token_address, symbol, current_price, 
                                        max_slippage, "signal_based")
            
            else:  # neutral
                logger.info(f"Neutral rating for {symbol}, checking stop losses")
                self._check_position_management(token_address, current_price)
                return True
                
        except Exception as e:
            logger.error(f"Error executing trade for {token_address}: {str(e)}")
            self.failed_trades += 1
            return False
    
    def _execute_buy(self, token_address: str, symbol: str, price: float,
                    confidence_score: float, max_slippage: float, 
                    token_info: Dict) -> bool:
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
            
            if self.paper_trading:
                return self._paper_trade_buy(token_address, symbol, quantity, price, token_info)
            else:
                return self._real_trade_buy(token_address, symbol, quantity, price, max_slippage)
                
        except Exception as e:
            logger.error(f"Error in buy execution for {symbol}: {str(e)}")
            return False
    
    def _execute_sell(self, token_address: str, symbol: str, price: float,
                     max_slippage: float, reason: str = "signal_based") -> bool:
        """Execute sell order"""
        try:
            # Check if we have a position
            position = self.risk_manager.positions.get(token_address)
            if not position:
                logger.debug(f"No position to sell for {symbol}")
                return True  # Not an error
            
            quantity = position.quantity
            logger.info(f"Executing SELL: {quantity:.6f} {symbol} @ ${price:.6f} ({reason})")
            
            if self.paper_trading:
                return self._paper_trade_sell(token_address, symbol, quantity, price, reason)
            else:
                return self._real_trade_sell(token_address, symbol, quantity, price, max_slippage)
                
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
            
            # Log trade
            trading_logger.info(
                f"PAPER_BUY,{order_id},{symbol},{token_address},{quantity},{price},"
                f"{quantity * price},{datetime.now().isoformat()}"
            )
            
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
            
            # Log trade
            trading_logger.info(
                f"PAPER_SELL,{order_id},{symbol},{token_address},{quantity},{price},"
                f"{quantity * price},{realized_pnl},{reason},{datetime.now().isoformat()}"
            )
            
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
    
    @exponential_backoff(max_retries=3)
    def _real_trade_buy(self, token_address: str, symbol: str, quantity: float,
                       price: float, max_slippage: float) -> bool:
        """Execute real buy order via GMGN"""
        try:
            order = self.gmgn.place_order(
                token_address=token_address,
                side="buy",
                quantity=quantity,
                order_type="market",
                slippage=max_slippage,
            )
            
            order_id = order.get("order_id")
            if not order_id:
                logger.error(f"No order ID received for {symbol} buy order")
                return False
            
            # Monitor order
            if self.monitor_order(order_id, symbol):
                # Add position to risk manager
                self.risk_manager.add_position(token_address, symbol, quantity, price)
                self.successful_trades += 1
                self.total_trades += 1
                return True
            else:
                self.failed_trades += 1
                self.total_trades += 1
                return False
                
        except InsufficientFundsException as e:
            logger.error(f"Insufficient funds for {symbol}: {str(e)}")
            return False
        except APIException as e:
            logger.error(f"API error for {symbol} buy: {str(e)}")
            raise  # Let retry mechanism handle this
        except Exception as e:
            logger.error(f"Unexpected error in real buy for {symbol}: {str(e)}")
            return False
    
    @exponential_backoff(max_retries=3)
    def _real_trade_sell(self, token_address: str, symbol: str, quantity: float,
                        price: float, max_slippage: float) -> bool:
        """Execute real sell order via GMGN"""
        try:
            order = self.gmgn.place_order(
                token_address=token_address,
                side="sell",
                quantity=quantity,
                order_type="market",
                slippage=max_slippage,
            )
            
            order_id = order.get("order_id")
            if not order_id:
                logger.error(f"No order ID received for {symbol} sell order")
                return False
            
            # Monitor order
            if self.monitor_order(order_id, symbol):
                # Update position in risk manager
                realized_pnl = self.risk_manager.reduce_position(token_address, quantity, price)
                self.successful_trades += 1
                self.total_trades += 1
                return True
            else:
                self.failed_trades += 1
                self.total_trades += 1
                return False
                
        except APIException as e:
            logger.error(f"API error for {symbol} sell: {str(e)}")
            raise  # Let retry mechanism handle this
        except Exception as e:
            logger.error(f"Unexpected error in real sell for {symbol}: {str(e)}")
            return False
    
    def monitor_order(self, order_id: str, symbol: str = "Unknown", 
                     timeout: int = 300) -> bool:
        """
        Monitor order execution with timeout
        
        Args:
            order_id: Order ID to monitor
            symbol: Token symbol for logging
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if order filled successfully, False otherwise
        """
        start_time = time.time()
        self.open_orders[order_id] = {'symbol': symbol, 'start_time': start_time}
        
        try:
            while time.time() - start_time < timeout:
                try:
                    status = self.gmgn.check_order_status(order_id)
                    current_status = status.get('status', 'unknown')
                    
                    logger.debug(f"Order {order_id} ({symbol}) status: {current_status}")
                    self.storage.save_order_status(order_id, current_status)
                    
                    if current_status == "filled":
                        logger.info(f"Order {order_id} ({symbol}) filled successfully")
                        self.open_orders.pop(order_id, None)
                        return True
                    
                    elif current_status in ["cancelled", "failed", "rejected"]:
                        logger.error(f"Order {order_id} ({symbol}) failed with status: {current_status}")
                        self.open_orders.pop(order_id, None)
                        return False
                    
                    elif current_status in ["pending", "partial"]:
                        # Continue monitoring
                        pass
                    
                    time.sleep(3)
                    
                except APIException as e:
                    logger.warning(f"Error checking order status for {order_id}: {str(e)}")
                    time.sleep(5)
                
            # Timeout reached
            logger.error(f"Order {order_id} ({symbol}) monitoring timeout after {timeout}s")
            self.open_orders.pop(order_id, None)
            
            # Try to cancel the order
            try:
                if not self.paper_trading:
                    self.gmgn.cancel_order(order_id)
                    logger.info(f"Cancelled timed-out order {order_id}")
            except Exception as e:
                logger.error(f"Failed to cancel order {order_id}: {str(e)}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error monitoring order {order_id}: {str(e)}")
            self.open_orders.pop(order_id, None)
            return False
    
    def _check_position_management(self, token_address: str, current_price: float) -> None:
        """Check for stop loss and take profit triggers"""
        try:
            # Update price in risk manager
            self.risk_manager.update_prices({token_address: current_price})
            
            # Check for triggers
            triggers = self.risk_manager.check_stop_losses()
            
            for trigger in triggers:
                if trigger['token_address'] == token_address:
                    symbol = trigger['symbol']
                    action = trigger['action']
                    quantity = trigger['quantity']
                    
                    logger.info(
                        f"{action.upper()} triggered for {symbol}: "
                        f"${current_price:.6f} vs ${trigger['trigger_price']:.6f} "
                        f"(PnL: {trigger['pnl_pct']:+.1f}%)"
                    )
                    
                    # Execute the trade
                    self._execute_sell(
                        token_address, symbol, current_price,
                        config.TRADING["default_slippage"], action
                    )
                    
        except Exception as e:
            logger.error(f"Error in position management for {token_address}: {str(e)}")
    
    def update_all_positions(self, price_updates: Dict[str, float]) -> None:
        """Update prices for all positions and check triggers"""
        try:
            self.risk_manager.update_prices(price_updates)
            
            # Check all positions for triggers
            triggers = self.risk_manager.check_stop_losses()
            
            for trigger in triggers:
                token_address = trigger['token_address']
                symbol = trigger['symbol']
                action = trigger['action']
                current_price = trigger['current_price']
                
                logger.info(f"Auto-trigger {action} for {symbol} at ${current_price:.6f}")
                
                self._execute_sell(
                    token_address, symbol, current_price,
                    config.TRADING["default_slippage"], f"auto_{action}"
                )
                
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
                'daily_pnl': risk_metrics.daily_pnl,
                'largest_position_pct': risk_metrics.largest_position_pct,
                'max_drawdown': risk_metrics.max_drawdown,
                'win_rate': risk_metrics.win_rate,
                'sharpe_ratio': risk_metrics.sharpe_ratio,
                'total_trades': self.total_trades,
                'successful_trades': self.successful_trades,
                'failed_trades': self.failed_trades,
                'success_rate': self.successful_trades / self.total_trades if self.total_trades > 0 else 0,
                'open_orders': len(self.open_orders),
                'paper_trading': self.paper_trading
            }
            
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {str(e)}")
            return {}
    
    def emergency_stop(self) -> bool:
        """Emergency stop all trading and close positions"""
        try:
            logger.critical("EMERGENCY STOP INITIATED")
            
            # Cancel all open orders
            for order_id in list(self.open_orders.keys()):
                try:
                    if not self.paper_trading:
                        self.gmgn.cancel_order(order_id)
                    self.open_orders.pop(order_id, None)
                    logger.info(f"Cancelled order {order_id}")
                except Exception as e:
                    logger.error(f"Failed to cancel order {order_id}: {str(e)}")
            
            # Close all positions
            positions_to_close = self.risk_manager.emergency_close_all()
            
            for position_info in positions_to_close:
                token_address = position_info['token_address']
                symbol = position_info['symbol']
                quantity = position_info['quantity']
                current_price = position_info['current_price']
                
                try:
                    self._execute_sell(
                        token_address, symbol, current_price,
                        config.TRADING["default_slippage"], "emergency_stop"
                    )
                except Exception as e:
                    logger.error(f"Failed to emergency close {symbol}: {str(e)}")
            
            logger.critical("EMERGENCY STOP COMPLETED")
            return True
            
        except Exception as e:
            logger.critical(f"EMERGENCY STOP FAILED: {str(e)}")
            return False
    
    def health_check(self) -> Dict:
        """Check trader health status"""
        try:
            # Check GMGN connection
            gmgn_healthy = self.gmgn.health_check() if not self.paper_trading else True
            
            # Check for stuck orders
            stuck_orders = []
            current_time = time.time()
            for order_id, order_info in self.open_orders.items():
                if current_time - order_info['start_time'] > 600:  # 10 minutes
                    stuck_orders.append(order_id)
            
            # Calculate success rates
            success_rate = self.successful_trades / self.total_trades if self.total_trades > 0 else 0
            
            health_status = {
                'gmgn_connection': gmgn_healthy,
                'open_orders_count': len(self.open_orders),
                'stuck_orders': stuck_orders,
                'total_trades': self.total_trades,
                'success_rate': success_rate,
                'paper_trading': self.paper_trading,
                'overall_healthy': gmgn_healthy and len(stuck_orders) == 0 and success_rate > 0.7
            }
            
            return health_status
            
        except Exception as e:
            logger.error(f"Error in trader health check: {str(e)}")
            return {'overall_healthy': False, 'error': str(e)}