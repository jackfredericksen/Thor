# Thor Advanced Features Guide

Complete guide to all advanced features in Thor memecoin sniping bot.

---

## 🚀 Jito MEV Bundles

### What It Does
Sends your transactions through Jito's MEV (Maximal Extractable Value) infrastructure for dramatically faster execution. Instead of waiting 2-3 seconds for regular RPC confirmation, Jito bundles land in ~0.05 seconds.

### Why It Matters
- **40-60x faster execution** than regular RPC
- **Atomic bundling** - transactions either all succeed or all fail together
- **Priority ordering** - your tx gets into the block first
- **Critical for sniping** - speed is everything when competing for new listings

### Configuration

```bash
# .env settings
THOR_USE_JITO=true
THOR_JITO_TIP=0.001              # Tip in SOL (higher = faster)
THOR_JITO_PRIORITY=medium        # min, low, medium, high, aggressive
```

**Tip Amounts:**
- `min` (0.00001 SOL) - Slowest, cheapest
- `low` (0.0001 SOL) - Basic priority
- `medium` (0.001 SOL) - Good for most trades (~$0.10)
- `high` (0.006 SOL) - Recommended for sniping (~$0.60)
- `aggressive` (0.01 SOL) - Maximum priority (~$1.00)

### Cost vs Benefit
At current SOL prices (~$100):
- Medium tip: $0.10 per trade
- High tip: $0.60 per trade
- If you're trading $100+ positions, the speed advantage pays for itself

---

## 🔒 Token Contract Analysis

### What It Does
Automatically analyzes token contracts on-chain before trading to detect rug pull risks.

### Checks Performed

**1. Mint Authority**
- Can the creator print infinite tokens?
- Dilutes your position to worthless
- Auto-skip if `THOR_SKIP_MINT_AUTHORITY=true`

**2. Freeze Authority**
- Can the creator freeze your wallet?
- Locks you out of selling
- Auto-skip if `THOR_SKIP_FREEZE_AUTHORITY=true`

**3. Holder Concentration**
- What % does the top holder own?
- >50% = very dangerous
- >30% = risky

**4. Safety Score (0-100)**
- Combines all checks
- Only trade tokens above `THOR_MIN_SAFETY_SCORE`

### Configuration

```bash
THOR_ENABLE_CONTRACT_ANALYSIS=true
THOR_MIN_SAFETY_SCORE=50          # 0-100, higher = safer
THOR_SKIP_MINT_AUTHORITY=true     # Skip dangerous tokens
THOR_SKIP_FREEZE_AUTHORITY=true   # Skip dangerous tokens
```

### Performance Impact
- Adds ~0.5s per token analyzed
- Analysis is cached for 10 minutes
- Worth it to avoid rugs

---

## 📈 Trailing Stop Loss

### What It Does
Automatically adjusts your stop loss upward as price rises, locking in profits while giving room for continued growth.

### How It Works

**Standard Trailing:**
1. You buy at $0.10
2. Set 15% trailing distance
3. Price rises to $0.20 (100% profit)
4. Stop is now at $0.17 (15% below peak)
5. Price drops to $0.17 → auto-sell
6. You locked in 70% profit instead of riding it back down

**Activation Threshold:**
- Doesn't activate until minimum profit reached
- Prevents premature stops during normal volatility
- Default: activate at 25% profit

### Types Available

**1. Standard Trailing**
- Fixed trailing distance (e.g., 15%)
- Simple and predictable

**2. Adaptive Trailing**
- Adjusts based on volatility
- High volatility = wider stop (20%)
- Low volatility = tighter stop (10%)
- `THOR_USE_ADAPTIVE_TRAILING=true`

**3. Tiered Trailing**
- Tightens as profit increases
- 25% profit → 20% trail
- 50% profit → 15% trail
- 100% profit → 10% trail
- 200% profit → 5% trail
- `THOR_USE_TIERED_TRAILING=true`

### Configuration

```bash
THOR_ENABLE_TRAILING_STOP=true
THOR_TRAILING_DISTANCE=0.15           # 15% below peak
THOR_TRAILING_ACTIVATION_PROFIT=0.25  # Activate at 25% profit
THOR_USE_ADAPTIVE_TRAILING=false      # Volatility-based
THOR_USE_TIERED_TRAILING=true         # Profit-based tiers (recommended)
```

### Best Practices
- Use tiered trailing for memecoins (volatile)
- Set activation at 25-50% profit
- Don't make trailing too tight (<10%) or you'll exit early

---

## 💰 DCA (Dollar-Cost Averaging)

### What It Does
Splits large orders into multiple smaller orders executed over time. Reduces slippage and improves average price.

### Why Use DCA

**Problem:** You want to buy $500 of a low-liquidity token.
- Single order → massive slippage (maybe 10-15%)
- You pay way over market price

**Solution:** Split into 10x $50 orders over 5 minutes
- Each order has minimal slippage (~1-2%)
- Better average entry price
- Less market impact

### Standard DCA

```bash
THOR_ENABLE_DCA=true
THOR_DCA_NUM_ORDERS=5              # Split into 5 orders
THOR_DCA_INTERVAL_SECONDS=30       # 30 seconds between orders
THOR_DCA_MIN_POSITION_SIZE=1.0     # Only DCA positions > 1 SOL
```

### Smart DCA

Adjusts dynamically based on price action:

- **Price dropping?** Accelerate buying (larger orders, shorter intervals)
- **Price rising?** Slow down buying (smaller orders, longer intervals)
- **High volatility?** Wait longer between orders

```bash
THOR_USE_SMART_DCA=true
```

### Example

Regular order: Buy 5 SOL of TOKEN
- All at once
- Slippage: 12%
- Average price: $0.00112

DCA order: Buy 5 SOL of TOKEN (5x 1 SOL orders @ 30s intervals)
- Order 1: Price $0.001000, slippage 2%
- Order 2: Price $0.001005, slippage 2%
- Order 3: Price $0.001010, slippage 2%
- Order 4: Price $0.000998, slippage 2%
- Order 5: Price $0.001003, slippage 2%
- Average price: $0.001003 (vs $0.00112)
- **Saved 10%**

### When to Use
- Large positions (>0.5 SOL)
- Low liquidity tokens
- Selling large positions
- Volatile markets

---

## 👥 Copy Trading / Wallet Tracking

### What It Does
Monitors successful traders' wallets and automatically copies their trades.

### How It Works

1. **Find Smart Money Wallets**
   - GMGN.ai smart money list
   - DexScreener top traders
   - Community-known wallets
   - Manual addition

2. **Monitor Their Transactions**
   - Real-time websocket monitoring
   - Detects buys/sells immediately
   - Parses swap details

3. **Auto-Copy (Optional)**
   - Execute same trade
   - Configurable position size (% of theirs)
   - Apply your own filters

### Configuration

```bash
THOR_ENABLE_WALLET_TRACKING=true
THOR_AUTO_COPY_TRADES=false           # Manual review first
THOR_COPY_PERCENTAGE=0.5              # Copy 50% of their size

# Comma-separated wallet addresses
THOR_TRACKED_WALLETS=wallet1,wallet2,wallet3
```

### Adding Wallets

Via config or API:
```python
from api_clients.wallet_tracker import WalletTracker

tracker = WalletTracker(rpc_url)
tracker.add_wallet(
    wallet_address="ABC123...",
    nickname="Smart Trader 1",
    auto_copy=True,
    copy_percentage=0.5
)
```

### Safety Notes
- **Start with manual copying** (`AUTO_COPY=false`)
- Review trades before blindly copying
- Even "smart money" makes bad trades
- Apply your own contract analysis filters
- Don't copy 100% of position size

---

## ⚡ Pre-Market Sniping / Mempool Monitoring

### What It Does
Monitors pending transactions to detect new token listings before they're confirmed, allowing you to be first in.

### How It Works

**Solana doesn't have a traditional mempool, but we can:**

1. **Subscribe to Program Accounts**
   - Monitor Raydium program for new pools
   - Detect pool initialization events
   - Extract token details

2. **Watch Transaction Logs**
   - Subscribe to relevant program logs
   - Filter for "initialize" events
   - Parse token mint addresses

3. **Jito Mempool (Advanced)**
   - Access Jito's pending bundle data
   - See transactions before they land
   - Requires special access

### Configuration

```bash
THOR_ENABLE_MEMPOOL_MONITOR=false      # Advanced feature
THOR_AUTO_SNIPE_NEW_LISTINGS=false     # Very aggressive
THOR_SNIPE_AMOUNT_SOL=0.1              # Amount per snipe
THOR_SNIPE_MIN_LIQUIDITY=5.0           # Min pool liquidity
THOR_SNIPE_MAX_LIQUIDITY=1000.0        # Max pool liquidity
THOR_MONITOR_RAYDIUM=true              # Monitor Raydium pools
THOR_MONITOR_JITO_MEMPOOL=false        # Requires access
```

### Risk Warning

Pre-market sniping is **extremely high risk**:
- You're trading blind (no chart history)
- Many new listings are scams
- High failure rate
- Can lose entire snipe amount

**Only use if:**
- You understand the risks
- Using very small snipe amounts
- Have strict liquidity filters
- Combining with contract analysis

### Liquidity Filters

```bash
THOR_SNIPE_MIN_LIQUIDITY=5.0    # Skip if <5 SOL liquidity (rug risk)
THOR_SNIPE_MAX_LIQUIDITY=1000.0 # Skip if >1000 SOL (already pumped)
```

Sweet spot for sniping: 10-100 SOL initial liquidity

---

## 🔄 Multi-Wallet Support

### What It Does
Manages multiple wallets and rotates between them for trades.

### Why Use Multiple Wallets

**1. Anonymity**
- Harder to track your strategy
- Prevents copycats

**2. Risk Isolation**
- One wallet gets drained → others safe
- Distribute rugs across wallets

**3. Rate Limiting**
- Some protocols rate-limit per wallet
- Rotate to bypass limits

### Rotation Strategies

**Round Robin**
- Wallet 1 → Wallet 2 → Wallet 3 → Wallet 1...
- Predictable, even distribution

**Random**
- Randomly select next wallet
- Harder to track pattern

**Balance-Based**
- Always use wallet with highest balance
- Maximizes available capital

### Configuration

```bash
THOR_ENABLE_MULTI_WALLET=false
THOR_WALLET_ROTATION_STRATEGY=round_robin
THOR_ROTATE_AFTER_TRADES=10          # Rotate every 10 trades

# Additional wallets (comma-separated private keys)
THOR_ADDITIONAL_WALLETS=key1,key2,key3
```

### Auto-Rebalancing

The `WalletPoolManager` can automatically:
- Distribute SOL evenly across wallets
- Retire low-balance wallets
- Generate fresh wallets
- Fund new wallets from main wallet

### Security Note
- Each wallet needs a separate private key
- Keep `.env` secure
- Consider hardware wallet for main funds
- Only keep trading amounts in hot wallets

---

## 📊 Social Sentiment Tracking

### What It Does
Analyzes Twitter/X and Reddit mentions to gauge community sentiment before trading.

### Data Sources

**Twitter/X:**
- Recent tweets mentioning token
- Like/retweet counts
- Keyword sentiment analysis
- Requires Twitter API bearer token

**Reddit:**
- Posts from crypto subreddits
- CryptoMoonShots, SatoshiStreetBets, etc.
- Upvote/comment engagement
- No API key needed

### Sentiment Score

**-1.0 to +1.0:**
- **+0.5 to +1.0:** Very Bullish - high positive mentions
- **+0.2 to +0.5:** Bullish - more positive than negative
- **-0.2 to +0.2:** Neutral - mixed sentiment
- **-0.5 to -0.2:** Bearish - more negative mentions
- **-1.0 to -0.5:** Very Bearish - lots of FUD

### Configuration

```bash
THOR_ENABLE_SENTIMENT_TRACKING=false
TWITTER_API_BEARER_TOKEN=your_token_here
THOR_MIN_SENTIMENT_SCORE=0.2         # Only trade if sentiment > 0.2
```

### Sentiment Filters

Combine with other filters:
```python
# Only buy if:
# 1. Contract analysis passes
# 2. Sentiment is bullish (>0.2)
# 3. At least 50 mentions
```

### Limitations
- Sentiment can be manipulated (bots, shills)
- Lagging indicator (by the time it's trending, might be late)
- Twitter API has rate limits
- Best used as confirmation, not primary signal

---

## Configuration Presets

### Conservative (Safety First)

```bash
# Strict filters
THOR_MIN_SAFETY_SCORE=70
THOR_SKIP_MINT_AUTHORITY=true
THOR_SKIP_FREEZE_AUTHORITY=true

# Lock in profits
THOR_ENABLE_TRAILING_STOP=true
THOR_USE_TIERED_TRAILING=true

# Moderate speed
THOR_USE_JITO=true
THOR_JITO_PRIORITY=medium

# No risky features
THOR_ENABLE_MEMPOOL_MONITOR=false
THOR_AUTO_COPY_TRADES=false
```

### Aggressive (Maximum Speed)

```bash
# Fast execution
THOR_USE_JITO=true
THOR_JITO_PRIORITY=high

# Looser filters (more opportunities)
THOR_MIN_SAFETY_SCORE=40
THOR_SKIP_MINT_AUTHORITY=false

# Pre-market sniping
THOR_ENABLE_MEMPOOL_MONITOR=true
THOR_AUTO_SNIPE_NEW_LISTINGS=true
THOR_SNIPE_AMOUNT_SOL=0.1

# Copy trading
THOR_ENABLE_WALLET_TRACKING=true
THOR_AUTO_COPY_TRADES=true
```

### Balanced (Recommended)

```bash
# Good speed
THOR_USE_JITO=true
THOR_JITO_PRIORITY=medium

# Reasonable safety
THOR_ENABLE_CONTRACT_ANALYSIS=true
THOR_MIN_SAFETY_SCORE=50
THOR_SKIP_MINT_AUTHORITY=true
THOR_SKIP_FREEZE_AUTHORITY=true

# Profit protection
THOR_ENABLE_TRAILING_STOP=true
THOR_USE_TIERED_TRAILING=true

# Slippage reduction
THOR_ENABLE_DCA=true
THOR_DCA_MIN_POSITION_SIZE=1.0

# Manual review for advanced features
THOR_ENABLE_WALLET_TRACKING=true
THOR_AUTO_COPY_TRADES=false
THOR_ENABLE_MEMPOOL_MONITOR=false
```

---

## Feature Combinations

### Best for Sniping New Listings
```bash
THOR_USE_JITO=true
THOR_JITO_PRIORITY=high
THOR_ENABLE_MEMPOOL_MONITOR=true
THOR_AUTO_SNIPE_NEW_LISTINGS=true
THOR_ENABLE_CONTRACT_ANALYSIS=true  # Safety check
THOR_SNIPE_AMOUNT_SOL=0.1           # Small positions
```

### Best for Large Positions
```bash
THOR_ENABLE_DCA=true
THOR_USE_SMART_DCA=true
THOR_DCA_NUM_ORDERS=10
THOR_ENABLE_TRAILING_STOP=true
THOR_USE_TIERED_TRAILING=true
```

### Best for Anonymity
```bash
THOR_ENABLE_MULTI_WALLET=true
THOR_WALLET_ROTATION_STRATEGY=random
THOR_ROTATE_AFTER_TRADES=5
```

### Best for Copy Trading
```bash
THOR_ENABLE_WALLET_TRACKING=true
THOR_AUTO_COPY_TRADES=false         # Manual review first
THOR_COPY_PERCENTAGE=0.3            # Conservative size
THOR_ENABLE_CONTRACT_ANALYSIS=true  # Extra safety
THOR_USE_JITO=true                  # Match their speed
```

---

## Performance Impact

| Feature | Execution Delay | CPU Usage | Network Load |
|---------|----------------|-----------|--------------|
| Jito MEV | **-2.95s** ⚡ | Low | Medium |
| Contract Analysis | +0.5s | Low | Medium |
| Trailing Stop | 0s | Very Low | None |
| DCA | +30s per order | Low | Medium |
| Wallet Tracking | 0s (async) | Low | High |
| Mempool Monitor | 0s (async) | Medium | High |
| Multi-Wallet | +0.1s | Very Low | Low |
| Sentiment | 0s (cached) | Low | High |

**Net effect with Jito + Contract Analysis:**
- Regular: 3.0s execution
- With features: 0.55s execution
- **5.5x faster**

---

## Troubleshooting

### Jito Not Working
- Check `THOR_USE_JITO=true` in `.env`
- Verify sufficient SOL for tips
- Try different priority level
- Check Jito endpoint status

### Contract Analysis Slow
- Results are cached for 10 minutes
- Increase `THOR_MIN_SAFETY_SCORE` to filter faster
- Disable if speed is critical

### DCA Orders Failing
- Check individual order sizes aren't too small
- Verify sufficient balance for all orders
- Reduce `THOR_DCA_NUM_ORDERS` if markets are fast

### Wallet Tracking No Trades
- Verify wallet addresses are correct
- Check websocket connection
- Tracked wallet might not be trading
- Increase monitoring duration

### Mempool Monitor Not Detecting
- Raydium pools might not be initializing
- Check websocket connection
- Enable debug logging
- Try different RPC endpoint

---

## Cost Analysis

### Monthly Costs (Trading 100x/day)

**Jito Tips (Medium Priority):**
- 0.001 SOL × 100 trades/day × 30 days
- = 3 SOL/month
- = ~$300/month at $100/SOL

**Jito Tips (High Priority):**
- 0.006 SOL × 100 trades/day × 30 days
- = 18 SOL/month
- = ~$1,800/month

**Worth it if:**
- Your average trade is >$100
- Speed matters for your strategy
- You're sniping competitive listings
- Even 1-2% better entry saves more than tip cost

**Alternative:**
- Use medium priority for regular trades
- Use high priority only for snipes
- Mix of Jito and regular RPC

---

## Security Best Practices

1. **Never commit `.env` file**
2. **Use separate wallets for trading vs holding**
3. **Start with small amounts**
4. **Test all features individually first**
5. **Monitor first 20-30 trades closely**
6. **Set max position sizes**
7. **Use hardware wallet for main funds**
8. **Rotate trading wallets periodically**
9. **Review contract analysis results**
10. **Don't blindly auto-copy trades**
