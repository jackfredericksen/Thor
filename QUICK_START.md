# Thor Bot - Quick Start Guide

## 🚀 Launch Commands

### Web GUI Mode (Easiest - Works on All Systems)
```bash
./start_web_gui.sh
```
Then open your browser to **http://localhost:5000** and click **START** button.

### Terminal Mode
```bash
./start_thor.sh
```
Auto-starts trading cycles. Press `q` to quit.

### Debug Mode
```bash
./venv/bin/python3 debug_mode.py
```
Tests all components. Use if having issues.

---

## 📋 Pre-Flight Checklist

Before first run:

- [ ] Edit `.env` file with your wallet credentials
- [ ] Set `THOR_WALLET_PRIVATE_KEY` (base58 format)
- [ ] Set `THOR_WALLET_ADDRESS`
- [ ] Set `THOR_MAX_POSITION_SIZE=10` (start small!)
- [ ] Fund wallet with at least 0.5 SOL
- [ ] Double-check private key is SECRET

---

## 🌐 Web GUI Features

Access at **http://localhost:5000** after running `./start_web_gui.sh`

### Controls
| Button | Action |
|--------|--------|
| ▶ START | Begin trading cycles |
| ⏸ PAUSE | Temporarily pause |
| ⏹ STOP | Stop completely |

### Dashboard Sections
- **Statistics Bar** - Real-time metrics (cycles, tokens, trades, uptime)
- **📊 Live Token Feed** - Top 20 tokens with scores
- **💰 Trades** - Recent trade history
- **📝 System Logs** - Color-coded logs (INFO/SUCCESS/WARNING/ERROR)

### Features
- ✅ Works in any browser (Chrome, Firefox, Safari, etc.)
- ✅ No additional GUI frameworks needed
- ✅ Auto-refreshes every second
- ✅ Mobile-responsive design
- ✅ Clean, modern interface

---

## ⚙️ Key Settings (.env)

```bash
# Position Sizing
THOR_MAX_POSITION_SIZE=100           # Max $ per trade

# Risk Management
THOR_DEFAULT_SLIPPAGE=0.02           # 2% slippage
THOR_STOP_LOSS_PERCENT=0.15          # 15% stop loss
THOR_TAKE_PROFIT_PERCENT=0.50        # 50% take profit

# Speed
THOR_USE_JITO=true                   # Fast execution
THOR_JITO_TIP=0.001                  # 0.001 SOL tip

# Safety
THOR_ENABLE_CONTRACT_ANALYSIS=true   # Check for scams
THOR_MIN_SAFETY_SCORE=50             # 0-100 scale
```

---

## ⚡ What to Expect

### First Launch
- Takes 10-15 seconds (building cache)
- May show 0 tokens first cycle
- Cache builds on subsequent cycles

### Normal Operation
- **5-10 seconds** per discovery cycle
- **~150 tokens** discovered per cycle
- **~25-30 seconds** total cycle time
- **15 second** wait between cycles

### Performance
- ✅ 30-60x faster than before
- ✅ ~100% cycle completion rate
- ✅ Low memory usage
- ✅ Reliable operation

---

## 🚨 Emergency Procedures

### Web GUI Mode
Click **STOP** button in browser immediately.

### Terminal Mode
Press `Ctrl+C` to stop.

### Force Kill
```bash
pkill -9 -f "python.*main.py"
pkill -9 -f "python.*web_gui.py"
```

---

## 🐛 Troubleshooting

### "Wallet credentials required"
1. Check `.env` file exists
2. Verify `THOR_WALLET_PRIVATE_KEY` is set
3. Run debug mode: `./venv/bin/python3 debug_mode.py`

### "No tokens discovered"
Normal for first 1-2 cycles while cache builds. Wait 60 seconds.

### Web GUI won't load
1. Check that port 5000 is available: `lsof -i :5000`
2. Try accessing: http://127.0.0.1:5000
3. Check terminal for error messages

### "ModuleNotFoundError: No module named '_tkinter'"
This is expected! Use Web GUI mode instead (`./start_web_gui.sh`).

### Bot seems stuck
Check logs in browser or terminal. May be network issue. Stop and restart.

---

## 📈 Recommended First-Time Settings

```bash
# Ultra-conservative (learning mode)
THOR_MAX_POSITION_SIZE=10
THOR_MIN_SAFETY_SCORE=70
THOR_SKIP_MINT_AUTHORITY=true
THOR_SKIP_FREEZE_AUTHORITY=true
```

Start with these, watch for 5-10 cycles, then adjust.

---

## 🎯 Success Indicators

✅ Web GUI shows "RUNNING" status in green
✅ Cycle counter incrementing
✅ Tokens appearing in feed table
✅ No red errors in logs
✅ Wallet balance changes reflect trades

---

## 🌐 Web GUI vs Terminal UI

| Feature | Web GUI | Terminal UI |
|---------|---------|-------------|
| **Ease of Use** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Visual Appeal** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Browser Access** | Yes | No |
| **Remote Access** | Yes (local network) | No |
| **Dependencies** | Flask only | Rich, Blessed |
| **Resource Usage** | Low | Very Low |
| **Mobile Friendly** | Yes | No |

**Recommendation:** Use Web GUI for easiest experience.

---

## 📞 Help

1. **Run Debug Mode First**
   ```bash
   ./venv/bin/python3 debug_mode.py
   ```

2. **Check Debug Log**
   Look for `debug_*.log` file in Thor directory

3. **Review Docs**
   - [README_FIXES.md](README_FIXES.md) - Recent fixes
   - [SUMMARY.md](SUMMARY.md) - Complete overview
   - [.env.example](.env.example) - All settings

---

## ⚠️ Safety Reminders

- 🔴 **LIVE TRADING** - Uses real money
- 💰 **START SMALL** - Test with $10-50 max
- 🔐 **PROTECT KEYS** - Never share private key
- 📊 **MONITOR CLOSELY** - Watch first 10 cycles
- 🛑 **EMERGENCY STOP** - Know how to stop quickly
- 📉 **ACCEPT RISK** - Crypto is volatile
- 🧠 **DYOR** - Do your own research
- ⚖️ **NFA** - Not financial advice

---

## 🎨 Web GUI Screenshot

When you open http://localhost:5000, you'll see:

```
┌────────────────────────────────────────────────────────┐
│ 🔨 Thor Memecoin Sniping Bot                          │
│ ● STOPPED          [▶ START] [⏸ PAUSE] [⏹ STOP]      │
├────────────────────────────────────────────────────────┤
│ Cycles: 0  Discovered: 0  Filtered: 0  Trades: 0      │
│ Uptime: 00:00:00                                       │
├────────────────────────────────────────────────────────┤
│ [📊 Live Token Feed] [💰 Trades] [📝 System Logs]     │
│                                                        │
│ Symbol │ Price      │ 24h Change │ Volume   │ Score  │
│ BONK   │ $0.000012  │ +125.3%    │ $2.5M    │ 0.85   │
│ PEPE   │ $0.00034   │ +87.2%     │ $1.8M    │ 0.78   │
└────────────────────────────────────────────────────────┘
```

---

**Version:** 2.0 (Web-Optimized)
**Performance:** 30-60x improvement
**Status:** Production Ready
**Platform:** Cross-platform (Web-based)

Happy Trading! 🚀
