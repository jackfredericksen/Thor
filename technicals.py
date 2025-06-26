# technicals.py

import pandas as pd


class Technicals:
    def compute_rsi(self, prices: pd.Series, period=14) -> float:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def compute_ema_slope(self, prices: pd.Series, period=14) -> float:
        ema = prices.ewm(span=period).mean()
        slope = (ema.iloc[-1] - ema.iloc[-2]) / ema.iloc[-2]
        return slope

    def compute_volatility_band(self, prices: pd.Series, period=20):
        sma = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        upper_band = sma + 2 * std
        lower_band = sma - 2 * std
        return upper_band.iloc[-1], lower_band.iloc[-1]

    def classify_trend(self, rsi, slope, prices, upper_band, lower_band):
        last_price = prices.iloc[-1]
        if rsi > 60 and slope > 0 and last_price > lower_band:
            return "bullish"
        elif rsi < 40 and slope < 0 and last_price < upper_band:
            return "bearish"
        return "neutral"
