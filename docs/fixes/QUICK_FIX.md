# Quick Fix Guide - Settlement Not Saving Trades

## Problem Summary
Trades are being placed but NOT saved to `data/trade_history.json` because:
- ML episode buffer is corrupted (array shape mismatch)
- Settlement fails when trying to train ML
- Trade saving code never reached

## Quick Fix (5 minutes)

### Step 1: Stop the Bot
```bash
pkill -f "python.*bot.py"
```

### Step 2: Backup Corrupted Data
```bash
cd [PROJECT_ROOT]
mv data/ml_episodes.json data/ml_episodes.json.corrupted
```

### Step 3: Restart the Bot
```bash
python3 run_bot.py
```

### Step 4: Verify Mode at Startup

Look for this in the console:
```
============================================================
    BOT MODE: REAL (Live Trading)
    Trades save to: data/trade_history.json
    Real Balance: $XX.XX USDC
============================================================
```

If you see "LEARNING MODE", you selected the wrong option. Restart and select:
- Mode: **A** (Arbitrage) or **B** (Standard ML), NOT C
- Risk Profile: Your choice
- Budget: Your choice

### Step 5: Wait for Next Round (15 minutes)

Watch `bot.log`:
```bash
tail -f bot.log
```

Look for these lines when settlement happens:
```
[REAL] [SETTLEMENT] Starting settlement for N bets
[REAL] [SETTLEMENT] Waited 15s, now settling...
[REAL] [SETTLEMENT] Processing bet: BTC UP
[REAL] Taking REAL MODE settlement path
[REAL] Saving trade to history: BTC UP - WON
[SETTLEMENT] Trade saved successfully
```

### Step 6: Verify Trade Saved

```bash
cat data/trade_history.json | jq '.[-1]'
```

Should show the latest trade with current timestamp.

## What If Settlement Still Fails?

If you see error messages like:
```
[ERROR] ML training failed (non-fatal): ...
[REAL] Continuing to save trade anyway...
```

**This is OK!** The trade will still be saved. The error is non-fatal now.

## Recover Missing Trades (Optional)

To recover the past 3 days of missing trades from Polymarket:

```bash
python3 -m src.utils.recover_trades 3
```

This queries the Polymarket CLOB API for your order history and imports trades into `data/trade_history.json`.

**Note**: This script is experimental. It will:
- Skip trades already in history (based on order_id)
- Try to determine outcomes from market resolution
- Only import settled/resolved markets

## Check Current State

Run the verification script anytime:
```bash
python3 -m src.utils.verify_mode
```

This shows:
- Which mode indicators are in logs
- Which trade files are being updated
- Recent trades in each file
- Current state of learning mode

## Success Criteria

✅ Bot startup shows "BOT MODE: REAL (Live Trading)"
✅ Settlement logs show "[REAL]" markers
✅ Trades appear in `data/trade_history.json` after each round
✅ Trade count increases on dashboard
✅ No more "settlement error" messages

## Files Modified

The following files have been updated with fixes:

1. **src/bot.py**
   - Enhanced mode logging (lines ~250-265)
   - Order placement logging (lines ~1135, ~1255)
   - Settlement path logging (lines ~782, ~810)
   - **ML error handling** (lines ~802, ~812) - CRITICAL FIX
   - History reload in dashboard (line ~350)

2. **src/utils/verify_mode.py** (NEW)
   - Diagnostic script to check current state

3. **src/utils/recover_trades.py** (NEW)
   - Trade recovery from CLOB API

## What Changed

### Before (Broken)
```python
# In settlement:
self.learning_engine.finalize_round(coin, actual)  # <-- FAILS HERE
# ... trade saving code never reached
self.history_manager.save_trade(trade_data)
```

### After (Fixed)
```python
# In settlement:
try:
    self.learning_engine.finalize_round(coin, actual)
except Exception as ml_error:
    logger.error(f"ML training failed (non-fatal): {ml_error}")
    logger.error(f"Continuing to save trade anyway...")

# ... trade saving happens regardless
self.history_manager.save_trade(trade_data)  # <-- ALWAYS REACHED NOW
```

## Why This Fixes It

1. **ML training is now optional** - if it fails, settlement continues
2. **Trades always saved** - even if ML breaks
3. **Corrupted episode buffer cleared** - ML starts fresh
4. **Enhanced logging** - can see exactly what's happening

## Long-Term Fix (For Later)

The ML episode buffer corruption should be investigated and fixed in `src/ml/learning.py`. For now, the bot will work without ML training until the buffer is repaired.

Once you have 50+ trades saved successfully, ML training will resume automatically and work correctly with fresh data.

## Need Help?

If settlement still fails after these steps:

1. Check `bot.log` for error messages
2. Run `python3 -m src.utils.verify_mode`
3. Share the output of these commands:
   ```bash
   tail -50 bot.log
   cat data/trade_history.json | jq '. | length'
   ls -la data/
   ```
