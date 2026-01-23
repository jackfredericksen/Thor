# Thor Memecoin Sniping Bot - Setup Guide

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd /Users/jack/Documents/Work/Thor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your wallet details
nano .env  # or use any text editor
```

**Required fields in .env:**
- `THOR_WALLET_PRIVATE_KEY` - Your Solana wallet private key
- `THOR_WALLET_ADDRESS` - Your Solana wallet public address
- `SOLANA_RPC_ENDPOINT` - RPC endpoint (default: https://api.mainnet-beta.solana.com)

### 3. Run the Bot

```bash
python main.py
```

## 📊 Terminal UI Features

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│ THOR MEMECOIN SNIPING BOT - Status: 🟢 RUNNING             │
│ Mode: 🔴 LIVE TRADING | Cycle: 42 | Trades: 12             │
├──────────────────────────┬──────────────────────────────────┤
│ LIVE TOKEN FEED          │ PORTFOLIO                        │
│ Symbol  Price  Change    │ Total: $100,000                  │
│ BONK    $0.001 +125%     │ Cash: $85,432 (85%)              │
│ PEPE    $0.034 +87%      │ Positions: $14,568 (15%)         │
├──────────────────────────┴──────────────────────────────────┤
│ RECENT TRADES                                               │
│ 14:23:45  BUY  BONK  1.2M @ $0.000012  Bullish (0.85)      │
├─────────────────────────────────────────────────────────────┤
│ SYSTEM LOG                                                  │
│ 14:23:50 INFO  Cycle 42 complete in 12.3s                  │
└─────────────────────────────────────────────────────────────┘
Press: [p]ause [c]ommand [r]efresh [s]top [q]uit
```

### Keyboard Controls

- **`p`** - Pause/Resume discovery cycles
- **`r`** - Force refresh display (auto-refreshes every 0.25s)
- **`s`** - Emergency stop all trades (closes all positions immediately)
- **`q`** - Quit application safely
- **`c`** - Command mode (coming soon)

## 🔧 What Changed

### ✅ Removed
- Telegram authentication (was never implemented)
- Paper trading mode (now LIVE TRADING ONLY)
- Basic console logging interface

### ✅ Added
- **Rich terminal UI** with live updating panels
- **Keyboard controls** for interactive operation
- **Real-time dashboard** showing:
  - Live token discoveries
  - Portfolio tracking
  - Trade history
  - System logs
- **Wallet configuration** for Solana live trading
- **Environment variable support** via .env file

### 🚧 To Be Added (Future)
- Solana trading client (currently using placeholder)
- Jupiter aggregator integration
- Real wallet integration
- Command mode for advanced controls

## ⚠️ Important Safety Notes

### LIVE TRADING MODE
This bot is configured for **LIVE TRADING ONLY**. There is NO paper trading mode.

**Before running:**
1. ✅ Start with SMALL position sizes (set `THOR_MAX_POSITION_SIZE=10` in .env)
2. ✅ Fund your wallet with minimal SOL for testing
3. ✅ Understand the risks - you can lose money
4. ✅ Review filter settings in `config.py`
5. ✅ Test emergency stop (`s` key) immediately after starting

### Security
- **NEVER share your private key**
- **NEVER commit .env file to git** (it's in .gitignore)
- Keep your .env file secure with proper permissions:
  ```bash
  chmod 600 .env
  ```

## 📁 Project Structure

```
Thor/
├── main.py                 # Main bot with UI integration
├── config.py               # Configuration with wallet settings
├── trader.py               # Trading execution
├── filters.py              # Token filtering logic
├── storage.py              # Database operations
├── requirements.txt        # Dependencies (including Rich, Solana)
├── .env.example           # Example environment file
├── .env                   # Your actual config (create this)
│
├── ui/                    # Terminal UI package
│   ├── __init__.py
│   ├── dashboard.py       # Main dashboard orchestrator
│   ├── components.py      # UI components (panels, tables)
│   ├── keyboard.py        # Keyboard input handler
│   ├── theme.py           # Colors and styling
│   ├── log_buffer.py      # Log message buffer
│   └── log_handler.py     # Custom log handler
│
├── api_clients/           # API integrations
│   ├── token_discovery.py # Multi-source token discovery
│   ├── dexscreener.py    # Dexscreener API
│   ├── pumpfun.py        # Pump.fun API
│   ├── gmgn.py           # GMGN API
│   └── ...
│
└── utils/                 # Utility modules
    ├── logging_setup.py   # Logging configuration
    └── ...
```

## 🐛 Troubleshooting

### Bot won't start
- Check that all required environment variables are set in `.env`
- Verify Python version is 3.9+ (`python --version`)
- Ensure all dependencies are installed (`pip install -r requirements.txt`)

### UI not displaying correctly
- Your terminal must support Unicode and colors
- Try a modern terminal (iTerm2, Windows Terminal, etc.)
- Check terminal size (needs at least 100x30 characters)

### "Package not found" errors
```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt

# If specific package fails, install individually
pip install rich
pip install solana
```

### Keyboard controls not working
- On some systems, you may need to run with `sudo` for raw terminal access
- Or modify terminal permissions
- Windows users: Make sure you're using Windows Terminal or a compatible terminal

## 📚 Next Steps

### For Testing
1. Set `THOR_MAX_POSITION_SIZE=10` for minimal risk
2. Watch a few cycles to see token discovery
3. Test pause/resume with `p` key
4. Test emergency stop with `s` key

### For Production Use
1. Adjust filter thresholds in `config.py`
2. Set appropriate position sizes
3. Monitor performance over multiple cycles
4. Fine-tune based on results

### To Implement Real Trading
Currently, the bot uses GMGN placeholders. To enable real Solana trading:

1. Implement Solana client in `api_clients/solana_trader.py`
2. Integrate Jupiter aggregator for swaps
3. Update `trader.py` to use Solana client
4. Test extensively with small amounts first

## 📞 Support

- Check logs in `logs/dex_bot.log` for errors
- Review `TESTING_INSTRUCTIONS.md` for testing procedures
- See `README.md` for feature documentation

## ⚖️ License

MIT License - Use at your own risk

---

**Remember: Cryptocurrency trading is extremely risky. Never invest more than you can afford to lose.**
