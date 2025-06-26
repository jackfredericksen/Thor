# config.py
import os
from typing import Dict, Any
import logging

class Config:
    """Centralized configuration management with validation"""
    
    def __init__(self):
        self.validate_config()
    
    # API Configuration - Updated based on actual requirements
    API_KEYS = {
        # FREE PUBLIC APIs - No keys required
        "dexscreener": "",  # DexScreener is completely free and public
        "gmgn": "",  # GMGN is free to use, no API key needed
        "pumpfun": "",  # Pump.fun data is accessible through public endpoints
        
        # APIs that REQUIRE keys/registration
        "rugcheck": os.getenv("RUGCHECK_API_KEY", ""),  # Requires API key from rugcheck.xyz
        "moni": os.getenv("MONI_API_KEY", ""),  # Requires paid subscription ($99+/month)
        "bubblemaps": os.getenv("BUBBLEMAPS_API_KEY", ""),  # May require API key for advanced features
        
        # Trading/Wallet Configuration (REQUIRED for live trading)
        "wallet_address": os.getenv("WALLET_ADDRESS", ""),
        "wallet_private_key": os.getenv("WALLET_PRIVATE_KEY", ""),
        "telegram_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),  # For GMGN integration
    }

    API_URLS = {
        # Free public APIs
        "dexscreener": "https://api.dexscreener.com/latest/dex",
        "gmgn": "https://gmgn.ai/defi/router/v1",  # Free trading API
        "pumpfun": "https://pumpportal.fun/api",  # Third-party free API
        
        # Paid/Key-required APIs
        "rugcheck": "https://api.rugcheck.xyz",
        "moni": "https://api-service.getmoni.io/v1",
        "bubblemaps": "https://api.bubblemaps.io/v1",
    }

    # API Status - Which APIs actually need keys
    API_REQUIREMENTS = {
        "dexscreener": {
            "requires_key": False,
            "cost": "Free",
            "rate_limit": "300 requests per minute (estimated)",
            "features": ["Token data", "Price history", "Trending tokens", "New pairs"]
        },
        "gmgn": {
            "requires_key": False,
            "cost": "Free",
            "rate_limit": "No official limit",
            "features": ["Trading", "Smart money tracking", "Token info", "Wallet analysis"]
        },
        "pumpfun": {
            "requires_key": False,  # Data API is free
            "cost": "Free for data, 0.5% fee for trading",
            "rate_limit": "No official limit for data",
            "features": ["Token data", "New tokens", "Trading (with fee)"]
        },
        "rugcheck": {
            "requires_key": True,
            "cost": "Paid API",
            "rate_limit": "Varies by plan",
            "features": ["Token security analysis", "Rug pull detection"]
        },
        "moni": {
            "requires_key": True,
            "cost": "$99+/month",
            "rate_limit": "Varies by plan", 
            "features": ["Social sentiment", "Twitter analysis", "Alpha discovery"]
        },
        "bubblemaps": {
            "requires_key": False,  # Basic features are free
            "cost": "Free basic, premium requires 250B MOONLIGHT tokens (~$1400)",
            "rate_limit": "Limited for free tier",
            "features": ["Wallet visualization", "Holder analysis", "Connection mapping"]
        }
    }

    # Trading Configuration
    TRADING = {
        "max_position_size_usd": float(os.getenv("MAX_POSITION_SIZE_USD", "1000")),
        "max_total_exposure_usd": float(os.getenv("MAX_TOTAL_EXPOSURE_USD", "10000")),
        "default_slippage": float(os.getenv("DEFAULT_SLIPPAGE", "0.02")),
        "stop_loss_pct": float(os.getenv("STOP_LOSS_PCT", "0.15")),
        "take_profit_pct": float(os.getenv("TAKE_PROFIT_PCT", "0.50")),
        "paper_trading": os.getenv("PAPER_TRADING", "true").lower() == "true",
        "min_liquidity_usd": float(os.getenv("MIN_LIQUIDITY_USD", "50000")),
    }

    # Filter Configuration
    FILTERS = {
        "max_volume_usd": float(os.getenv("MAX_VOLUME_USD", "1500000")),
        "max_age_hours": float(os.getenv("MAX_AGE_HOURS", "72")),
        "min_holders": int(os.getenv("MIN_HOLDERS", "7500")),
        "min_market_cap": float(os.getenv("MIN_MARKET_CAP", "100000")),
        "max_market_cap": float(os.getenv("MAX_MARKET_CAP", "10000000")),
    }

    # Rate Limiting (estimated based on public info)
    RATE_LIMITS = {
        "dexscreener": int(os.getenv("DEXSCREENER_RATE_LIMIT", "300")),  # Generous estimate
        "gmgn": int(os.getenv("GMGN_RATE_LIMIT", "120")),  # Conservative estimate
        "pumpfun": int(os.getenv("PUMPFUN_RATE_LIMIT", "60")),  # Conservative estimate
        "rugcheck": int(os.getenv("RUGCHECK_RATE_LIMIT", "10")),  # Very conservative for paid API
        "moni": int(os.getenv("MONI_RATE_LIMIT", "30")),  # Conservative for paid API
        "bubblemaps": int(os.getenv("BUBBLEMAPS_RATE_LIMIT", "20")),  # Conservative estimate
    }

    # System Configuration
    DB_PATH = os.getenv("DB_PATH", "dex_bot.db")
    FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL", "15"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "dex_bot.log")
    
    # Technical Analysis
    TECHNICAL = {
        "rsi_period": int(os.getenv("RSI_PERIOD", "14")),
        "ema_period": int(os.getenv("EMA_PERIOD", "14")),
        "bb_period": int(os.getenv("BB_PERIOD", "20")),
        "bb_std": float(os.getenv("BB_STD", "2.0")),
        "rsi_oversold": float(os.getenv("RSI_OVERSOLD", "30")),
        "rsi_overbought": float(os.getenv("RSI_OVERBOUGHT", "70")),
    }

    # Feature toggles based on available APIs
    FEATURES = {
        "enable_rugcheck": bool(API_KEYS["rugcheck"]),  # Only if API key provided
        "enable_moni_sentiment": bool(API_KEYS["moni"]),  # Only if API key provided
        "enable_bubblemaps": True,  # Always available (free tier)
        "enable_smart_money_tracking": True,  # GMGN is free
        "enable_pump_fun": True,  # Free data API
    }

    def validate_config(self):
        """Validate critical configuration parameters"""
        # Only require wallet address for live trading
        if not self.TRADING["paper_trading"]:
            if not self.API_KEYS.get("wallet_address"):
                raise ValueError("WALLET_ADDRESS required for live trading")
        
        if self.TRADING["max_position_size_usd"] <= 0:
            raise ValueError("MAX_POSITION_SIZE_USD must be positive")
        
        if self.TRADING["max_total_exposure_usd"] <= 0:
            raise ValueError("MAX_TOTAL_EXPOSURE_USD must be positive")

    def get_enabled_apis(self) -> Dict[str, Dict]:
        """Get list of enabled APIs with their status"""
        enabled_apis = {}
        
        for api_name, requirements in self.API_REQUIREMENTS.items():
            if requirements["requires_key"]:
                # Check if API key is provided
                api_key = self.API_KEYS.get(api_name)
                enabled = bool(api_key)
                status = "Enabled" if enabled else "Disabled (no API key)"
            else:
                # Free APIs are always enabled
                enabled = True
                status = "Enabled (free)"
            
            enabled_apis[api_name] = {
                "enabled": enabled,
                "status": status,
                "cost": requirements["cost"],
                "features": requirements["features"]
            }
        
        return enabled_apis

    def print_api_status(self):
        """Print status of all APIs"""
        print("\n" + "="*60)
        print("API CONFIGURATION STATUS")
        print("="*60)
        
        enabled_apis = self.get_enabled_apis()
        
        for api_name, info in enabled_apis.items():
            status_color = "✅" if info["enabled"] else "❌"
            print(f"{status_color} {api_name.upper()}")
            print(f"   Status: {info['status']}")
            print(f"   Cost: {info['cost']}")
            print(f"   Features: {', '.join(info['features'])}")
            print()
        
        print("SUMMARY:")
        enabled_count = sum(1 for api in enabled_apis.values() if api["enabled"])
        total_count = len(enabled_apis)
        print(f"Enabled APIs: {enabled_count}/{total_count}")
        
        if not enabled_apis["rugcheck"]["enabled"]:
            print("⚠️  Rugcheck disabled - token security analysis unavailable")
        if not enabled_apis["moni"]["enabled"]:
            print("⚠️  Moni disabled - social sentiment analysis unavailable")
        
        print("="*60)

# Global config instance
config = Config()

# Print API status when config is loaded
if __name__ == "__main__":
    config.print_api_status()