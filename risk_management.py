# risk_management.py
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
from utils.error_handling import safe_float, InsufficientFundsException
from config import config

logger = logging.getLogger(__name__)

@dataclass
class Position:
    """Represents a trading position"""
    token_address: str
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float
    entry_time: datetime
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    
    @property
    def current_value(self) -> float:
        return self.quantity * self.current_price
    
    @property
    def entry_value(self) -> float:
        return self.quantity * self.avg_entry_price
    
    @property
    def pnl_percentage(self) -> float:
        if self.avg_entry_price == 0:
            return 0.0
        return ((self.current_price - self.avg_entry_price) / self.avg_entry_price) * 100

@dataclass
class RiskMetrics:
    """Portfolio risk metrics"""
    total_portfolio_value: float
    total_exposure: float
    largest_position_pct: float
    total_unrealized_pnl: float
    number_of_positions: int
    daily_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float

class RiskManager:
    """Comprehensive risk management system"""
    
    def __init__(self, storage):
        self.storage = storage
        self.positions: Dict[str, Position] = {}
        self.daily_pnl_history: List[Dict] = []
        self.trade_history: List[Dict] = []
        self.max_portfolio_value = 0.0
        self.lock = threading.Lock()
        
        # Risk limits from config
        self.max_position_size = config.TRADING["max_position_size_usd"]
        self.max_total_exposure = config.TRADING["max_total_exposure_usd"]
        self.stop_loss_pct = config.TRADING["stop_loss_pct"]
        self.take_profit_pct = config.TRADING["take_profit_pct"]
        
        # Load existing positions
        self._load_positions()
    
    def validate_trade(self, token_address: str, side: str, quantity: float, 
                      price: float) -> Tuple[bool, str]:
        """
        Validate if a trade is allowed based on risk management rules
        
        Returns:
            (is_valid, reason)
        """
        with self.lock:
            trade_value = quantity * price
            
            # Check position size limits
            if side == "buy":
                current_position = self.positions.get(token_address)
                new_position_value = trade_value
                
                if current_position:
                    new_position_value += current_position.current_value
                
                if new_position_value > self.max_position_size:
                    return False, f"Position size limit exceeded: ${new_position_value:,.0f} > ${self.max_position_size:,.0f}"
                
                # Check total exposure
                current_exposure = self.get_total_exposure()
                new_exposure = current_exposure + trade_value
                
                if new_exposure > self.max_total_exposure:
                    return False, f"Total exposure limit exceeded: ${new_exposure:,.0f} > ${self.max_total_exposure:,.0f}"
                
                # Check concentration risk
                portfolio_value = self.get_portfolio_value()
                if portfolio_value > 0:
                    new_position_pct = new_position_value / portfolio_value
                    if new_position_pct > 0.25:  # Max 25% in single position
                        return False, f"Concentration risk: {new_position_pct:.1%} > 25%"
            
            # Check if selling more than we have
            elif side == "sell":
                current_position = self.positions.get(token_address)
                if not current_position:
                    return False, "No position to sell"
                
                if quantity > current_position.quantity:
                    return False, f"Insufficient position: {current_position.quantity} < {quantity}"
            
            return True, "Trade validated"
    
    def calculate_position_size(self, token_address: str, price: float, 
                              confidence_score: float = 1.0) -> float:
        """
        Calculate optimal position size based on risk management
        
        Args:
            token_address: Token to trade
            price: Current price
            confidence_score: Trading signal confidence (0.0 to 1.0)
            
        Returns:
            Recommended position size in tokens
        """
        # Base position size (1% of portfolio or max position size, whichever is smaller)
        portfolio_value = self.get_portfolio_value()
        base_size_usd = min(
            portfolio_value * 0.01,
            self.max_position_size * 0.1  # Start with 10% of max
        )
        
        # Adjust for confidence
        adjusted_size_usd = base_size_usd * confidence_score
        
        # Ensure we don't exceed limits
        max_allowed_usd = min(
            self.max_position_size,
            self.max_total_exposure - self.get_total_exposure()
        )
        
        final_size_usd = min(adjusted_size_usd, max_allowed_usd)
        
        if final_size_usd <= 0:
            return 0.0
        
        return final_size_usd / price
    
    def add_position(self, token_address: str, symbol: str, quantity: float, 
                    price: float) -> None:
        """Add or update a position"""
        with self.lock:
            current_time = datetime.now()
            
            if token_address in self.positions:
                # Update existing position (average price)
                pos = self.positions[token_address]
                total_quantity = pos.quantity + quantity
                total_value = (pos.quantity * pos.avg_entry_price) + (quantity * price)
                new_avg_price = total_value / total_quantity
                
                pos.quantity = total_quantity
                pos.avg_entry_price = new_avg_price
                
                logger.info(f"Updated position {symbol}: {total_quantity} @ ${new_avg_price:.6f}")
            else:
                # Create new position
                stop_loss_price = price * (1 - self.stop_loss_pct)
                take_profit_price = price * (1 + self.take_profit_pct)
                
                position = Position(
                    token_address=token_address,
                    symbol=symbol,
                    quantity=quantity,
                    avg_entry_price=price,
                    current_price=price,
                    entry_time=current_time,
                    stop_loss_price=stop_loss_price,
                    take_profit_price=take_profit_price
                )
                
                self.positions[token_address] = position
                logger.info(f"New position {symbol}: {quantity} @ ${price:.6f}")
            
            # Save to storage
            self._save_position(token_address)
    
    def reduce_position(self, token_address: str, quantity: float, 
                       exit_price: float) -> Optional[float]:
        """
        Reduce or close a position
        
        Returns:
            Realized PnL from the trade
        """
        with self.lock:
            if token_address not in self.positions:
                logger.warning(f"Attempted to reduce non-existent position: {token_address}")
                return None
            
            position = self.positions[token_address]
            
            if quantity > position.quantity:
                logger.error(f"Cannot reduce position by {quantity}, only have {position.quantity}")
                return None
            
            # Calculate realized PnL
            realized_pnl = quantity * (exit_price - position.avg_entry_price)
            
            # Update position
            position.quantity -= quantity
            position.realized_pnl += realized_pnl
            
            # Remove position if fully closed
            if position.quantity <= 0:
                self.positions.pop(token_address)
                logger.info(f"Closed position {position.symbol} with PnL: ${realized_pnl:.2f}")
            else:
                logger.info(f"Reduced position {position.symbol} by {quantity}, PnL: ${realized_pnl:.2f}")
            
            # Record trade
            self._record_trade(token_address, "sell", quantity, exit_price, realized_pnl)
            
            # Save changes
            if token_address in self.positions:
                self._save_position(token_address)
            
            return realized_pnl
    
    def update_prices(self, price_updates: Dict[str, float]) -> None:
        """Update current prices for all positions"""
        with self.lock:
            for token_address, price in price_updates.items():
                if token_address in self.positions:
                    position = self.positions[token_address]
                    position.current_price = price
                    position.unrealized_pnl = position.quantity * (price - position.avg_entry_price)
    
    def check_stop_losses(self) -> List[Dict]:
        """
        Check for stop loss triggers
        
        Returns:
            List of positions that should be closed
        """
        triggers = []
        
        with self.lock:
            for token_address, position in self.positions.items():
                # Stop loss check
                if (position.stop_loss_price and 
                    position.current_price <= position.stop_loss_price):
                    triggers.append({
                        'token_address': token_address,
                        'symbol': position.symbol,
                        'action': 'stop_loss',
                        'current_price': position.current_price,
                        'trigger_price': position.stop_loss_price,
                        'quantity': position.quantity,
                        'pnl_pct': position.pnl_percentage
                    })
                
                # Take profit check
                elif (position.take_profit_price and 
                      position.current_price >= position.take_profit_price):
                    triggers.append({
                        'token_address': token_address,
                        'symbol': position.symbol,
                        'action': 'take_profit',
                        'current_price': position.current_price,
                        'trigger_price': position.take_profit_price,
                        'quantity': position.quantity,
                        'pnl_pct': position.pnl_percentage
                    })
        
        return triggers
    
    def get_portfolio_value(self) -> float:
        """Get total portfolio value"""
        with self.lock:
            total_value = 0.0
            for position in self.positions.values():
                total_value += position.current_value
            return total_value
    
    def get_total_exposure(self) -> float:
        """Get total exposure (sum of position values)"""
        return self.get_portfolio_value()
    
    def get_risk_metrics(self) -> RiskMetrics:
        """Calculate comprehensive risk metrics"""
        with self.lock:
            portfolio_value = self.get_portfolio_value()
            
            if not self.positions:
                return RiskMetrics(
                    total_portfolio_value=portfolio_value,
                    total_exposure=0.0,
                    largest_position_pct=0.0,
                    total_unrealized_pnl=0.0,
                    number_of_positions=0,
                    daily_pnl=0.0,
                    max_drawdown=0.0,
                    sharpe_ratio=0.0,
                    win_rate=0.0
                )
            
            # Calculate metrics
            total_unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
            largest_position_value = max(pos.current_value for pos in self.positions.values())
            largest_position_pct = largest_position_value / portfolio_value if portfolio_value > 0 else 0
            
            # Calculate daily PnL
            daily_pnl = self._calculate_daily_pnl()
            
            # Calculate max drawdown
            max_drawdown = self._calculate_max_drawdown()
            
            # Calculate win rate
            win_rate = self._calculate_win_rate()
            
            # Calculate Sharpe ratio (simplified)
            sharpe_ratio = self._calculate_sharpe_ratio()
            
            return RiskMetrics(
                total_portfolio_value=portfolio_value,
                total_exposure=portfolio_value,
                largest_position_pct=largest_position_pct,
                total_unrealized_pnl=total_unrealized_pnl,
                number_of_positions=len(self.positions),
                daily_pnl=daily_pnl,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                win_rate=win_rate
            )
    
    def _calculate_daily_pnl(self) -> float:
        """Calculate PnL for today"""
        today = datetime.now().date()
        daily_pnl = 0.0
        
        for trade in self.trade_history:
            if trade['date'].date() == today:
                daily_pnl += trade.get('realized_pnl', 0)
        
        return daily_pnl
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        if not self.daily_pnl_history:
            return 0.0
        
        peak = self.daily_pnl_history[0]['portfolio_value']
        max_drawdown = 0.0
        
        for record in self.daily_pnl_history:
            portfolio_value = record['portfolio_value']
            if portfolio_value > peak:
                peak = portfolio_value
            
            drawdown = (peak - portfolio_value) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)
        
        return max_drawdown
    
    def _calculate_win_rate(self) -> float:
        """Calculate win rate from trade history"""
        if not self.trade_history:
            return 0.0
        
        winning_trades = sum(1 for trade in self.trade_history if trade.get('realized_pnl', 0) > 0)
        return winning_trades / len(self.trade_history)
    
    def _calculate_sharpe_ratio(self) -> float:
        """Calculate simplified Sharpe ratio"""
        if len(self.daily_pnl_history) < 2:
            return 0.0
        
        daily_returns = [record['daily_return'] for record in self.daily_pnl_history]
        
        if not daily_returns:
            return 0.0
        
        avg_return = sum(daily_returns) / len(daily_returns)
        
        # Calculate standard deviation
        variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return 0.0
        
        # Annualized Sharpe ratio (assuming 252 trading days)
        return (avg_return / std_dev) * (252 ** 0.5)
    
    def _record_trade(self, token_address: str, side: str, quantity: float, 
                     price: float, realized_pnl: float = None) -> None:
        """Record trade in history"""
        trade_record = {
            'date': datetime.now(),
            'token_address': token_address,
            'side': side,
            'quantity': quantity,
            'price': price,
            'realized_pnl': realized_pnl
        }
        
        self.trade_history.append(trade_record)
        
        # Keep only last 1000 trades
        if len(self.trade_history) > 1000:
            self.trade_history = self.trade_history[-1000:]
    
    def _load_positions(self) -> None:
        """Load positions from storage"""
        try:
            # Implementation depends on your storage system
            # This is a placeholder
            pass
        except Exception as e:
            logger.error(f"Failed to load positions: {str(e)}")
    
    def _save_position(self, token_address: str) -> None:
        """Save position to storage"""
        try:
            # Implementation depends on your storage system
            # This is a placeholder
            pass
        except Exception as e:
            logger.error(f"Failed to save position {token_address}: {str(e)}")
    
    def emergency_close_all(self) -> List[Dict]:
        """
        Emergency function to close all positions
        Returns list of positions that need to be closed
        """
        logger.critical("EMERGENCY CLOSE ALL POSITIONS TRIGGERED")
        
        positions_to_close = []
        with self.lock:
            for token_address, position in self.positions.items():
                positions_to_close.append({
                    'token_address': token_address,
                    'symbol': position.symbol,
                    'quantity': position.quantity,
                    'current_price': position.current_price,
                    'reason': 'emergency_close'
                })
        
        return positions_to_close