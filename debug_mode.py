#!/usr/bin/env python3
"""
Thor Debug Mode - Deep debugging for troubleshooting
"""

import logging
import time
import sys
from datetime import datetime

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'debug_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def test_imports():
    """Test all imports"""
    logger.info("=" * 60)
    logger.info("TESTING IMPORTS")
    logger.info("=" * 60)

    imports = [
        ("config", "from config import DB_PATH, FETCH_INTERVAL, TradingConfig"),
        ("storage", "from storage import Storage"),
        ("filters", "from filters import filter_tokens_batch"),
        ("technicals", "from technicals import Technicals"),
        ("trader", "from trader import Trader"),
        ("token_discovery", "from api_clients.token_discovery import TokenDiscovery"),
        ("gmgn", "from api_clients.gmgn import GMGNClient"),
        ("smart_money", "from smart_money import SmartMoneyTracker"),
    ]

    for name, import_stmt in imports:
        try:
            exec(import_stmt)
            logger.info(f"✓ {name} imported successfully")
        except Exception as e:
            logger.error(f"✗ {name} import failed: {e}")
            return False

    return True

def test_config():
    """Test configuration"""
    logger.info("=" * 60)
    logger.info("TESTING CONFIGURATION")
    logger.info("=" * 60)

    try:
        from config import TradingConfig, FETCH_INTERVAL, DB_PATH

        logger.info(f"Fetch Interval: {FETCH_INTERVAL}s")
        logger.info(f"Database Path: {DB_PATH}")
        logger.info(f"Wallet Private Key: {'SET' if TradingConfig.WALLET_PRIVATE_KEY else 'NOT SET'}")
        logger.info(f"Wallet Address: {TradingConfig.WALLET_ADDRESS if TradingConfig.WALLET_ADDRESS else 'NOT SET'}")
        logger.info(f"RPC Endpoint: {TradingConfig.RPC_ENDPOINT}")
        logger.info(f"Max Position Size: ${TradingConfig.MAX_POSITION_SIZE_USD}")

        if not TradingConfig.WALLET_PRIVATE_KEY:
            logger.error("✗ Wallet private key not configured!")
            return False

        if not TradingConfig.WALLET_ADDRESS:
            logger.error("✗ Wallet address not configured!")
            return False

        logger.info("✓ Configuration looks good")
        return True

    except Exception as e:
        logger.error(f"✗ Configuration test failed: {e}")
        return False

def test_token_discovery():
    """Test token discovery (limited)"""
    logger.info("=" * 60)
    logger.info("TESTING TOKEN DISCOVERY")
    logger.info("=" * 60)

    try:
        from api_clients.token_discovery import TokenDiscovery

        discovery = TokenDiscovery()
        logger.info("✓ TokenDiscovery initialized")

        logger.info("Fetching tokens (limited to 5 seconds)...")
        start = time.time()
        tokens = discovery.discover_all_tokens(max_workers=2)
        elapsed = time.time() - start

        logger.info(f"✓ Discovered {len(tokens)} tokens in {elapsed:.1f}s")

        if tokens:
            logger.info("Sample token:")
            sample = tokens[0]
            for key, value in sample.items():
                logger.info(f"  {key}: {value}")

        return True

    except Exception as e:
        logger.error(f"✗ Token discovery failed: {e}", exc_info=True)
        return False

def test_filtering():
    """Test filtering"""
    logger.info("=" * 60)
    logger.info("TESTING FILTERING")
    logger.info("="* 60)

    try:
        from filters import filter_tokens_batch

        # Create mock tokens
        mock_tokens = [
            {
                'address': 'test123',
                'symbol': 'TEST',
                'daily_volume_usd': 10000,
                'price_change_24h': 50,
                'liquidity_usd': 50000,
                'market_cap': 500000,
                'age_hours': 24
            }
        ]

        filtered = filter_tokens_batch(mock_tokens, max_tokens=10, min_score=0.1)
        logger.info(f"✓ Filtered {len(filtered)} / {len(mock_tokens)} tokens")

        if filtered:
            logger.info(f"Sample filtered token score: {filtered[0].get('filter_score', 0):.3f}")

        return True

    except Exception as e:
        logger.error(f"✗ Filtering failed: {e}", exc_info=True)
        return False

def test_trader():
    """Test trader initialization"""
    logger.info("=" * 60)
    logger.info("TESTING TRADER")
    logger.info("=" * 60)

    try:
        from trader import Trader
        from storage import Storage
        from config import DB_PATH

        storage = Storage(DB_PATH)
        trader = Trader(storage)

        logger.info("✓ Trader initialized successfully")
        return True

    except Exception as e:
        logger.error(f"✗ Trader initialization failed: {e}", exc_info=True)
        return False

def test_single_cycle():
    """Test a single bot cycle"""
    logger.info("=" * 60)
    logger.info("TESTING SINGLE BOT CYCLE")
    logger.info("=" * 60)

    try:
        from main import TradingBot

        bot = TradingBot()
        logger.info("✓ Bot initialized")

        logger.info("Running single cycle...")
        start = time.time()
        bot.run_single_cycle()
        elapsed = time.time() - start

        logger.info(f"✓ Cycle completed in {elapsed:.1f}s")
        logger.info(f"   Tokens discovered: {bot.total_tokens_discovered}")
        logger.info(f"   Tokens filtered: {bot.total_tokens_filtered}")
        logger.info(f"   Trades executed: {bot.total_trades_executed}")

        return True

    except Exception as e:
        logger.error(f"✗ Bot cycle failed: {e}", exc_info=True)
        return False

def main():
    """Run all debug tests"""
    logger.info("")
    logger.info("🔍 THOR DEBUG MODE")
    logger.info("=" * 60)
    logger.info("")

    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Token Discovery", test_token_discovery),
        ("Filtering", test_filtering),
        ("Trader", test_trader),
        ("Single Cycle", test_single_cycle),
    ]

    results = []
    for name, test_func in tests:
        try:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Running: {name}")
            logger.info(f"{'=' * 60}\n")

            result = test_func()
            results.append((name, result))

            if result:
                logger.info(f"\n✅ {name} PASSED\n")
            else:
                logger.error(f"\n❌ {name} FAILED\n")

        except Exception as e:
            logger.error(f"\n💥 {name} CRASHED: {e}\n", exc_info=True)
            results.append((name, False))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("DEBUG SUMMARY")
    logger.info("=" * 60)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {name}")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    logger.info("=" * 60)
    logger.info(f"Result: {passed}/{total} tests passed")
    logger.info("=" * 60)

    if passed == total:
        logger.info("\n🎉 All tests passed! Bot should work correctly.\n")
        return 0
    else:
        logger.error(f"\n⚠️  {total - passed} test(s) failed. Review errors above.\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
