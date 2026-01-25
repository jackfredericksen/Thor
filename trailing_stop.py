"""
Trailing Stop Loss System
Dynamic stop loss that follows price upward to lock in profits
"""

import logging
from typing import Dict, Optional
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TrailingStop:
    """Trailing stop configuration for a position"""
    token_address: str
    entry_price: float
    highest_price: float
    trailing_distance_pct: float  # How far below peak to set stop (e.g., 0.15 = 15%)
    minimum_profit_pct: float  # Don't activate until this profit reached
    activated: bool = False
    stop_price: float = 0.0


class TrailingStopManager:
    """Manage trailing stops for all positions"""

    def __init__(self, storage=None):
        self.storage = storage
        self.trailing_stops: Dict[str, TrailingStop] = {}

        # Default configuration
        self.default_trailing_distance = 0.15  # 15% below peak
        self.default_activation_profit = 0.25  # Activate after 25% profit

    def add_trailing_stop(
        self,
        token_address: str,
        entry_price: float,
        trailing_distance_pct: Optional[float] = None,
        activation_profit_pct: Optional[float] = None
    ):
        """
        Add trailing stop for a position

        Args:
            token_address: Token address
            entry_price: Entry price for position
            trailing_distance_pct: How far below peak to trail (default 15%)
            activation_profit_pct: Profit % needed to activate (default 25%)
        """
        trailing_stop = TrailingStop(
            token_address=token_address,
            entry_price=entry_price,
            highest_price=entry_price,
            trailing_distance_pct=trailing_distance_pct or self.default_trailing_distance,
            minimum_profit_pct=activation_profit_pct or self.default_activation_profit,
            activated=False
        )

        self.trailing_stops[token_address] = trailing_stop

        logger.info(
            f"Trailing stop added for {token_address[:8]}: "
            f"Trail {trailing_stop.trailing_distance_pct*100:.0f}% below peak, "
            f"activate at {trailing_stop.minimum_profit_pct*100:.0f}% profit"
        )

    def update_price(self, token_address: str, current_price: float) -> Optional[Dict]:
        """
        Update price and check if stop triggered

        Args:
            token_address: Token to update
            current_price: Current market price

        Returns:
            Dict with sell signal if stop triggered, None otherwise
        """
        if token_address not in self.trailing_stops:
            return None

        stop = self.trailing_stops[token_address]

        # Calculate current profit %
        current_profit_pct = (current_price - stop.entry_price) / stop.entry_price

        # Update highest price if new high
        if current_price > stop.highest_price:
            old_high = stop.highest_price
            stop.highest_price = current_price

            # Calculate new stop price
            stop.stop_price = current_price * (1 - stop.trailing_distance_pct)

            logger.info(
                f"New high for {token_address[:8]}: "
                f"${current_price:.6f} (was ${old_high:.6f}), "
                f"stop now at ${stop.stop_price:.6f}"
            )

        # Activate trailing stop if profit threshold reached
        if not stop.activated and current_profit_pct >= stop.minimum_profit_pct:
            stop.activated = True
            stop.stop_price = current_price * (1 - stop.trailing_distance_pct)

            logger.info(
                f"Trailing stop ACTIVATED for {token_address[:8]} at "
                f"{current_profit_pct*100:.1f}% profit. Stop: ${stop.stop_price:.6f}"
            )

        # Check if stop triggered
        if stop.activated and current_price <= stop.stop_price:
            profit_pct = (current_price - stop.entry_price) / stop.entry_price

            logger.warning(
                f"🔻 TRAILING STOP TRIGGERED for {token_address[:8]}: "
                f"Price ${current_price:.6f} <= Stop ${stop.stop_price:.6f}, "
                f"Profit: {profit_pct*100:.1f}%"
            )

            return {
                'signal': 'sell',
                'reason': 'trailing_stop',
                'entry_price': stop.entry_price,
                'exit_price': current_price,
                'highest_price': stop.highest_price,
                'profit_pct': profit_pct,
                'profit_from_peak_pct': (current_price - stop.highest_price) / stop.highest_price
            }

        return None

    def remove_trailing_stop(self, token_address: str):
        """Remove trailing stop for a position"""
        if token_address in self.trailing_stops:
            del self.trailing_stops[token_address]
            logger.info(f"Trailing stop removed for {token_address[:8]}")

    def get_stop_info(self, token_address: str) -> Optional[Dict]:
        """Get current trailing stop information"""
        if token_address not in self.trailing_stops:
            return None

        stop = self.trailing_stops[token_address]

        return {
            'token_address': token_address,
            'entry_price': stop.entry_price,
            'highest_price': stop.highest_price,
            'stop_price': stop.stop_price,
            'trailing_distance_pct': stop.trailing_distance_pct,
            'minimum_profit_pct': stop.minimum_profit_pct,
            'activated': stop.activated,
            'current_profit_from_entry': (stop.highest_price - stop.entry_price) / stop.entry_price,
            'distance_to_stop': (stop.highest_price - stop.stop_price) / stop.highest_price if stop.activated else None
        }

    def get_all_stops(self) -> Dict[str, Dict]:
        """Get info for all active trailing stops"""
        return {
            addr: self.get_stop_info(addr)
            for addr in self.trailing_stops
        }

    def adjust_trailing_distance(self, token_address: str, new_distance_pct: float):
        """
        Adjust trailing distance for active stop

        Args:
            token_address: Token to adjust
            new_distance_pct: New trailing distance (e.g., 0.10 = 10%)
        """
        if token_address in self.trailing_stops:
            stop = self.trailing_stops[token_address]
            old_distance = stop.trailing_distance_pct
            stop.trailing_distance_pct = new_distance_pct

            # Recalculate stop price if activated
            if stop.activated:
                stop.stop_price = stop.highest_price * (1 - new_distance_pct)

            logger.info(
                f"Trailing distance adjusted for {token_address[:8]}: "
                f"{old_distance*100:.0f}% -> {new_distance_pct*100:.0f}%, "
                f"new stop: ${stop.stop_price:.6f}"
            )


class AdaptiveTrailingStop(TrailingStopManager):
    """
    Advanced trailing stop that adjusts based on volatility

    - Tighter stops for low volatility
    - Wider stops for high volatility
    - Accelerated trailing in strong trends
    """

    def __init__(self, storage=None):
        super().__init__(storage)
        self.volatility_data: Dict[str, list] = {}  # Track price volatility

    def update_price(self, token_address: str, current_price: float) -> Optional[Dict]:
        """Update with volatility-adjusted trailing"""

        # Track price history for volatility calculation
        if token_address not in self.volatility_data:
            self.volatility_data[token_address] = []

        self.volatility_data[token_address].append(current_price)

        # Keep last 20 prices
        if len(self.volatility_data[token_address]) > 20:
            self.volatility_data[token_address].pop(0)

        # Calculate volatility
        if len(self.volatility_data[token_address]) >= 5:
            prices = self.volatility_data[token_address]
            volatility = self._calculate_volatility(prices)

            # Adjust trailing distance based on volatility
            if token_address in self.trailing_stops:
                stop = self.trailing_stops[token_address]

                # Higher volatility = wider stop
                # Lower volatility = tighter stop
                if volatility > 0.10:  # High volatility (>10% swings)
                    adjusted_distance = 0.20  # 20% trail
                elif volatility > 0.05:  # Medium volatility
                    adjusted_distance = 0.15  # 15% trail
                else:  # Low volatility
                    adjusted_distance = 0.10  # 10% trail

                # Apply adjustment if stop is activated
                if stop.activated and adjusted_distance != stop.trailing_distance_pct:
                    logger.info(
                        f"Volatility-adjusted trailing for {token_address[:8]}: "
                        f"{stop.trailing_distance_pct*100:.0f}% -> {adjusted_distance*100:.0f}% "
                        f"(volatility: {volatility*100:.1f}%)"
                    )
                    stop.trailing_distance_pct = adjusted_distance

        # Call parent update_price
        return super().update_price(token_address, current_price)

    def _calculate_volatility(self, prices: list) -> float:
        """Calculate price volatility (simplified standard deviation)"""
        if len(prices) < 2:
            return 0.0

        # Calculate average
        avg = sum(prices) / len(prices)

        # Calculate variance
        variance = sum((p - avg) ** 2 for p in prices) / len(prices)

        # Standard deviation as % of average price
        std_dev = variance ** 0.5
        volatility = std_dev / avg if avg > 0 else 0.0

        return volatility


class TieredTrailingStop(TrailingStopManager):
    """
    Multi-tier trailing stop system

    Example:
    - At 25% profit: Activate 20% trailing stop
    - At 50% profit: Tighten to 15% trailing
    - At 100% profit: Tighten to 10% trailing
    - At 200% profit: Tighten to 5% trailing

    Locks in more profit as position grows
    """

    def __init__(self, storage=None):
        super().__init__(storage)

        # Define profit tiers and corresponding trailing distances
        self.profit_tiers = [
            (2.0, 0.05),   # 200% profit -> 5% trail
            (1.0, 0.10),   # 100% profit -> 10% trail
            (0.50, 0.15),  # 50% profit -> 15% trail
            (0.25, 0.20),  # 25% profit -> 20% trail (activation)
        ]

    def update_price(self, token_address: str, current_price: float) -> Optional[Dict]:
        """Update with tiered trailing adjustment"""

        if token_address in self.trailing_stops:
            stop = self.trailing_stops[token_address]

            # Calculate current profit
            current_profit_pct = (current_price - stop.entry_price) / stop.entry_price

            # Find appropriate tier
            for profit_threshold, trail_distance in self.profit_tiers:
                if current_profit_pct >= profit_threshold:
                    # Apply tighter stop if we've reached this tier
                    if trail_distance < stop.trailing_distance_pct:
                        logger.info(
                            f"Tier upgrade for {token_address[:8]} at "
                            f"{current_profit_pct*100:.0f}% profit: "
                            f"Tightening trail from {stop.trailing_distance_pct*100:.0f}% "
                            f"to {trail_distance*100:.0f}%"
                        )
                        stop.trailing_distance_pct = trail_distance

                    break

        # Call parent update_price
        return super().update_price(token_address, current_price)
