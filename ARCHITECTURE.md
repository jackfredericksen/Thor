# Thor Bot - System Architecture

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                       │
├─────────────────────────────────────────────────────────────┤
│  GUI Mode (gui.py)          │  Terminal Mode (main.py)      │
│  - Tkinter window           │  - Rich terminal UI           │
│  - START/PAUSE/STOP         │  - Keyboard controls          │
│  - Real-time dashboard      │  - Live updating panels       │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      CORE BOT ENGINE                         │
│                     (TradingBot class)                       │
├─────────────────────────────────────────────────────────────┤
│  Cycle Loop (every 15 seconds):                             │
│  1. Discover tokens → 2. Filter → 3. Analyze → 4. Trade     │
└─────────────────────────────────────────────────────────────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ Discovery│  │ Filtering│  │ Analysis │  │ Execution│
│  Module  │  │  Module  │  │  Module  │  │  Module  │
└──────────┘  └──────────┘  └──────────┘  └──────────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
┌──────────────────────────────────────────────────────────┐
│                   EXTERNAL SERVICES                       │
├──────────────────────────────────────────────────────────┤
│  • DexScreener API      • Solana RPC                     │
│  • Jupiter API          • Jito MEV                       │
│  • GMGN API            • Database (SQLite)              │
└──────────────────────────────────────────────────────────┘
```

---

## 📦 Component Details

### 1. Token Discovery System

**File:** `api_clients/token_discovery.py`

```
TokenDiscovery
├── Jupiter Source (cached)
│   ├── Cache TTL: 30 minutes
│   ├── Max tokens: 100
│   └── Memecoin scoring
├── DexScreener Source
│   ├── Search: Solana pairs
│   ├── Max tokens: 50
│   └── Real-time data
└── Deduplication
    └── Address-based
```

**Key Features:**
- ⚡ Intelligent caching (30-min TTL)
- 🎯 Memecoin prioritization
- 🔄 Parallel API calls
- 📊 ~150 tokens per cycle
- ⏱️ 5-10 second execution

---

### 2. Filtering System

**File:** `filters.py`

```
Filter Pipeline
├── Quick Filter (fast)
│   ├── Volume check
│   ├── Age check
│   └── Market cap range
├── Detailed Scoring (6 categories)
│   ├── Volume score (0-1)
│   ├── Activity score (0-1)
│   ├── Liquidity score (0-1)
│   ├── Age score (0-1)
│   ├── Market cap score (0-1)
│   └── Risk assessment (0-1)
└── Final Ranking
    ├── Weighted average
    ├── Min threshold: 0.25
    └── Top 200 tokens
```

**Scoring Weights:**
- Volume: 25%
- Activity: 20%
- Liquidity: 20%
- Age: 15%
- Market Cap: 15%
- Risk: 5%

---

### 3. Technical Analysis

**File:** `technicals.py`

```
Technical Indicators
├── RSI (Relative Strength Index)
│   ├── Period: 14
│   └── Range: 0-100
├── EMA Slope (Exponential Moving Average)
│   ├── Periods: 12, 26
│   └── Trend direction
└── Bollinger Bands
    ├── Period: 20
    ├── Std Dev: 2
    └── Volatility measure

Classification
├── Bullish
│   ├── RSI > 30 and < 70
│   ├── Positive slope
│   └── Price near upper band
├── Bearish
│   ├── RSI > 30
│   ├── Negative slope
│   └── Price near lower band
└── Neutral
    └── Everything else
```

---

### 4. Trading Execution

**File:** `trader.py`

```
Trader
├── Risk Management
│   ├── Position sizing
│   ├── Portfolio limits
│   └── Stop loss/Take profit
├── Live Execution
│   ├── Solana wallet
│   ├── Jupiter swaps
│   └── Jito MEV bundles
└── Trade Recording
    ├── Database storage
    ├── History tracking
    └── Performance metrics
```

**Trade Flow:**
```
Token Signal
     ↓
Risk Check (position size, limits)
     ↓
Wallet Balance Check
     ↓
Execute Swap (Jupiter)
     ↓
Submit via Jito (fast)
     ↓
Record Trade
     ↓
Update Portfolio
```

---

### 5. Risk Management

**File:** `risk_management.py`

```
RiskManager
├── Position Sizing
│   ├── Max per trade: $100
│   ├── Portfolio %: 2%
│   └── Dynamic scaling
├── Portfolio Limits
│   ├── Max positions: 50
│   ├── Max daily trades: 200
│   └── Cooldown: 5s between trades
├── Stop Loss/Take Profit
│   ├── Stop: 15% loss
│   ├── Take: 50% profit
│   └── Trailing stops (optional)
└── Safety Checks
    ├── Mint authority
    ├── Freeze authority
    └── Contract analysis
```

---

### 6. GUI Architecture

**File:** `gui.py`

```
ThorGUI (Tkinter)
├── Main Window
│   ├── Control Frame
│   │   ├── Status indicator (●)
│   │   ├── START button
│   │   ├── PAUSE button
│   │   └── STOP button
│   ├── Stats Frame
│   │   ├── Cycles
│   │   ├── Discovered
│   │   ├── Filtered
│   │   ├── Trades
│   │   └── Uptime
│   └── Notebook (Tabs)
│       ├── Tab 1: Live Token Feed
│       │   └── Treeview table
│       ├── Tab 2: Trades
│       │   └── Trade history
│       └── Tab 3: System Logs
│           └── ScrolledText (color-coded)
├── Threading
│   ├── Main thread: GUI
│   ├── Bot thread: Trading logic
│   └── Message queue: Thread-safe updates
└── Update Loop
    └── Process queue every 100ms
```

---

## 🔄 Data Flow

### Discovery → Trading Flow

```
┌──────────────┐
│ START CYCLE  │
└──────┬───────┘
       │
       ▼
┌─────────────────────────┐
│ 1. Token Discovery      │
│    • DexScreener (50)   │
│    • Jupiter (100)      │
│    • Deduplicate        │
│    = ~150 unique tokens │
└──────┬──────────────────┘
       │ (5-10s)
       ▼
┌─────────────────────────┐
│ 2. Quick Filter         │
│    • Volume > $500      │
│    • Age < 720h         │
│    • Market cap valid   │
│    = ~50-100 tokens     │
└──────┬──────────────────┘
       │ (1-2s)
       ▼
┌─────────────────────────┐
│ 3. Detailed Scoring     │
│    • 6-factor scoring   │
│    • Rank by score      │
│    • Min score: 0.25    │
│    = ~10-30 tokens      │
└──────┬──────────────────┘
       │ (1-2s)
       ▼
┌─────────────────────────┐
│ 4. Technical Analysis   │
│    • RSI, EMA, Bands    │
│    • Classify trend     │
│    = Bullish/Bearish    │
└──────┬──────────────────┘
       │ (2-3s)
       ▼
┌─────────────────────────┐
│ 5. Risk Check           │
│    • Position limits    │
│    • Portfolio check    │
│    • Safety score       │
│    = Approve/Reject     │
└──────┬──────────────────┘
       │ (0.1s)
       ▼
┌─────────────────────────┐
│ 6. Execute Trade        │
│    • Calculate amount   │
│    • Jupiter swap       │
│    • Jito submission    │
│    = Trade confirmed    │
└──────┬──────────────────┘
       │ (1-2s)
       ▼
┌─────────────────────────┐
│ 7. Record & Update      │
│    • Database save      │
│    • Portfolio update   │
│    • GUI refresh        │
└──────┬──────────────────┘
       │
       ▼
┌──────────────┐
│ WAIT 15s     │
│ Next cycle   │
└──────────────┘
```

**Total Time:** ~25-30 seconds per cycle

---

## 🗄️ Database Schema

**File:** `storage.py`

```sql
-- Tokens Table
CREATE TABLE tokens (
    address TEXT PRIMARY KEY,
    symbol TEXT,
    data TEXT,              -- JSON blob
    source TEXT,
    discovered_at TIMESTAMP,
    last_updated TIMESTAMP
);

-- Trades Table
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    token_address TEXT,
    action TEXT,            -- 'bullish' or 'bearish'
    amount REAL,
    price REAL,
    confidence REAL,
    executed_at TIMESTAMP,
    FOREIGN KEY (token_address) REFERENCES tokens(address)
);

-- Positions Table
CREATE TABLE positions (
    token_address TEXT PRIMARY KEY,
    entry_price REAL,
    quantity REAL,
    current_value REAL,
    profit_loss REAL,
    opened_at TIMESTAMP,
    FOREIGN KEY (token_address) REFERENCES tokens(address)
);
```

---

## 🔌 External Integrations

### APIs Used

| Service | Purpose | Rate Limit | Cost |
|---------|---------|------------|------|
| DexScreener | Token discovery | 1 req/s | Free |
| Jupiter | Token list, swaps | 2 req/s | Free |
| GMGN | Smart money data | 1 req/s | Free |
| Solana RPC | Blockchain interaction | Variable | ~$0.0001/tx |
| Jito MEV | Fast execution | Variable | 0.001 SOL/bundle |

### Configuration

All API keys/endpoints in `.env`:
```bash
SOLANA_RPC_ENDPOINT=https://api.mainnet-beta.solana.com
BIRDEYE_API_KEY=optional
COINGECKO_API_KEY=optional
RUGCHECK_API_KEY=optional
```

---

## 📂 File Structure

```
Thor/
├── main.py                      # Terminal UI entry point
├── gui.py                       # GUI entry point
├── debug_mode.py                # Diagnostic tool
├── config.py                    # Configuration loader
├── trader.py                    # Trade execution
├── filters.py                   # Token filtering
├── technicals.py                # Technical analysis
├── risk_management.py           # Risk controls
├── storage.py                   # Database operations
├── smart_money.py               # Smart money tracking
├── .env                         # Secrets (DO NOT COMMIT)
├── .env.example                 # Template
├── requirements.txt             # Dependencies
├── start_thor.sh                # Terminal launcher
├── start_thor_gui.sh            # GUI launcher
├── api_clients/
│   ├── token_discovery.py       # Multi-source discovery
│   ├── solana_trader.py         # Solana/Jito integration
│   └── gmgn.py                  # GMGN API client
├── ui/
│   ├── dashboard.py             # Rich dashboard
│   ├── components.py            # UI components
│   ├── keyboard.py              # Keyboard handler
│   ├── theme.py                 # Color scheme
│   ├── log_buffer.py            # Log buffering
│   └── log_handler.py           # Custom log handler
└── docs/
    ├── README.md                # Main documentation
    ├── README_FIXES.md          # Recent fixes
    ├── SUMMARY.md               # Complete summary
    ├── QUICK_START.md           # Quick guide
    ├── ARCHITECTURE.md          # This file
    └── FEATURES.md              # Feature list
```

---

## 🔐 Security Architecture

### Secrets Management
```
Environment Variables (.env)
      ↓
load_dotenv()
      ↓
config.py (TradingConfig)
      ↓
Used by components
```

**Never Stored:**
- Private keys (in memory only)
- Wallet addresses (logged but not persisted)

**Protected:**
- `.env` in `.gitignore`
- Logs redact sensitive data
- No network transmission of keys

---

## ⚡ Performance Optimizations

### Caching Strategy
```
Jupiter Token List (287k tokens)
      ↓
Initial fetch: ~10-15s
      ↓
Cache in memory (30 min TTL)
      ↓
Subsequent fetches: 0.1s (from cache)
      ↓
Auto-refresh every 30 min
```

### Parallel Processing
```
Discovery Phase:
├── Thread 1: DexScreener fetch
└── Thread 2: Jupiter cache lookup

Filter Phase:
├── Quick filter (all tokens)
└── Detailed filter (passed tokens only)

Analysis Phase:
└── Sequential (for accurate technical calculations)
```

### Memory Management
- Token list limited to 150/cycle
- Cache limited to top 500 Jupiter tokens
- Database auto-cleanup of old records
- GUI updates throttled to 4Hz

---

## 🎯 Design Principles

1. **Performance First**
   - Cache aggressively
   - Limit API calls
   - Parallel processing where possible

2. **Safety First**
   - Risk checks before every trade
   - Position limits enforced
   - Emergency stop capability

3. **User-Friendly**
   - Clear GUI controls
   - Real-time feedback
   - Comprehensive logging

4. **Reliability**
   - Graceful error handling
   - Automatic retries
   - Fallback mechanisms

5. **Transparency**
   - All trades logged
   - Performance metrics tracked
   - Debug mode available

---

**Last Updated:** 2026-01-24
**Version:** 2.0 (Optimized)
**Architecture Status:** Production Ready
