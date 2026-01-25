# Thor - Solana Memecoin Sniping Bot

A terminal-based trading bot for discovering and trading new Solana memecoins. Built for speed, runs in your terminal, trades on-chain.

## What It Does

Thor continuously scans multiple sources (Pump.fun, DexScreener, Raydium, etc.) looking for new token launches. It filters them based on volume, liquidity, holder distribution, and age, then executes trades automatically through Jupiter when it finds something that matches your criteria.

Think of it as having 8 different browser tabs open watching for new tokens, with rules for what to buy and when to sell - except it all happens in one terminal window and trades automatically.

## Quick Start

```bash
# Clone and setup
cd Thor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure your wallet
cp .env.example .env
nano .env  # Add your Solana wallet private key

# Run
python3 main.py
```

You'll see a live dashboard with token discoveries, your portfolio, and recent trades. Press `s` to emergency stop, `q` to quit.

## What You'll See

```
┌─ THOR - Status: RUNNING | Mode: LIVE TRADING ───┐
│ Cycle: 42 | Discovered: 1,247 | Trades: 12      │
├──────────────────┬──────────────────────────────┤
│ LIVE TOKENS      │ PORTFOLIO                    │
│ BONK  +125%      │ Value: $1,234                │
│ PEPE  +87%       │ Positions: 3                 │
│ WIF   +65%       │ P&L: +$156                   │
├──────────────────┴──────────────────────────────┤
│ TRADES                                          │
│ 14:23  BUY  BONK  $12.40  Bullish (0.85)       │
└─────────────────────────────────────────────────┘
```

Real-time updates, color-coded logs, keyboard controls.

## How It Works

### Discovery (every 15 seconds)
- Fetches new tokens from 8 different sources in parallel
- Gets price, volume, liquidity, holder count, age
- Typically finds 500-1500 tokens per cycle

### Filtering
- Removes garbage (LP tokens, obvious scams, test tokens)
- Checks volume (min $500/day), liquidity (min $2k), age (< 30 days preferred)
- Scores each token 0-1 based on 6 factors
- Only passes tokens with score > 0.25

### Trading
- Calculates position size based on confidence score and risk limits
- Gets best swap route from Jupiter aggregator
- Executes on-chain transaction through Solana
- Tracks positions and P&L automatically

### Risk Management
- Max position size (default $1000, configurable)
- Max concurrent positions (default 50)
- Stop loss at -15%, take profit at +50%
- Emergency stop closes everything immediately

## Configuration

Edit `.env`:

```bash
# Required
THOR_WALLET_PRIVATE_KEY=your_base58_encoded_private_key
THOR_WALLET_ADDRESS=your_public_address
SOLANA_RPC_ENDPOINT=https://api.mainnet-beta.solana.com

# Optional
THOR_MAX_POSITION_SIZE=100   # USD per trade
THOR_DEFAULT_SLIPPAGE=0.02   # 2%
```

All the data source APIs are public - no API keys needed for basic operation. Optional keys (Birdeye, CoinGecko, etc.) can enhance data but aren't required.

## Keyboard Controls

- `p` - Pause/resume discovery cycles
- `r` - Force refresh display
- `s` - Emergency stop (closes all positions)
- `q` - Quit

## Advanced Features

Thor includes several competitive features found in professional sniping bots:

### 🚀 Jito MEV Bundles
- **40-60x faster execution** (~0.05s vs regular 2-3s)
- Atomic transaction bundling
- Configurable priority tipping
- Enable in `.env`: `THOR_USE_JITO=true`

### 🔒 Token Contract Analysis
- Automatic honeypot detection
- Mint authority checks (infinite supply risk)
- Freeze authority checks (wallet freeze risk)
- Holder concentration analysis
- Safety scoring (0-100)

### 📈 Trailing Stop Loss
- Locks in profits as price rises
- Adjustable trailing distance
- Adaptive mode (volatility-based)
- Tiered mode (tightens with profit)

### 💰 DCA (Dollar-Cost Averaging)
- Splits large orders into smaller chunks
- Reduces slippage on entry/exit
- Smart DCA adjusts to price action
- Configurable intervals and order count

### 👥 Copy Trading / Wallet Tracking
- Monitor successful wallets
- Auto-copy their trades
- Configurable copy percentage
- Track multiple wallets simultaneously

### ⚡ Pre-Market Sniping
- Mempool monitoring for new listings
- Raydium pool detection
- Jito mempool access (advanced)
- Auto-snipe with filters

### 🔄 Multi-Wallet Support
- Wallet rotation for anonymity
- Round-robin, random, or balance-based
- Auto-rebalancing across wallets
- Isolate risk per wallet

### 📊 Social Sentiment (Optional)
- Twitter/X mention tracking
- Reddit sentiment analysis
- Trending score calculation
- Filter trades by sentiment

## Adjusting Filters

Open `config.py` and modify the `FilterConfig` class:

```python
class FilterConfig:
    MIN_VOLUME_USD = 500        # Raise to be more selective
    MIN_LIQUIDITY_USD = 2_000   # Higher = safer but fewer opportunities
    MAX_AGE_HOURS = 720         # Newer tokens only
    MIN_MARKET_CAP = 5_000      # Floor for viability
```

Higher thresholds = fewer but potentially better quality tokens. Lower = more opportunities but higher risk.

Or enable advanced features in `.env`:

```bash
# Jito for speed
THOR_USE_JITO=true
THOR_JITO_PRIORITY=high

# Safety first
THOR_ENABLE_CONTRACT_ANALYSIS=true
THOR_SKIP_MINT_AUTHORITY=true
THOR_SKIP_FREEZE_AUTHORITY=true

# Lock in profits
THOR_ENABLE_TRAILING_STOP=true
THOR_USE_TIERED_TRAILING=true

# Reduce slippage
THOR_ENABLE_DCA=true
THOR_DCA_NUM_ORDERS=5
```

## Project Structure

```
Thor/
├── main.py                      # Bot orchestration
├── trader.py                    # Trade execution
├── filters.py                   # Token filtering logic
├── config.py                    # All settings
├── trailing_stop.py             # Trailing stop loss system
├── dca_manager.py               # DCA order management
├── mempool_monitor.py           # Pre-market sniping
├── multi_wallet.py              # Multi-wallet rotation
├── sentiment_tracker.py         # Social sentiment
├── api_clients/
│   ├── solana_trader.py        # Solana/Jupiter + Jito
│   ├── token_discovery.py      # Multi-source discovery
│   ├── token_analyzer.py       # Contract safety analysis
│   ├── jito_client.py          # Jito MEV bundles
│   ├── wallet_tracker.py       # Copy trading system
│   └── [various APIs]          # DexScreener, Pump.fun, etc.
└── ui/
    ├── dashboard.py            # Terminal interface
    ├── components.py           # UI panels
    ├── keyboard.py             # Input handling
    └── theme.py                # Styling
```

Core logic is in `filters.py` (what tokens pass) and `trader.py` (how trades execute). Advanced features are in their own modules for easy enable/disable.

## Performance Notes

**With default settings (free RPC):**
- 2-3 second discovery cycles
- 3-5 second trade execution
- Occasional rate limiting

**With Jito MEV enabled:**
- Same discovery speed
- **0.05-0.1 second trade execution** (40-60x faster)
- Priority ordering in blocks
- Higher success rate on competitive tokens

**With paid RPC (Helius, QuickNode) + Jito:**
- Sub-second discovery
- 0.05s execution
- No rate limits
- Maximum competitiveness

The bot competes with other snipers through:
1. Early discovery (8 parallel sources)
2. Fast execution (Jito bundles)
3. Smart filtering (contract analysis, sentiment)
4. Risk management (trailing stops, DCA)

## Common Issues

**"Wallet credentials required"**
You forgot to set `THOR_WALLET_PRIVATE_KEY` in `.env`

**Transactions failing**
Either insufficient SOL for gas, or the token has low liquidity. Check Solana explorer for details.

**UI looks weird**
Use a modern terminal (iTerm2, Hyper, Windows Terminal). Default terminals often have rendering issues.

**No tokens passing filters**
Market might be slow, or your filters are too strict. Lower `MIN_VOLUME_USD` or `MIN_MARKET_CAP` in `config.py`.

## Files You Care About

- **`.env`** - Your wallet credentials (NEVER commit this)
- **`config.py`** - All trading parameters and filters
- **`filters.py`** - The actual filtering logic
- **`logs/dex_bot.log`** - Full activity log

Everything else is either infrastructure or UI code.

## Testing Approach

Don't just run this on mainnet with real money immediately. Here's what I did:

1. Run it without wallet credentials first - watch discovery and filtering only
2. Set `THOR_MAX_POSITION_SIZE=5` and fund wallet with 0.05 SOL
3. Let it make 3-5 micro trades, verify on Solana explorer
4. Test emergency stop while it has positions
5. Review logs, adjust filters based on what you see
6. Gradually increase position size if results look good

The discovery system is solid - it'll find tokens. Whether you want to trade them depends entirely on your risk tolerance and filter settings.

## Tech Stack

- Python 3.9+ (asyncio for concurrent API calls)
- Rich (terminal UI - way better than print statements)
- Solana-py (blockchain interaction)
- Jupiter API (swap execution and routing)
- SQLite (trade history and position tracking)

No frameworks, no bloat. Just ~3000 lines of Python that does one thing.

## Disclaimers

**DYOR / NFA**

This is experimental software for trading highly volatile, speculative assets. Do your own research. This is not financial advice. Don't invest money you can't afford to lose.

I built this for myself because I wanted to stop manually checking Pump.fun and DexScreener every 10 minutes. It works for what I need. Your mileage may vary.

**Risks**

- Memecoins are essentially gambling
- You can lose 100% of your investment
- Rug pulls exist and filters won't catch everything
- Liquidity can vanish instantly
- Slippage on small tokens can be brutal
- Smart contracts can have exploits
- This bot can't predict the future

**Use At Your Own Risk**

The code is MIT licensed. It's provided as-is with no warranties. If you lose money, that's on you. If you make money, congrats but don't tell me about it because again - NFA.

Crypto trading bots aren't magic money printers. They're tools. Bad tools in skilled hands beat good tools in unskilled hands. Learn how the filters work, understand what you're trading, and don't blame the bot when a memecoin rugs.

**Security**

Your private key is stored in `.env` (which is gitignored). Keep that file secure. If someone gets your key, they get your funds. The bot doesn't send your key anywhere - all transactions are signed locally - but that doesn't mean you should be careless with it.

## Why "Thor"?

Needed a name. Lightning is fast. Seemed fitting for a sniping bot. That's it.

## Contributing

PRs welcome for bugs or obvious improvements. Keep it simple - no frameworks, no over-engineering, no "enterprise patterns."

If you add a new data source, follow the existing API client pattern. If you improve the filters, document your reasoning. If you rewrite everything in TypeScript, I'll close the PR.

## License

MIT - Do whatever you want with it. Just don't sue me if it breaks.

---

Made for traders who like terminals more than browser tabs. If you prefer clicking buttons, this isn't for you.

Built with coffee and frustration at missing token launches. Works on my machine™.
