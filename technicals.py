# technicals.py - Technical analysis without pandas dependency


class Technicals:
    def compute_rsi(self, prices, period=14) -> float:
        """Compute RSI from list of prices"""
        if len(prices) < period + 1:
            return 50.0  # Neutral if not enough data

        # Calculate price changes
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        # Separate gains and losses
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        # Calculate average gain and loss
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def compute_ema_slope(self, prices, period=14) -> float:
        """Compute EMA slope from list of prices"""
        if len(prices) < period + 2:
            return 0.0

        # Simple EMA calculation
        multiplier = 2 / (period + 1)
        ema = prices[0]

        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        # Previous EMA
        prev_ema = prices[0]
        for price in prices[1:-1]:
            prev_ema = (price * multiplier) + (prev_ema * (1 - multiplier))

        slope = (ema - prev_ema) / prev_ema if prev_ema != 0 else 0
        return slope

    def compute_volatility_band(self, prices, period=20):
        """Compute Bollinger Bands from list of prices"""
        if len(prices) < period:
            return prices[-1] * 1.02, prices[-1] * 0.98  # Default 2% bands

        # Calculate SMA
        recent_prices = prices[-period:]
        sma = sum(recent_prices) / period

        # Calculate standard deviation
        variance = sum((p - sma) ** 2 for p in recent_prices) / period
        std = variance ** 0.5

        upper_band = sma + 2 * std
        lower_band = sma - 2 * std

        return upper_band, lower_band

    def classify_trend(self, rsi, slope, prices, upper_band, lower_band):
        """Classify trend based on technical indicators"""
        if not prices:
            return "neutral"

        last_price = prices[-1]

        if rsi > 60 and slope > 0 and last_price > lower_band:
            return "bullish"
        elif rsi < 40 and slope < 0 and last_price < upper_band:
            return "bearish"
        return "neutral"
