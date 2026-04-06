# 🚀 How to Run the Bot

## Setup: Open 2 Terminals

### Terminal 1: Main Bot
```bash
cd C:\Users\lhsim\OneDrive\Documentos\Polymarket-bot
python run_bot.py
```

**What it does:**
1. Runs 4 quick tests to verify everything works
2. If tests pass, starts trading continuously
3. Shows all activity in real-time
4. Press `Ctrl+C` to stop gracefully

**Options:**
```bash
python run_bot.py              # Run tests, then trade
python run_bot.py --test-only  # Only run tests
python run_bot.py --skip-tests # Skip tests, start trading
```

### Terminal 2: Live Monitor (Optional)
```bash
cd C:\Users\lhsim\OneDrive\Documentos\Polymarket-bot
python monitor_bot.py
```

**What it shows:**
- Current wallet balance
- Active markets and prices
- Recent trades
- Refreshes every 30 seconds
- Press `Ctrl+C` to exit

---

## Quick Start

**Recommended first run:**
```bash
# Terminal 1
python run_bot.py --test-only
```

This runs all tests without trading. If tests pass, then:

```bash
# Terminal 1
python run_bot.py
```

And optionally in another terminal:
```bash
# Terminal 2
python monitor_bot.py
```

---

## What to Expect

### During Tests (30-60 seconds):
```
[1/4] Testing Polymarket connection...
  ✓ Connected successfully

[2/4] Testing market discovery...
  ✓ Found BTC market: Bitcoin Up or Down - ...

[3/4] Testing token extraction...
  ✓ Extracted YES and NO tokens

[4/4] Testing price fetching and validation...
  ✓ YES: 0.5050, NO: 0.4950, Sum: 1.0000
  ✓ Market valid: True

TESTS PASSED: 4/4
```

### During Trading:
- Bot waits for next 15-minute window
- Collects 49 ML features for 14 minutes
- Makes prediction at 14:00
- Places bet at 14:59 (last second)
- Waits for resolution
- Learns from result
- Repeats

---

## Files Created

- `run_bot.py` - Main bot runner with tests
- `monitor_bot.py` - Live monitoring dashboard
- `reports/` - Trade reports saved here (JSON format)

---

## Stopping the Bot

Press `Ctrl+C` in Terminal 1 to stop gracefully. The bot will:
- Close all WebSocket connections
- Save final statistics
- Generate final report

---

## Configuration

All settings in `config/config.yaml`:
- Initial bet: 0.5 USDC
- Profit increase: 10%
- All 5 enhancements: Enabled

---

## Troubleshooting

**If tests fail:**
1. Check .env file has WALLET_PRIVATE_KEY
2. Check internet connection
3. Verify wallet has USDC and POL

**If bot crashes:**
- Check Terminal 1 for error messages
- Recent report saved in `reports/` folder
- Bot can be restarted anytime

---

## Current Configuration

✅ Wallet: 7.90 USDC + 41.86 POL
✅ Initial Bet: 0.5 USDC per trade
✅ Trading: BTC, ETH, SOL (15-minute markets)
✅ ML Features: 49 (including cross-market correlations)
✅ All Enhancements: Active

**Ready to trade!** 🎯
