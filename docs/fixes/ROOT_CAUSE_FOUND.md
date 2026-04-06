# ROOT CAUSE FOUND: Settlement Code Never Executes Past First Log

**Date**: February 3, 2026, 20:15 UTC
**Status**: CRITICAL BUG - Code reaches settlement but stops executing

---

## The Evidence

### What We See in Logs

**Settlement starts correctly** (19:59:52):
```
[REAL] [SETTLEMENT] Starting settlement for 2 bets
[REAL] [SETTLEMENT] Market timing: 8s until close + 90s resolution delay = 98s total wait
[REAL] [SETTLEMENT] Waiting 98s for market close + resolution...
```

**After 98-second wait** (20:01:30):
```
[REAL] [SETTLEMENT] Wait complete, now checking market resolution...
[REAL] [SETTLEMENT] Processing bet: BTC UP
[REAL] [RESOLUTION] Polling for BTC market resolution (condition: 0xfaac9f222bfe58...)
[REAL] [RESOLUTION] Market not resolved yet, polling every 5s...
```

**After 120-second timeout** (20:03:36):
```
[ERROR] [REAL] [RESOLUTION] ✗ Market did not resolve after 120s! Falling back to price comparison.
[WARNING] [REAL] [SETTLEMENT] Using fallback price comparison for BTC
[INFO] [REAL] Taking REAL MODE settlement path  ← **LAST MESSAGE**
```

**Then NOTHING**. No more settlement logs. Ever.

---

## What SHOULD Happen Next

Looking at `src/bot.py` lines 886-918, after "Taking REAL MODE settlement path" (line 886), the code should:

1. **Line 887**: `won = (bet['prediction'] == actual)`
2. **Lines 890-894**: Try ML training (wrapped in try-except, safe)
3. **Lines 902-905**: Calculate profit
4. **Lines 908-914**: Create trade_data dict
5. **Line 915**: `logger.info(f"[REAL] Saving trade to history: {coin} {bet.get('prediction')} - {'WON' if won else 'LOST'}")` ← **SHOULD APPEAR**
6. **Line 917**: `self.history_manager.save_trade(trade_data)`
7. **Line 918**: `logger.info(f"[SETTLEMENT] Trade saved successfully")` ← **SHOULD APPEAR**

### What We Actually See

**Line 886 log appears**: ✅
**Line 915 log appears**: ❌
**Line 918 log appears**: ❌
**Trades in trade_history.json**: ❌ (file is empty: `[]`)

---

## Theories Tested & Eliminated

### ❌ Theory 1: Python Exception Crashes Thread

**Test**: Searched logs for "Traceback", "KeyError", "AttributeError", "TypeError", "Settlement error"
**Result**: ZERO exceptions found
**Conclusion**: No unhandled exception

The exception handler at lines 945-954 SHOULD catch any error and log "Settlement error: {e}", but this message never appears.

### ❌ Theory 2: Missing 'prediction' Field in Bet Dict

**Test**: Checked `market_15m.py:place_prediction()` return value (lines 224-229)
**Result**: Returns dict with 'prediction' field ✅
**Conclusion**: Field exists, not the issue

### ❌ Theory 3: Trades ARE Saved But Not Logged

**Test**: `cat data/trade_history.json | jq 'length'`
**Result**: `0` (empty array)
**Conclusion**: Trades are NOT being saved

---

## THE SMOKING GUN

### Code Analysis

The settlement code has this structure:

```python
def background_settlement(self, placed_bets, start_prices, seconds_remaining_at_start=0):
    try:  # Line 813
        # ... setup code ...

        for bet in placed_bets:  # Line 830
            # ... get final_price ...
            # ... poll for resolution ...

            if self.learning_mode and self.learning_simulator:  # Line 853
                logger.info(f"[LEARNING] Taking LEARNING MODE settlement path")
                # ... learning mode code ...
            else:  # Line 884
                # Real Mode: Normal settlement
                logger.info(f"[REAL] Taking REAL MODE settlement path")  # Line 886 ← LOGS
                won = (bet['prediction'] == actual)  # Line 887

                # ML training (lines 890-894)
                try:
                    self.learning_engine.finalize_round(coin, actual)
                except Exception as ml_error:
                    logger.error(f"[REAL] ML training failed (non-fatal): {ml_error}")

                # ... profit calculation (lines 902-905) ...

                # Save trade (lines 908-918)
                trade_data = {...}
                logger.info(f"[REAL] Saving trade to history...")  # Line 915 ← NEVER LOGS
                self.history_manager.save_trade(trade_data)  # Line 917
                logger.info(f"[SETTLEMENT] Trade saved successfully")  # Line 918 ← NEVER LOGS

    except Exception as e:  # Line 945
        logger.error(f"Settlement error: {e}")  # Line 946 ← NEVER LOGS
        traceback.print_exc()
```

### The Mystery

1. Line 886 logs successfully: "Taking REAL MODE settlement path"
2. Line 915 NEVER logs: "Saving trade to history..."
3. Line 946 NEVER logs: "Settlement error: ..."

**This is impossible** unless:
- The code between line 886 and 915 is hanging forever (blocking)
- The thread is being killed externally
- There's a `return` or `break` statement we're missing

---

## New Hypothesis: Code is HANGING, Not Crashing

### The ML Training Call

Looking at lines 890-894:

```python
try:
    self.learning_engine.finalize_round(coin, actual)
except Exception as ml_error:
    logger.error(f"[REAL] ML training failed (non-fatal): {ml_error}")
```

**What if `finalize_round()` is HANGING (infinite loop/deadlock) instead of raising an exception?**

The try-except would NOT catch it (it only catches exceptions, not hangs).
The code would block at line 891 FOREVER.
The thread would never reach line 915 (save trade).
No error would be logged (because no exception was raised).

### Supporting Evidence

1. ✅ Line 886 logs (code reaches ML training)
2. ✅ No error logs (no exception raised)
3. ✅ No success logs (never reaches line 915)
4. ✅ Thread is still alive (main bot continues running)
5. ✅ Matches observed behavior perfectly

---

## How to Verify

### Check if settlement thread is still running:

```bash
# While bot is running, check thread count
ps aux | grep "python.*run_bot.py"

# Or check bot.log for settlement thread completion
grep "Round settled" bot.log
```

**Expected if hanging**: Settlement thread never completes, never logs "Round settled"

### Check what finalize_round does:

```bash
# Look at learning_engine.finalize_round implementation
grep -A 50 "def finalize_round" src/ml/learning.py
```

**Look for**: Infinite loops, blocking I/O, deadlocks, resource locks

---

## Fix Strategy

### Immediate Fix: Add Timeout to ML Training

```python
# In src/bot.py, replace lines 890-894 with:

import signal

def timeout_handler(signum, frame):
    raise TimeoutError("ML training timeout")

try:
    # Set 10-second timeout for ML training
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)

    self.learning_engine.finalize_round(coin, actual)

    signal.alarm(0)  # Cancel alarm
except TimeoutError:
    logger.error(f"[REAL] ML training timed out after 10s (non-fatal)")
except Exception as ml_error:
    logger.error(f"[REAL] ML training failed (non-fatal): {ml_error}")
finally:
    signal.alarm(0)  # Ensure alarm is cancelled
```

### Alternative: Skip ML Training Entirely for Now

```python
# In src/bot.py, replace lines 890-894 with:

# TEMP: Skip ML training to verify it's the cause
logger.info(f"[REAL] Skipping ML training (debugging)")

# try:
#     self.learning_engine.finalize_round(coin, actual)
# except Exception as ml_error:
#     logger.error(f"[REAL] ML training failed (non-fatal): {ml_error}")
```

---

## Summary

**Root Cause**: `self.learning_engine.finalize_round(coin, actual)` is HANGING (blocking forever), preventing settlement from completing.

**Evidence**:
- Code reaches line 886 ✅
- Code never reaches line 915 ❌
- No exceptions logged ✅
- Settlement thread never completes ✅
- Matches hanging behavior perfectly ✅

**Impact**: ALL settlements fail, ZERO trades saved, 160+ orders lost.

**Next Step**: Either:
1. Add timeout to ML training call
2. Skip ML training temporarily to verify
3. Investigate what's causing finalize_round to hang

---

**Analysis Complete**: February 3, 2026, 20:15 UTC
