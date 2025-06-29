# config.py - Enhanced configuration for comprehensive memecoin discovery

import os
from typing import Any, Dict, List

# API Keys - Most sources are public APIs that don't need keys!
API_KEYS = {
    # Required for trading execution
    "telegram_token": os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN"),
    "wallet_address": os.getenv("WALLET_ADDRESS", "YOUR_WALLET_ADDRESS"),
    # Optional - for enhanced features (many have free tiers)
    "birdeye": os.getenv("BIRDEYE_API_KEY", ""),  # Optional, has free tier
    "coingecko": os.getenv("COINGECKO_API_KEY", ""),  # Optional, often free
    "rugcheck": os.getenv("RUGCHECK_API_KEY", ""),  # Optional
    "bubblemaps": os.getenv("BUBBLEMAPS_API_KEY", ""),  # Optional
    "moni": os.getenv("MONI_API_KEY", ""),  # Optional
    # Public APIs (no keys needed)
    "dexscreener": "",  # Public API
    "pumpfun": "",  # Public API
    "gmgn": "",  # Public API
    "jupiter": "",  # Public API
    "raydium": "",  # Public API
}

# API URLs - Updated with additional sources for comprehensive coverage
API_URLS = {
    # Primary token discovery sources
    "dexscreener": "https://api.dexscreener.com/latest/dex",
    "pumpfun": "https://frontend-api.pump.fun",
    "bubblemaps": "https://api.bubblemaps.io/wallets",
    "rugcheck": "https://api.rugcheck.xyz/v1/audit",
    "moni": "https://api.moni.score/v1/tokens",
    "gmgn": "https://api.gmgn.io/v1",
    # Additional comprehensive sources
    "birdeye": "https://public-api.birdeye.so",
    "jupiter": "https://price.jup.ag",
    "raydium": "https://api.raydium.io/v2",
    "coingecko": "https://api.coingecko.com/api/v3",
    "solscan": "https://public-api.solscan.io",
}

# Database and storage settings
DB_PATH = "dex_bot.db"
FETCH_INTERVAL = 15  # seconds between discovery cycles


# Enhanced filtering configuration for memecoins
class FilterConfig:
    """Memecoin-optimized filtering parameters"""

    # Age filters (in hours)
    MAX_AGE_HOURS = 720  # 30 days maximum age
    OPTIMAL_AGE_HOURS = 72  # 3 days is optimal for memecoins
    FRESH_AGE_HOURS = 6  # Very fresh tokens (highest priority)

    # Volume filters (USD)
    MIN_VOLUME_USD = 500  # Minimum daily volume
    GOOD_VOLUME_USD = 10_000  # Good volume threshold
    HIGH_VOLUME_USD = 100_000  # High volume threshold
    MAX_VOLUME_USD = 50_000_000  # Avoid overly hyped tokens

    # Market cap filters (USD)
    MIN_MARKET_CAP = 5_000  # Minimum viable market cap
    OPTIMAL_MIN_MARKET_CAP = 50_000  # Optimal minimum
    OPTIMAL_MAX_MARKET_CAP = 10_000_000  # Optimal maximum
    MAX_MARKET_CAP = 100_000_000  # Maximum before too mainstream

    # Liquidity filters (USD)
    MIN_LIQUIDITY_USD = 2_000  # Absolute minimum for trading
    GOOD_LIQUIDITY_USD = 20_000  # Good liquidity threshold
    EXCELLENT_LIQUIDITY_USD = 100_000  # Excellent liquidity

    # Activity filters
    MIN_PRICE_CHANGE = 5  # Minimum 24h price change %
    HIGH_PRICE_CHANGE = 50  # High activity threshold %
    EXTREME_PRICE_CHANGE = 200  # Extreme activity threshold %

    # Holder filters
    MIN_HOLDERS = 50  # Minimum holders (if data available)
    GOOD_HOLDERS = 1000  # Good holder count

    # Risk management
    MAX_VOLUME_MCAP_RATIO = 2.0  # Max daily volume / market cap ratio
    SUSPICIOUS_VOLUME_MCAP_RATIO = 1.0  # Flag suspicious ratios


# Trading configuration
class TradingConfig:
    """Trading execution parameters"""

    # Position sizing
    MAX_POSITION_SIZE_USD = 1000  # Maximum position size
    DEFAULT_POSITION_SIZE_USD = 100  # Default position size
    MIN_POSITION_SIZE_USD = 10  # Minimum position size

    # Risk management
    MAX_SLIPPAGE = 0.05  # 5% maximum slippage
    DEFAULT_SLIPPAGE = 0.02  # 2% default slippage
    STOP_LOSS_PERCENT = 0.15  # 15% stop loss
    TAKE_PROFIT_PERCENT = 0.50  # 50% take profit

    # Execution limits
    MAX_TRADES_PER_CYCLE = 20  # Maximum trades per discovery cycle
    MAX_DAILY_TRADES = 200  # Maximum trades per day
    COOLDOWN_BETWEEN_TRADES = 5  # Seconds between trades

    # Portfolio management
    MAX_CONCURRENT_POSITIONS = 50  # Maximum open positions
    PORTFOLIO_ALLOCATION_PERCENT = 0.02  # 2% of portfolio per trade


# Discovery configuration
class DiscoveryConfig:
    """Token discovery parameters"""

    # Source priorities (higher = more trusted)
    SOURCE_PRIORITIES = {
        "pumpfun_new": 10,  # Highest priority - new pump.fun tokens
        "pumpfun_trending": 9,  # High priority - trending pump.fun
        "dexscreener_new": 8,  # High priority - new on dexscreener
        "raydium_pools": 7,  # Good priority - new Raydium pools
        "birdeye_trending": 6,  # Medium priority - Birdeye trending
        "dexscreener_trending": 5,  # Medium priority - trending overall
        "jupiter_trending": 4,  # Lower priority - Jupiter data
        "coingecko_trending": 3,  # Lowest priority - usually too late
    }

    # Rate limiting (requests per second)
    RATE_LIMITS = {
        "dexscreener": 2,  # 2 requests per second
        "pumpfun": 1,  # 1 request per second
        "birdeye": 3,  # 3 requests per second
        "jupiter": 5,  # 5 requests per second
        "raydium": 2,  # 2 requests per second
        "coingecko": 1,  # 1 request per second (free tier)
    }

    # Token limits per source (to manage processing time)
    MAX_TOKENS_PER_SOURCE = {
        "pumpfun_new": 1000,  # Get lots of new tokens
        "pumpfun_trending": 500,
        "dexscreener_new": 200,
        "dexscreener_trending": 500,
        "birdeye_trending": 300,
        "raydium_pools": 300,
        "jupiter_trending": 200,
        "coingecko_trending": 50,
    }

    # Concurrent processing
    MAX_WORKERS = 6  # Concurrent API calls
    REQUEST_TIMEOUT = 10  # Seconds timeout per request
    RETRY_ATTEMPTS = 3  # Retry failed requests

    # Data freshness
    MAX_DATA_AGE_MINUTES = 30  # Ignore data older than 30 minutes


# Performance and monitoring
class MonitoringConfig:
    """Performance monitoring and logging"""

    # Logging levels
    LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
    LOG_TO_FILE = True
    LOG_FILE = "trading_bot.log"
    LOG_MAX_SIZE_MB = 50
    LOG_BACKUP_COUNT = 5

    # Performance tracking
    TRACK_PERFORMANCE = True
    PERFORMANCE_LOG_INTERVAL = 100  # Log stats every N cycles

    # Alerts and notifications
    ENABLE_ALERTS = True
    ALERT_HIGH_PROFIT_PERCENT = 0.50  # Alert on 50%+ profit
    ALERT_HIGH_LOSS_PERCENT = 0.20  # Alert on 20%+ loss
    ALERT_DISCOVERY_FAILURES = 5  # Alert after N consecutive failures

    # Statistics
    SAVE_STATS_INTERVAL = 50  # Save performance stats every N cycles


# Consolidated config object
class Config:
    """Main configuration class combining all settings"""

    def __init__(self):
        self.FILTERS = self._dict_from_class(FilterConfig)
        self.TRADING = self._dict_from_class(TradingConfig)
        self.DISCOVERY = self._dict_from_class(DiscoveryConfig)
        self.MONITORING = self._dict_from_class(MonitoringConfig)

        # Legacy compatibility
        self.API_KEYS = API_KEYS
        self.API_URLS = API_URLS
        self.DB_PATH = DB_PATH
        self.FETCH_INTERVAL = FETCH_INTERVAL

    def _dict_from_class(self, cls):
        """Convert class attributes to dictionary"""
        return {
            key: value
            for key, value in cls.__dict__.items()
            if not key.startswith("_") and not callable(value)
        }

    def get_source_priority(self, source_name: str) -> int:
        """Get priority for a discovery source"""
        return self.DISCOVERY["SOURCE_PRIORITIES"].get(source_name, 1)

    def get_rate_limit(self, source_name: str) -> float:
        """Get rate limit for a source (requests per second)"""
        base_name = source_name.split("_")[0]  # e.g., 'pumpfun_new' -> 'pumpfun'
        return 1.0 / self.DISCOVERY["RATE_LIMITS"].get(base_name, 1)

    def should_process_token(self, token_data: Dict[str, Any]) -> bool:
        """Quick check if token meets basic criteria"""
        try:
            # Basic viability checks
            volume = float(token_data.get("daily_volume_usd", 0))
            age_hours = float(token_data.get("age_hours", 9999))
            market_cap = float(token_data.get("market_cap", 0))

            # Must meet basic thresholds
            volume_ok = volume >= self.FILTERS["MIN_VOLUME_USD"]
            age_ok = age_hours <= self.FILTERS["MAX_AGE_HOURS"]

            # Market cap check (if available)
            mcap_ok = True
            if market_cap > 0:
                mcap_ok = (
                    self.FILTERS["MIN_MARKET_CAP"]
                    <= market_cap
                    <= self.FILTERS["MAX_MARKET_CAP"]
                )

            return volume_ok and age_ok and mcap_ok

        except (ValueError, TypeError, KeyError):
            return False

    def validate_config(self) -> List[str]:
        """Validate configuration and return any issues"""
        issues = []

        # Check required API keys - only telegram and wallet are actually required
        required_keys = ["telegram_token", "wallet_address"]
        for key in required_keys:
            if not self.API_KEYS.get(key) or "YOUR_" in str(self.API_KEYS[key]):
                issues.append(f"Missing or invalid required key: {key}")

        # Check database path is writable
        try:
            import os

            db_dir = os.path.dirname(self.DB_PATH) or "."
            if not os.access(db_dir, os.W_OK):
                issues.append(f"Database directory not writable: {db_dir}")
        except Exception as e:
            issues.append(f"Database path issue: {str(e)}")

        # Check reasonable values
        if self.FETCH_INTERVAL < 5:
            issues.append("FETCH_INTERVAL too low (minimum 5 seconds recommended)")

        if (
            self.TRADING["MAX_POSITION_SIZE_USD"]
            < self.TRADING["MIN_POSITION_SIZE_USD"]
        ):
            issues.append("MAX_POSITION_SIZE_USD must be >= MIN_POSITION_SIZE_USD")

        return issues


# Create global config instance
config = Config()

# Backwards compatibility exports
FILTERS = config.FILTERS
TRADING = config.TRADING
DISCOVERY = config.DISCOVERY
MONITORING = config.MONITORING


# Helper function for environment setup
def setup_environment():
    """Setup environment and validate configuration"""
    import logging
    import os

    # Setup logging
    if config.MONITORING["LOG_TO_FILE"]:
        logging.basicConfig(
            level=getattr(logging, config.MONITORING["LOG_LEVEL"]),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(config.MONITORING["LOG_FILE"]),
                logging.StreamHandler(),
            ],
        )

    # Validate configuration
    issues = config.validate_config()
    if issues:
        logger = logging.getLogger(__name__)
        logger.warning("Configuration issues found:")
        for issue in issues:
            logger.warning(f"  - {issue}")

        if any("Missing or invalid API key" in issue for issue in issues):
            logger.error("Critical API keys missing. Please update config.py")
            return False

    return True


# Example environment file content
ENV_FILE_TEMPLATE = """
# Copy this to .env file - Only these 2 are required!
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
WALLET_ADDRESS=your_solana_wallet_address_here

# Optional API keys for enhanced features (all have free tiers or are public):
BIRDEYE_API_KEY=your_birdeye_key_here
COINGECKO_API_KEY=your_coingecko_key_here
RUGCHECK_API_KEY=your_rugcheck_key_here
BUBBLEMAPS_API_KEY=your_bubblemaps_key_here
MONI_API_KEY=your_moni_key_here

# Note: Dexscreener, Pump.fun, GMGN.ai, Jupiter, and Raydium are all public APIs
"""

if __name__ == "__main__":
    # Configuration validation script
    print("Validating configuration...")
    issues = config.validate_config()

    if issues:
        print("❌ Configuration issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\n💡 Example .env file:")
        print(ENV_FILE_TEMPLATE)
    else:
        print("✅ Configuration looks good!")
        print(
            f"📊 Configured for {len(config.DISCOVERY['SOURCE_PRIORITIES'])} discovery sources"
        )
        print(f"💰 Max position size: ${config.TRADING['MAX_POSITION_SIZE_USD']}")
        print(f"⏱️  Fetch interval: {config.FETCH_INTERVAL} seconds")
