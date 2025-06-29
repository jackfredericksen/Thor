# config.py

import os

# API Keys - Only for services that actually require them
API_KEYS = {
    "telegram_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),  # Optional for notifications
    "wallet_private_key": os.getenv("WALLET_PRIVATE_KEY", ""),  # For actual trading
    "wallet_address": os.getenv("WALLET_ADDRESS", ""),  # Your wallet address
}

# Open API URLs (No authentication required)
API_URLS = {
    # Dexscreener - Open API, no key needed
    "dexscreener_pairs": "https://api.dexscreener.com/latest/dex/pairs/solana",
    "dexscreener_search": "https://api.dexscreener.com/latest/dex/search",
    "dexscreener_token": "https://api.dexscreener.com/latest/dex/tokens",
    # GMGN.ai - Open endpoints (bypass Cloudflare with proper headers)
    "gmgn_trending": "https://gmgn.ai/defi/quotation/v1/tokens/top_gainers/sol",
    "gmgn_new_pairs": "https://gmgn.ai/defi/quotation/v1/tokens/new_pools/sol",
    "gmgn_smart_money": "https://gmgn.ai/defi/quotation/v1/smartmoney/sol/wallets",
    # Pump.fun - Public API
    "pumpfun_new": "https://frontend-api.pump.fun/coins",
    "pumpfun_trending": "https://frontend-api.pump.fun/coins/trending",
    # Jupiter - Token list and prices
    "jupiter_tokens": "https://token.jup.ag/strict",
    "jupiter_price": "https://price.jup.ag/v4/price",
    # Backup sources
    "coingecko_trending": "https://api.coingecko.com/api/v3/search/trending",
    "birdeye_tokens": "https://public-api.birdeye.so/public/tokenlist",
}

# Bot Configuration
DB_PATH = os.getenv("DB_PATH", "dex_bot.db")
FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL", "15"))  # seconds

# Rate Limiting Configuration (be respectful to free APIs)
RATE_LIMITS = {
    "requests_per_minute": 20,  # Conservative for free APIs
    "min_request_interval": 3,  # 3 seconds between requests
    "burst_limit": 3,
    "circuit_breaker_threshold": 5,
    "circuit_breaker_timeout": 300,  # 5 minutes
}

# Token Filtering Configuration
FILTER_CONFIG = {
    "max_volume_usd": 1_500_000,
    "max_age_hours": 72,
    "min_holders": 7_500,
    "min_liquidity_usd": 10_000,
    "blacklisted_symbols": ["SCAM", "TEST", "FAKE", "DEAD"],
    "min_market_cap": 50_000,  # $50k minimum
    "max_market_cap": 10_000_000,  # $10M maximum
}

# Trading Configuration
TRADING_CONFIG = {
    "max_slippage": 0.02,  # 2%
    "position_size_usd": 100,
    "max_positions": 10,
    "stop_loss_percent": 0.15,  # 15%
    "take_profit_percent": 0.50,  # 50%
    "min_trade_amount": 10,  # $10 minimum
}

# Smart Money Configuration
SMART_MONEY_CONFIG = {
    "min_trade_value_usd": 1000,
    "tracking_keywords": [
        "early investor",
        "insider",
        "whale",
        "vc",
        "founder",
        "team",
        "advisor",
        "angel",
    ],
    "min_wallet_success_rate": 0.6,  # 60% success rate
}

# Request Headers (Important for bypassing basic bot detection)
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

# Specific headers for GMGN (to bypass Cloudflare)
GMGN_HEADERS = {
    **DEFAULT_HEADERS,
    "Referer": "https://gmgn.ai/",
    "Origin": "https://gmgn.ai",
    "Sec-Fetch-Site": "same-origin",
}

# Error Handling Configuration
ERROR_CONFIG = {
    "max_retries": 3,
    "retry_delays": [1, 2, 4],  # seconds
    "timeout_seconds": 30,
    "log_level": os.getenv("LOG_LEVEL", "INFO"),
}

# Logging Configuration
LOGGING_CONFIG = {
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "bot.log",
    "max_size_mb": 10,
    "backup_count": 5,
}


def get_headers_for_url(url: str) -> dict:
    """
    Get appropriate headers for different URLs
    """
    if "gmgn.ai" in url:
        return GMGN_HEADERS
    else:
        return DEFAULT_HEADERS


def get_working_endpoints() -> dict:
    """
    Return endpoints that are known to work reliably
    """
    return {
        "dexscreener_pairs": API_URLS["dexscreener_pairs"],
        "jupiter_tokens": API_URLS["jupiter_tokens"],
        "pumpfun_new": API_URLS["pumpfun_new"],
        "coingecko_trending": API_URLS["coingecko_trending"],
    }


def get_priority_endpoints() -> list:
    """
    Return endpoints in order of reliability/preference
    """
    return [
        ("Dexscreener", API_URLS["dexscreener_pairs"]),
        ("Jupiter", API_URLS["jupiter_tokens"]),
        ("Pump.fun", API_URLS["pumpfun_new"]),
        ("GMGN New Pairs", API_URLS["gmgn_new_pairs"]),
        ("CoinGecko", API_URLS["coingecko_trending"]),
    ]


def validate_config() -> list:
    """
    Validate configuration and return warnings
    """
    warnings = []

    # Check database path
    db_dir = os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else "."
    if not os.path.exists(db_dir):
        warnings.append(f"Database directory does not exist: {db_dir}")

    # Check fetch interval
    if FETCH_INTERVAL < 5:
        warnings.append("Fetch interval very low - may cause rate limiting")

    # Check if wallet is configured for actual trading
    if not API_KEYS["wallet_address"]:
        warnings.append("Wallet address not configured - trading will be simulated")

    return warnings


# Network configuration for Solana
SOLANA_CONFIG = {
    "rpc_url": os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"),
    "ws_url": os.getenv("SOLANA_WS_URL", "wss://api.mainnet-beta.solana.com"),
    "commitment": "confirmed",
}

# Known token addresses for reference
KNOWN_TOKENS = {
    "SOL": "So11111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
    "SRM": "SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt",
}

if __name__ == "__main__":
    # Test configuration when run directly
    print("🔧 Configuration Test")
    print("=" * 40)

    warnings = validate_config()
    if warnings:
        print("⚠️ Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("✅ Configuration looks good!")

    print(f"\n📊 Settings:")
    print(f"  Database: {DB_PATH}")
    print(f"  Fetch Interval: {FETCH_INTERVAL}s")
    print(f"  Rate Limit: {RATE_LIMITS['requests_per_minute']} req/min")

    print(f"\n🔗 Available Endpoints:")
    for name, url in get_working_endpoints().items():
        print(f"  {name}: {url}")
