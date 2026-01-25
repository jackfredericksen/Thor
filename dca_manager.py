"""
DCA (Dollar-Cost Averaging) Manager
Splits large orders into multiple smaller trades to reduce slippage and improve average entry
"""

import logging
import asyncio
from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DCAOrder:
    """DCA order configuration"""
    token_address: str
    total_amount_sol: float
    num_orders: int
    interval_seconds: int
    current_order: int = 0
    amount_per_order: float = 0.0
    completed_orders: List[Dict] = None
    total_spent: float = 0.0
    total_tokens_received: float = 0.0
    average_price: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = 'pending'  # pending, active, completed, cancelled

    def __post_init__(self):
        if self.completed_orders is None:
            self.completed_orders = []
        self.amount_per_order = self.total_amount_sol / self.num_orders


class DCAManager:
    """Manage DCA orders for better entry/exit prices"""

    def __init__(self, trader=None):
        """
        Args:
            trader: Trading client to execute orders
        """
        self.trader = trader
        self.active_orders: Dict[str, DCAOrder] = {}
        self.completed_orders: List[DCAOrder] = []

    def create_dca_buy(
        self,
        token_address: str,
        total_amount_sol: float,
        num_orders: int = 5,
        interval_seconds: int = 30,
        order_id: Optional[str] = None
    ) -> str:
        """
        Create DCA buy order

        Args:
            token_address: Token to buy
            total_amount_sol: Total SOL to spend
            num_orders: Split into this many orders
            interval_seconds: Seconds between each order
            order_id: Optional custom order ID

        Returns:
            Order ID
        """
        if order_id is None:
            order_id = f"dca_{token_address[:8]}_{int(datetime.now().timestamp())}"

        dca_order = DCAOrder(
            token_address=token_address,
            total_amount_sol=total_amount_sol,
            num_orders=num_orders,
            interval_seconds=interval_seconds
        )

        self.active_orders[order_id] = dca_order

        logger.info(
            f"DCA BUY created: {order_id[:20]} - "
            f"{num_orders}x {dca_order.amount_per_order:.4f} SOL "
            f"every {interval_seconds}s for {token_address[:8]}"
        )

        return order_id

    def create_dca_sell(
        self,
        token_address: str,
        total_token_amount: float,
        num_orders: int = 5,
        interval_seconds: int = 30,
        order_id: Optional[str] = None
    ) -> str:
        """
        Create DCA sell order

        Args:
            token_address: Token to sell
            total_token_amount: Total tokens to sell
            num_orders: Split into this many orders
            interval_seconds: Seconds between each order

        Returns:
            Order ID
        """
        if order_id is None:
            order_id = f"dca_sell_{token_address[:8]}_{int(datetime.now().timestamp())}"

        # Store as negative to indicate sell
        dca_order = DCAOrder(
            token_address=token_address,
            total_amount_sol=-total_token_amount,  # Negative for sell
            num_orders=num_orders,
            interval_seconds=interval_seconds
        )

        self.active_orders[order_id] = dca_order

        logger.info(
            f"DCA SELL created: {order_id[:20]} - "
            f"{num_orders}x {dca_order.amount_per_order:.4f} tokens "
            f"every {interval_seconds}s for {token_address[:8]}"
        )

        return order_id

    async def execute_dca_order(
        self,
        order_id: str,
        execute_callback: Optional[Callable] = None
    ) -> bool:
        """
        Execute DCA order

        Args:
            order_id: Order to execute
            execute_callback: Optional callback(token_address, amount_sol, action) -> result

        Returns:
            True if completed successfully
        """
        if order_id not in self.active_orders:
            logger.error(f"DCA order not found: {order_id}")
            return False

        order = self.active_orders[order_id]
        order.status = 'active'
        order.started_at = datetime.now()

        is_sell = order.total_amount_sol < 0
        action = 'SELL' if is_sell else 'BUY'

        logger.info(f"Starting DCA {action}: {order_id[:20]}")

        try:
            for i in range(order.num_orders):
                order.current_order = i + 1

                logger.info(
                    f"DCA {action} {i+1}/{order.num_orders}: "
                    f"{abs(order.amount_per_order):.4f} of {order.token_address[:8]}"
                )

                # Execute order
                if execute_callback:
                    result = await execute_callback(
                        order.token_address,
                        abs(order.amount_per_order),
                        'sell' if is_sell else 'buy'
                    )

                    if result:
                        # Record successful order
                        order_result = {
                            'order_num': i + 1,
                            'timestamp': datetime.now(),
                            'amount': abs(order.amount_per_order),
                            'price': result.get('price', 0.0),
                            'tokens_received': result.get('tokens_received', 0.0),
                            'transaction_signature': result.get('signature')
                        }

                        order.completed_orders.append(order_result)
                        order.total_spent += abs(order.amount_per_order)
                        order.total_tokens_received += result.get('tokens_received', 0.0)

                        logger.info(
                            f"DCA {action} {i+1}/{order.num_orders} completed - "
                            f"Price: ${result.get('price', 0):.6f}"
                        )
                    else:
                        logger.error(f"DCA {action} {i+1}/{order.num_orders} failed")
                else:
                    logger.warning("No execute callback - DCA order simulation only")

                # Wait before next order (unless it's the last one)
                if i < order.num_orders - 1:
                    await asyncio.sleep(order.interval_seconds)

            # Calculate average price
            if order.total_tokens_received > 0:
                order.average_price = order.total_spent / order.total_tokens_received
            else:
                order.average_price = 0.0

            # Mark as completed
            order.status = 'completed'
            order.completed_at = datetime.now()

            logger.info(
                f"DCA {action} COMPLETED: {order_id[:20]} - "
                f"Avg price: ${order.average_price:.6f}, "
                f"Total: {order.total_tokens_received:.2f} tokens"
            )

            # Move to completed
            self.completed_orders.append(order)
            del self.active_orders[order_id]

            return True

        except Exception as e:
            logger.error(f"Error executing DCA order {order_id}: {e}")
            order.status = 'failed'
            return False

    def cancel_dca_order(self, order_id: str) -> bool:
        """Cancel active DCA order"""
        if order_id not in self.active_orders:
            return False

        order = self.active_orders[order_id]
        order.status = 'cancelled'
        order.completed_at = datetime.now()

        logger.warning(f"DCA order cancelled: {order_id[:20]}")

        # Move to completed
        self.completed_orders.append(order)
        del self.active_orders[order_id]

        return True

    def get_dca_status(self, order_id: str) -> Optional[Dict]:
        """Get status of DCA order"""
        # Check active orders
        if order_id in self.active_orders:
            order = self.active_orders[order_id]
            return self._order_to_dict(order)

        # Check completed orders
        for order in self.completed_orders:
            if order_id in str(order):  # Simplified check
                return self._order_to_dict(order)

        return None

    def _order_to_dict(self, order: DCAOrder) -> Dict:
        """Convert DCA order to dictionary"""
        return {
            'token_address': order.token_address,
            'total_amount': order.total_amount_sol,
            'num_orders': order.num_orders,
            'current_order': order.current_order,
            'completed_orders': len(order.completed_orders),
            'progress_pct': (len(order.completed_orders) / order.num_orders) * 100,
            'total_spent': order.total_spent,
            'total_tokens_received': order.total_tokens_received,
            'average_price': order.average_price,
            'status': order.status,
            'started_at': order.started_at.isoformat() if order.started_at else None,
            'completed_at': order.completed_at.isoformat() if order.completed_at else None,
        }

    def get_all_active_orders(self) -> List[Dict]:
        """Get all active DCA orders"""
        return [
            self._order_to_dict(order)
            for order in self.active_orders.values()
        ]

    async def auto_dca_mode(
        self,
        token_address: str,
        target_position_sol: float,
        market_conditions: str = 'normal',
        execute_callback: Optional[Callable] = None
    ) -> str:
        """
        Automatically configure and execute DCA based on market conditions

        Args:
            token_address: Token to buy
            target_position_sol: Target position size in SOL
            market_conditions: 'calm', 'normal', 'volatile', 'extreme'
            execute_callback: Callback to execute trades

        Returns:
            DCA order ID
        """
        # Configure based on market conditions
        if market_conditions == 'calm':
            num_orders = 3
            interval_seconds = 60  # 1 minute between orders
        elif market_conditions == 'normal':
            num_orders = 5
            interval_seconds = 30  # 30 seconds between orders
        elif market_conditions == 'volatile':
            num_orders = 10
            interval_seconds = 15  # 15 seconds between orders
        else:  # extreme
            num_orders = 20
            interval_seconds = 5   # 5 seconds between orders

        logger.info(
            f"Auto DCA configured for {market_conditions} market: "
            f"{num_orders} orders @ {interval_seconds}s intervals"
        )

        # Create DCA order
        order_id = self.create_dca_buy(
            token_address,
            target_position_sol,
            num_orders,
            interval_seconds
        )

        # Execute in background if callback provided
        if execute_callback:
            asyncio.create_task(self.execute_dca_order(order_id, execute_callback))

        return order_id


class SmartDCAManager(DCAManager):
    """
    Advanced DCA with dynamic adjustment based on price action

    - Accelerates buying if price is dropping (buying the dip)
    - Slows down if price is rising (waiting for better entry)
    - Adjusts order size based on volatility
    """

    def __init__(self, trader=None):
        super().__init__(trader)
        self.price_history: Dict[str, List[float]] = {}

    async def execute_smart_dca(
        self,
        order_id: str,
        execute_callback: Optional[Callable] = None,
        get_price_callback: Optional[Callable] = None
    ) -> bool:
        """
        Execute DCA with dynamic adjustment

        Args:
            order_id: Order to execute
            execute_callback: Function to execute trades
            get_price_callback: Function to get current price

        Returns:
            True if completed successfully
        """
        if order_id not in self.active_orders:
            return False

        order = self.active_orders[order_id]
        order.status = 'active'
        order.started_at = datetime.now()

        # Initialize price history
        if order.token_address not in self.price_history:
            self.price_history[order.token_address] = []

        try:
            for i in range(order.num_orders):
                order.current_order = i + 1

                # Get current price
                current_price = None
                if get_price_callback:
                    current_price = await get_price_callback(order.token_address)
                    if current_price:
                        self.price_history[order.token_address].append(current_price)

                # Determine order size based on price action
                order_size = order.amount_per_order

                if len(self.price_history[order.token_address]) >= 2:
                    prices = self.price_history[order.token_address]

                    # Check if price is dropping
                    if prices[-1] < prices[-2]:
                        # Price dropping - increase this order size
                        order_size *= 1.2  # 20% larger
                        logger.info(f"Price dropping - increasing order size to {order_size:.4f}")

                    # Check if price is rising fast
                    elif len(prices) >= 3 and prices[-1] > prices[-3] * 1.05:
                        # Price up >5% - reduce order size
                        order_size *= 0.8  # 20% smaller
                        logger.info(f"Price rising - reducing order size to {order_size:.4f}")

                # Execute order with adjusted size
                if execute_callback:
                    result = await execute_callback(
                        order.token_address,
                        order_size,
                        'buy'
                    )

                    if result:
                        order.completed_orders.append({
                            'order_num': i + 1,
                            'timestamp': datetime.now(),
                            'amount': order_size,
                            'price': result.get('price', 0.0),
                            'tokens_received': result.get('tokens_received', 0.0)
                        })

                        order.total_spent += order_size
                        order.total_tokens_received += result.get('tokens_received', 0.0)

                # Dynamic wait time based on volatility
                if i < order.num_orders - 1:
                    wait_time = self._calculate_dynamic_wait(order.token_address)
                    await asyncio.sleep(wait_time)

            # Finalize order
            if order.total_tokens_received > 0:
                order.average_price = order.total_spent / order.total_tokens_received

            order.status = 'completed'
            order.completed_at = datetime.now()

            self.completed_orders.append(order)
            del self.active_orders[order_id]

            return True

        except Exception as e:
            logger.error(f"Error in smart DCA: {e}")
            order.status = 'failed'
            return False

    def _calculate_dynamic_wait(self, token_address: str) -> int:
        """Calculate wait time based on recent price volatility"""
        if token_address not in self.price_history:
            return 30  # Default

        prices = self.price_history[token_address]

        if len(prices) < 3:
            return 30

        # Calculate price volatility
        recent_prices = prices[-5:]
        avg_price = sum(recent_prices) / len(recent_prices)
        volatility = max(recent_prices) - min(recent_prices)
        volatility_pct = volatility / avg_price if avg_price > 0 else 0

        # Higher volatility = wait longer
        if volatility_pct > 0.10:  # >10% swing
            return 60  # Wait 1 minute
        elif volatility_pct > 0.05:  # >5% swing
            return 45  # Wait 45 seconds
        else:
            return 30  # Default 30 seconds
