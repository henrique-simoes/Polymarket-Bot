# Mode Detection Issue - Diagnosis & Findings

## Initial Hypothesis
**INCORRECT**: Bot incorrectly detecting REAL mode as LEARNING mode

## Actual Issue Discovered
**CORRECT**: Settlement is **FAILING SILENTLY** - trades are NOT being saved at all

## Evidence from Log Analysis

### 1. Mode Verification Results
```
Real Mode Trades (data/trade_history.json): 6 trades
Most recent real trades:
  2026-01-31T20:29:57.821498: ETH DOWN - WON
  2026-01-31T20:29:57.822407: SOL DOWN - WON
  2026-01-31T21:14:57.248198: BTC DOWN - LOST

Learning Mode Trades (data/learning_trades.json): 0 trades
```

**Conclusion**: Last successful trade was Jan 31. No learning trades exist.

### 2. Settlement Activity (Feb 3)

**17:00:08 Settlement** - FAILED with ERROR:
```
[SETTLEMENT] Processing bet: BTC DOWN
[ERROR] Settlement error: setting an array element with a sequence.
        The requested array has an inhomogeneous shape after 1 dimensions.
        The detected shape was (5000,) + inhomogeneous part.
[ERROR] Failed to settle 3 orders
  - BTC DOWN $0.00
  - ETH UP $0.00
  - SOL DOWN $0.00
```

**17:30:08 Settlement** - INCOMPLETE:
```
[SETTLEMENT] Waited 15s, now settling...
[SETTLEMENT] Processing bet: BTC UP
[INFO] New round started - Budget: $3.00  <-- Jumped to next round immediately
```

**17:45:10 Settlement** - INCOMPLETE:
```
[SETTLEMENT] Waited 15s, now settling...
[SETTLEMENT] Processing bet: BTC UP
[INFO] Wallet Balance: $24.86 USDC  <-- Jumped to next round immediately
```

## Root Cause

### Primary Issue: ML Episode Buffer Error

The error message reveals the problem:
```
setting an array element with a sequence.
The requested array has an inhomogeneous shape after 1 dimensions.
The detected shape was (5000,) + inhomogeneous part.
```

This is a **numpy array shape mismatch** in the ML learning engine's episode buffer.

**Location**: `src/ml/learning.py` - `finalize_round()` method

**What's Happening**:
1. Settlement calls `self.learning_engine.finalize_round(coin, actual)`
2. finalize_round() tries to add observation to episode buffer
3. Episode buffer has shape mismatch (inhomogeneous array)
4. Exception raised
5. **Settlement exits early** - trade never saved
6. No error logged for subsequent settlements (exception caught somewhere)

### Why Settlement Completes Instantly

After the first error, subsequent settlements show:
1. "Processing bet: BTC UP"
2. **Immediately** jumps to next round (no delay, no "Trade saved successfully" log)

This suggests:
- Exception being caught and swallowed silently
- OR early return in settlement code
- Trade saving code never reached

## What the Fixes Will Do

### Already Applied (Mode Detection Logging)

✅ Enhanced logging in `src/bot.py`:
- Clear mode indicator at startup
- `[REAL]` or `[LEARNING]` prefix on all orders
- Settlement path logging

**Benefit**: Will show us WHICH path is being taken and WHERE it fails

### Still Needed (Episode Buffer Fix)

The ML episode buffer has corrupted data. Need to:

1. **Clear corrupted episode buffer**:
   ```bash
   rm data/ml_episodes.json
   # OR
   mv data/ml_episodes.json data/ml_episodes.json.backup
   ```

2. **Fix episode buffer initialization** in `src/ml/learning.py`:
   - Ensure homogeneous array shapes
   - Add validation on buffer append
   - Handle edge cases (missing features, etc.)

3. **Add error handling** in `background_settlement()`:
   - Log ML errors without stopping settlement
   - Continue to save trade even if ML training fails

## Immediate Solution

### Option 1: Clear Episode Buffer (Quick Fix)

```bash
cd [PROJECT_ROOT]

# Backup corrupted data
mv data/ml_episodes.json data/ml_episodes.json.corrupted

# Restart bot
pkill -f "python.*bot.py"
python run_bot.py
```

**Result**: ML training will start fresh, settlement will work

### Option 2: Disable ML Training During Settlement (Safer)

Add try-catch around ML training in settlement:

```python
# In background_settlement()
try:
    self.learning_engine.finalize_round(coin, actual)
except Exception as e:
    logger.error(f"ML training failed (non-fatal): {e}")
    # Continue to save trade anyway
```

**Result**: Trades save even if ML fails

## Files That Need Changes

### 1. `src/bot.py` (ALREADY MODIFIED ✅)
- Enhanced logging
- History reload

### 2. `src/bot.py` - Settlement Error Handling (NEW)
- Wrap ML training in try-catch
- Ensure trade saving happens regardless

### 3. `src/ml/learning.py` - Episode Buffer Fix (NEW)
- Fix array shape validation
- Handle corrupted buffer gracefully

### 4. Recovery Script Usage
- Trade recovery script already created
- Can recover missing trades from CLOB API

## Verification Plan (Revised)

### Step 1: Clear Corrupted Data
```bash
mv data/ml_episodes.json data/ml_episodes.json.corrupted
```

### Step 2: Restart Bot
```bash
pkill -f "python.*bot.py"
python run_bot.py
```

**Look for** in startup logs:
```
============================================================
    BOT MODE: REAL (Live Trading)
    Trades save to: data/trade_history.json
    Real Balance: $XX.XX USDC
============================================================
```

### Step 3: Wait for Next Round (15 minutes)

**Look for** in settlement logs:
```
[REAL] [SETTLEMENT] Starting settlement for N bets
[REAL] [SETTLEMENT] Processing bet: BTC UP
[REAL] Taking REAL MODE settlement path
[REAL] Saving trade to history: BTC UP - WON
[SETTLEMENT] Trade saved successfully
```

**Should NOT see**:
- "Settlement error: setting an array element..."
- Immediate jump to next round

### Step 4: Verify Trade Saved
```bash
cat data/trade_history.json | jq '.[-1]'
# Should show latest trade
```

### Step 5: Run Recovery Script
```bash
python -m src.utils.recover_trades 3
```

## Summary

### What We Thought
- Bot detecting wrong mode
- Mode flag incorrectly set

### What's Actually Happening
- Settlement is FAILING due to ML episode buffer corruption
- Trades not being saved because settlement exits early on exception
- No mode detection issue - bot IS in real mode

### What We Fixed
✅ Enhanced logging to see what's happening
✅ Created recovery script for missing trades
✅ Created verification script for diagnostics

### What Still Needs Fixing
❌ ML episode buffer corruption
❌ Settlement error handling (continue on ML failure)
❌ Buffer validation in learning engine

## Next Steps

1. **Immediate**: Clear corrupted episode buffer and restart
2. **Short-term**: Add try-catch in settlement to prevent ML errors from blocking trade saving
3. **Long-term**: Fix episode buffer validation in learning engine
4. **Recovery**: Run trade recovery script to get past 3 days of trades

The enhanced logging we added will help diagnose any future issues immediately.
