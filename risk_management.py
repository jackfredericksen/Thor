# risk_management.py - Fixed to work with new config structure

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

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
        self.positions = {}  # Track open positions
        self.trade_history = []  # Track all trades
        self.daily_trades = {}  # Track daily trade counts
        
        logger.info(f"Risk manager initialized with max position size: ${self.max_position_size}")
    
    def calculate_position_size(self, token_address: str, rating: str, 
                              token_data: Dict[str, Any] = None) -> float:
        """Calculate appropriate position size based on risk factors"""
        try:
            base_size = self.default_position_size
            
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
    
    def can_place_trade(self, token_address: str) -> tuple[bool, str]:
        """Check if we can place a trade based on risk limits"""
        try:
            # Check daily trade limit
            today = datetime.now().date()
            # This would need to be implemented with actual trade counting
            # For now, always allow trades
            
            # Check concurrent positions
            # This would need to be implemented with actual position tracking
            # For now, always allow trades
            
            # Check if we've traded this token recently (cooldown)
            # This would need to be implemented with trade history
            # For now, always allow trades
            
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