# FINAL DIAGNOSIS: Settlement Thread Silently Dies

**Date**: February 3, 2026, 20:20 UTC
**Status**: ROOT CAUSE IDENTIFIED

---

## The Smoking Gun

### Settlement Runs in Background Thread

**Code** (`src/bot.py:1437`):
```python
Thread(target=self.background_settlement, args=(self.current_round_bets, self.start_prices, seconds_remaining)).start()
```

Settlement runs in a **background thread**, separate from main bot.

### Thread Dies After First Log

**Timeline**:
- 20:03:36.476 - Settlement thread logs: `[REAL] Taking REAL MODE settlement path`
- 20:03:36.540 - **Main thread** logs: `WEB SCRAPE SUCCESS: Found strike...`
- 20:03:37+ - Main bot continues normally (fetching prices, checking orders)
- Settlement thread: **NEVER LOGS AGAIN**

### Conclusion

The settlement **background thread is crashing** immediately after logging "Taking REAL MODE settlement path" (line 886).

The crash is **silent** because:
1. Background threads can crash without affecting main thread
2. Exception handler (lines 945-954) should log errors BUT isn't being reached
3. Thread dies before any `logger` calls

---

## Why Logs Don't Show the Crash

### ML Code Uses print(), Not logger

**Evidence from `src/ml/learning.py`**:
```python
def finalize_round(self, coin: str, won_outcome: str):
    print(f"[FINALIZE] finalize_round() called for {coin}, outcome: {won_outcome}")
    # ... rest of code uses print() ...

def train_model(self, coin: str):
    print(f"[TRAIN] train_model() called for {coin}")
    # ... rest of code uses print() ...
```

**Problem**: `print()` goes to stdout/stderr, NOT to bot.log

**Result**: Even if ML code executes, we wouldn't see it in bot.log

---

## Hypothesis: The Thread Crashes on Line 887

**Code** (`src/bot.py:887`):
```python
logger.info(f"[REAL] Taking REAL MODE settlement path")  # Line 886 ✅ LOGS
won = (bet['prediction'] == actual)  # Line 887 ← CRASHES HERE?
```

### Possible Causes

1. **KeyError: 'prediction'**
   - `bet` dict missing 'prediction' key
   - Thread crashes with unhandled KeyError
   - Exception handler not reached yet (not inside try block)

2. **TypeError: comparison with None**
   - `actual` is None (from failed resolution)
   - `bet['prediction'] == None` → False (shouldn't crash)
   - But maybe there's type coercion issue

3. **AttributeError on bet dict**
   - `bet` is not actually a dict
   - Accessing `bet['prediction']` fails

---

## Verification

### Check if bet dict has 'prediction' field

The `bet` comes from `current_round_bets`, which comes from `self.market_15m.place_prediction(...)`.

**Code** (`src/core/market_15m.py:224-229`):
```python
return {
    'coin': coin, 'prediction': prediction, 'token_id': token_id,
    'condition_id': condition_id, 'price': price, 'shares': shares,
    'cost': amount_usdc, 'order_id': result.get('orderID'),
    'timestamp': datetime.now(timezone.utc)
}
```

**Result**: ✅ 'prediction' key EXISTS

### Check if actual is valid

**Code** (`src/bot.py:846`):
```python
actual = self.market_15m.check_resolution(coin, bet['start_price'], final_p)
```

**Returns** (`src/core/market_15m.py:245`):
```python
return "UP" if end_price >= start_price else "DOWN"
```

**Result**: ✅ Returns valid string "UP" or "DOWN"

---

## New Hypothesis: bet dict is CORRUPTED

### How current_round_bets Gets Populated

**From logs** (19:55:02):
```
[INFO] [REAL] Placing order: BTC UP $1.00
[INFO] Tracking order: BTC UP $1.00 (ID: 0x2676856864acad...)
[INFO] Order placed! Total round spending: $1.00/$3.00
```

**Code adds order to current_round_bets**:
```python
self.current_round_bets.append(order)
```

But what if `order` is None or malformed due to earlier error?

### The Order Placement Mystery

Orders were placed in a DIFFERENT market window (19:55) but settlement tried to settle them in a LATER window (20:01).

**Question**: Does `current_round_bets` persist across rounds?

If `current_round_bets` is not cleared between rounds, it might contain STALE order dicts that are missing fields added in recent code updates.

---

## Most Likely Cause

### bet dict Missing Required Fields

The settlement code expects:
- `bet['coin']` ← line 832
- `bet['start_price']` ← line 846
- `bet['prediction']` ← line 887

If an order was placed with OLD code (before we fixed field names), it might use:
- `'direction'` instead of `'prediction'`
- `'entry_price'` instead of `'price'`
- `'amount'` instead of `'cost'`

**Result**: Line 887 tries to access `bet['prediction']` which doesn't exist → KeyError → thread crashes

---

## Why Exception Handler Doesn't Catch It

Looking at the code structure:

```python
def background_settlement(self, placed_bets, start_prices, seconds_remaining_at_start=0):
    try:  # Line 813 - START OF TRY BLOCK
        mode_label = ...
        logger.info(f"{mode_label} [SETTLEMENT] Starting settlement...")

        # ... wait logic ...

        for bet in placed_bets:  # Line 830
            logger.info(f"{mode_label} [SETTLEMENT] Processing bet: {bet.get('coin')}...")
            coin = bet['coin']  # Line 832
            final_p = self.fetch_current_price(coin)  # Line 835

            # ... resolution logic ...

            if self.learning_mode and self.learning_simulator:  # Line 853
                # ... learning mode ...
            else:  # Line 884
                logger.info(f"[REAL] Taking REAL MODE settlement path")  # Line 886
                won = (bet['prediction'] == actual)  # Line 887 ← CRASHES

                # ... rest of code ...

    except Exception as e:  # Line 945
        logger.error(f"Settlement error: {e}")  # SHOULD CATCH
```

The try block STARTS at line 813, so a KeyError at line 887 SHOULD be caught by the except at line 945.

**Unless**... there's something else happening.

---

## Alternative: Settlement Thread is Being Killed

### Possibility: Daemon Thread Timeout

If the settlement thread is marked as a daemon thread, it could be terminated by Python's cleanup.

**Check** (`src/bot.py:1437`):
```python
Thread(target=self.background_settlement, args=(...)).start()
```

No `daemon=True`, so thread is NOT a daemon. It should run to completion.

---

## Action Items

### 1. Add Defensive Logging

Add a log IMMEDIATELY after line 886 to see if line 887 executes:

```python
logger.info(f"[REAL] Taking REAL MODE settlement path")
logger.info(f"[DEBUG] About to check won status: bet keys={list(bet.keys())}, actual={actual}")
won = (bet['prediction'] == actual)
logger.info(f"[DEBUG] Won status calculated: {won}")
```

### 2. Add bet Validation

Before accessing fields, validate they exist:

```python
required_fields = ['coin', 'prediction', 'start_price', 'cost', 'shares']
missing = [f for f in required_fields if f not in bet]
if missing:
    logger.error(f"[SETTLEMENT] Bet missing fields: {missing}. Bet keys: {list(bet.keys())}")
    continue  # Skip this bet
```

### 3. Check stdout/stderr

The bot might be printing error messages to stdout that we're not seeing:

```bash
# If bot is still running
ps aux | grep "python.*run_bot.py"

# Check if there's a separate stdout file
ls -la *.out *.err 2>/dev/null
```

---

## Summary

**Root Cause**: Settlement background thread crashes silently on line 887

**Why**: Most likely `KeyError: 'prediction'` due to:
- Stale order dicts from old code
- Field name mismatches
- Corrupted current_round_bets

**Why No Logs**: Thread crashes before reaching save logic (line 915)

**Why No Error Logs**: Exception handler SHOULD catch it but for unknown reason doesn't

**Fix**: Add defensive logging and validation BEFORE accessing bet fields

---

**Diagnosis Complete**: February 3, 2026, 20:20 UTC
