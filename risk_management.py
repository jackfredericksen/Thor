# risk_management.py - Fixed to work with new config structure

import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    current_price: float = 0.0

    @property
    def unrealized_pnl(self) -> float:
        if self.current_price and self.entry_price:
            return (self.current_price - self.entry_price) * self.quantity
        return 0.0

    @property
    def cost_basis(self) -> float:
        return self.entry_price * self.quantity


@dataclass
class RiskMetrics:
    total_portfolio_value: float = 0.0
    total_exposure: float = 0.0
    number_of_positions: int = 0
    total_unrealized_pnl: float = 0.0

class RiskManager:
    """Risk management system for trading operations"""
    
    def __init__(self, storage):
        self.storage = storage
        
        # Use safe config access with defaults
        try:
            from config import config
            self.max_position_size = config.TRADING.get("MAX_POSITION_SIZE_USD", 1000)
            self.default_position_size = config.TRADING.get("DEFAULT_POSITION_SIZE_USD", 100)
            self.min_position_size = config.TRADING.get("MIN_POSITION_SIZE_USD", 10)
            self.max_slippage = config.TRADING.get("MAX_SLIPPAGE", 0.05)
            self.default_slippage = config.TRADING.get("DEFAULT_SLIPPAGE", 0.02)
            self.stop_loss_percent = config.TRADING.get("STOP_LOSS_PERCENT", 0.15)
            self.take_profit_percent = config.TRADING.get("TAKE_PROFIT_PERCENT", 0.50)
            self.max_trades_per_cycle = config.TRADING.get("MAX_TRADES_PER_CYCLE", 20)
            self.max_daily_trades = config.TRADING.get("MAX_DAILY_TRADES", 200)
            self.max_concurrent_positions = config.TRADING.get("MAX_CONCURRENT_POSITIONS", 50)
        except (ImportError, AttributeError, KeyError) as e:
            logger.warning(f"Config access error, using defaults: {e}")
            # Fallback defaults if config is not available
            self.max_position_size = 1000
            self.default_position_size = 100
            self.min_position_size = 10
            self.max_slippage = 0.05
            self.default_slippage = 0.02
            self.stop_loss_percent = 0.15
            self.take_profit_percent = 0.50
            self.max_trades_per_cycle = 20
            self.max_daily_trades = 200
            self.max_concurrent_positions = 50
        
        # Initialize tracking dictionaries
        self.positions: Dict[str, Position] = {}  # Track open positions
        self.trade_history = []  # Track all trades
        self.daily_trades = {}  # Track daily trade counts
        
        logger.info(f"Risk manager initialized with max position size: ${self.max_position_size}")
    
    def calculate_position_size(self, token_address: str, rating: str,
                                token_data: Dict[str, Any] = None) -> float:
        """Calculate appropriate position size based on risk factors"""
        try:
            base_size = self.default_position_size
            
            # Ensure token_data is a dict
            if token_data is None:
                token_data = {}
            elif not isinstance(token_data, dict):
                # If it's a float or other type, create empty dict
                token_data = {}
            
            # Adjust based on rating confidence
            if rating == "bullish":
                multiplier = 1.0
            elif rating == "bearish":
                multiplier = 0.5  # Smaller positions for short trades
            else:  # neutral
                multiplier = 0.3  # Very small positions for neutral
            
            # Adjust based on token data if available
            if token_data:
                # Reduce size for very new tokens (higher risk)
                age_hours = float(token_data.get("age_hours", 0))
                if age_hours < 1:
                    multiplier *= 0.5  # 50% size for tokens < 1 hour old
                elif age_hours < 6:
                    multiplier *= 0.7  # 70% size for tokens < 6 hours old
                
                # Reduce size for low liquidity
                liquidity = float(token_data.get("liquidity_usd", 0))
                if liquidity > 0 and liquidity < 10000:  # Less than $10k liquidity
                    multiplier *= 0.5
                
                # Increase size for high-scoring tokens
                filter_score = float(token_data.get("filter_score", 0))
                if filter_score > 0.8:
                    multiplier *= 1.2  # 20% bonus for high-quality tokens
            
            # Calculate final position size
            position_size = base_size * multiplier
            
            # Apply limits
            position_size = max(self.min_position_size, position_size)
            position_size = min(self.max_position_size, position_size)
            
            logger.debug(f"Position size for {token_address}: ${position_size:.2f} (multiplier: {multiplier:.2f})")
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return self.min_position_size
    
    def validate_trade(self, token_address: str, rating: str, position_size: float) -> tuple[bool, str]:
        """Validate if trade should be executed"""
        try:
            # Check if we can place trade based on risk limits
            can_trade, reason = self.can_place_trade(token_address)
            if not can_trade:
                return False, reason
            
            # Check position size limits
            if position_size > self.max_position_size:
                return False, f"Position size ${position_size:.2f} exceeds limit ${self.max_position_size}"
            
            if position_size < self.min_position_size:
                return False, f"Position size ${position_size:.2f} below minimum ${self.min_position_size}"
            
            return True, "Trade validated"
            
        except Exception as e:
            logger.error(f"Error validating trade: {e}")
            return False, f"Validation error: {e}"
    
    def can_place_trade(self, token_address: str) -> tuple[bool, str]:
        """Check if we can place a trade based on risk limits"""
        try:
            today = datetime.now().date()

            # Check daily trade limit
            if self.daily_trades.get(today, 0) >= self.max_daily_trades:
                return False, f"Daily trade limit reached ({self.max_daily_trades})"

            # Check concurrent position limit
            if len(self.positions) >= self.max_concurrent_positions:
                return False, f"Max concurrent positions reached ({self.max_concurrent_positions})"

            # Prevent duplicate position in same token
            if token_address in self.positions:
                return False, f"Position already open for {token_address[:8]}"

            return True, "Trade allowed"

        except Exception as e:
            logger.error(f"Error checking trade eligibility: {e}")
            return False, f"Risk check failed: {e}"
    
    def get_recommended_slippage(self, token_data: Dict[str, Any] = None) -> float:
        """Get recommended slippage based on token characteristics"""
        try:
            slippage = self.default_slippage
            
            if token_data:
                # Increase slippage for low liquidity tokens
                liquidity = float(token_data.get("liquidity_usd", 0))
                if liquidity > 0:
                    if liquidity < 5000:
                        slippage = min(self.max_slippage, slippage * 2)  # Double slippage
                    elif liquidity < 20000:
                        slippage = min(self.max_slippage, slippage * 1.5)  # 50% more slippage
                
                # Increase slippage for highly volatile tokens
                price_change = abs(float(token_data.get("price_change_24h", 0)))
                if price_change > 100:  # Very volatile
                    slippage = min(self.max_slippage, slippage * 1.5)
            
            return slippage
            
        except Exception as e:
            logger.error(f"Error calculating slippage: {e}")
            return self.default_slippage
    
    def should_stop_loss(self, current_price: float, entry_price: float, 
                        position_type: str = "long") -> bool:
        """Check if position should be stopped out"""
        try:
            if position_type == "long":
                loss_percent = (entry_price - current_price) / entry_price
            else:  # short
                loss_percent = (current_price - entry_price) / entry_price
            
            return loss_percent >= self.stop_loss_percent
            
        except Exception as e:
            logger.error(f"Error checking stop loss: {e}")
            return False
    
    def should_take_profit(self, current_price: float, entry_price: float,
                          position_type: str = "long") -> bool:
        """Check if position should take profit"""
        try:
            if position_type == "long":
                profit_percent = (current_price - entry_price) / entry_price
            else:  # short
                profit_percent = (entry_price - current_price) / entry_price

            return profit_percent >= self.take_profit_percent

        except Exception as e:
            logger.error(f"Error checking take profit: {e}")
            return False

    def add_position(self, token_address: str, symbol: str, quantity: float, entry_price: float) -> None:
        """Record a new open position."""
        self.positions[token_address] = Position(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            current_price=entry_price,
        )
        today = datetime.now().date()
        self.daily_trades[today] = self.daily_trades.get(today, 0) + 1
        logger.info(f"Position added: {symbol} qty={quantity:.4f} @ ${entry_price:.6f}")

    def reduce_position(self, token_address: str, quantity: float, exit_price: float) -> float:
        """Remove (or reduce) a position and return realized P&L."""
        position = self.positions.pop(token_address, None)
        if position is None:
            return 0.0
        realized_pnl = (exit_price - position.entry_price) * quantity
        logger.info(
            f"Position closed: {position.symbol} P&L=${realized_pnl:.2f}"
        )
        return realized_pnl

    def update_prices(self, price_updates: Dict[str, float]) -> None:
        """Update current prices for all tracked positions."""
        for token_address, price in price_updates.items():
            if token_address in self.positions and price > 0:
                self.positions[token_address].current_price = price

    def get_risk_metrics(self) -> RiskMetrics:
        """Return a snapshot of current portfolio risk metrics."""
        total_exposure = sum(p.cost_basis for p in self.positions.values())
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        # Portfolio value = cost basis + unrealized gains
        total_portfolio_value = total_exposure + total_unrealized_pnl
        return RiskMetrics(
            total_portfolio_value=total_portfolio_value,
            total_exposure=total_exposure,
            number_of_positions=len(self.positions),
            total_unrealized_pnl=total_unrealized_pnl,
        )