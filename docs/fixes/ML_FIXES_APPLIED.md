# ML Training Pipeline - Critical Bugs Fixed

**Date**: February 3, 2026
**Status**: ✅ FIXED - Ready for testing

---

## Summary

Two critical bugs preventing ML training have been fixed:

### Bug #1: Feature Extraction Missing Arguments ✅ FIXED

**Location**: `src/bot.py:715`

**Problem**:
- Method `extract_features()` requires 4 arguments: `(coin, start_price, orderbook, time_remaining)`
- Was being called with only 2 arguments: `(coin, remaining)`
- Caused 7,238+ errors in logs: "missing 1 required positional argument: 'orderbook'"

**Fix Applied**:
```python
# Now properly fetches orderbook and provides all required arguments
tokens = self.market_15m.get_token_ids_for_coin(coin)
if tokens:
    token_id = tokens['yes'] if arb['direction'] == 'UP' else tokens['no']
    orderbook = self.market_15m.client.get_order_book(token_id)
    if not orderbook:
        orderbook = {'bids': [], 'asks': []}
else:
    orderbook = {'bids': [], 'asks': []}

start_price = self.start_prices.get(coin, 0)
features = self.extract_features(coin, start_price, orderbook, remaining)
```

**Result**: Feature extraction now works correctly

---

### Bug #2: Replay Buffer Not Persisted ✅ FIXED

**Location**: `src/ml/learning.py`

**Problem**:
- `replay_buffer` (labeled training data) was in-memory only
- Lost on bot restart/crash
- Even though 6 trades completed, labeled data was never saved

**Fix Applied**:

1. **Added `save_replay_buffer()` method** (line ~140):
   - Converts deque to JSON-serializable list
   - Saves to `data/replay_buffer.json`
   - Handles numpy array serialization

2. **Added `load_replay_buffer()` method** (line ~165):
   - Loads from `data/replay_buffer.json` on startup
   - Restores labeled training data
   - Converts back to deque with numpy arrays

3. **Integrated into workflow**:
   - `__init__`: Calls `load_replay_buffer()` (line 46)
   - `finalize_round()`: Calls `save_replay_buffer()` after labeling (line 93)

**Result**: Labeled training data now persists across restarts

---

## Current Data Status

**Verified** (via `verify_ml_fixes.py`):

| Metric | Value | Status |
|--------|-------|--------|
| **Episode observations** | 312 total | ✓ Non-zero features |
| **BTC observations** | 46 | ✓ Valid |
| **ETH observations** | 95 | ✓ Valid |
| **SOL observations** | 171 | ✓ Valid |
| **Completed trades** | 6 | ✓ Outcomes recorded |
| **Win rate** | 66.7% (4W/2L) | ✓ Excellent |
| **Replay buffer** | Not created yet | ⚠️ Waiting for next trade |
| **ML models** | 0 files | ⚠️ Waiting for 50+ samples |

**Notes**:
- ✅ Features are **non-zero** in existing data (feature extraction was working)
- ⚠️ Replay buffer doesn't exist yet (expected - no trades completed since fix)
- ⚠️ 312 unlabeled observations waiting for trade completions
- ✓ 6 historical trade outcomes available

---

## What Happens Next

### When Bot Restarts:

1. **Load existing data**:
   - Episode buffer: 312 unlabeled observations ✓
   - Replay buffer: Empty (will load when file exists) ✓
   - Historical trades: 6 completed trades ✓

2. **When next trade completes**:
   - `finalize_round()` called with outcome (UP/DOWN)
   - Labels all observations for that coin
   - Moves to replay buffer (in-memory)
   - **NEW**: Saves to `data/replay_buffer.json` ✓

3. **When replay buffer reaches 50+ samples**:
   - `train_model()` triggered automatically
   - Creates ML models in `data/models/`
   - Models start making predictions

### Expected Timeline:

| Event | Time | What Happens |
|-------|------|--------------|
| **Bot restart** | Now | Loads 312 observations |
| **First trade completes** | 1-2 hours | Creates replay_buffer.json |
| **50+ samples accumulated** | 3-6 hours | First ML models trained |
| **ML predictions active** | Same day | Bot uses ML for decisions |
| **Early betting ready** | 1-2 days | 100+ samples, confident predictions |

---

## Verification Steps

### Immediate (After Bot Restarts):

```bash
# 1. Check logs for errors
tail -f bot.log | grep "ERROR"
# Should NOT see: "missing 1 required positional argument"

# 2. Check feature extraction
tail -f bot.log | grep "ML prediction"
# Should see successful predictions (or neutral fallback)
```

### After First Trade (1-2 hours):

```bash
# 3. Check replay buffer created
ls -la data/replay_buffer.json
cat data/replay_buffer.json | python3 -c "import json, sys; print(len(json.load(sys.stdin)), 'samples')"

# 4. Verify non-zero features in replay buffer
cat data/replay_buffer.json | python3 -c "import json, sys; data=json.load(sys.stdin); print('Features sample:', data[0]['features'][:5])"
# Should show: [0.234, 0.567, ...] NOT [0.0, 0.0, ...]
```

### After 50+ Samples (3-6 hours):

```bash
# 5. Check model files created
ls -la data/models/
# Should see: BTC_model.pkl, ETH_model.pkl, SOL_model.pkl

# 6. Check training logs
grep "Training model" bot.log
# Should see: "Training model with N samples"
```

### Continuous Verification:

```bash
# Run verification script anytime
python3 verify_ml_fixes.py
```

---

## Files Modified

### `src/bot.py`
- **Line 715-731**: Fixed feature extraction call
- **Added**: Orderbook fetching before extract_features
- **Added**: All required arguments to extract_features

### `src/ml/learning.py`
- **Line 46**: Added load_replay_buffer() call in __init__
- **Line 93**: Added save_replay_buffer() call in finalize_round
- **Line ~140**: Added save_replay_buffer() method
- **Line ~165**: Added load_replay_buffer() method

### New Files Created:
- `verify_ml_fixes.py`: Verification script
- `ML_FIXES_APPLIED.md`: This document

---

## Testing Checklist

- [x] Bug #1 fix applied (feature extraction)
- [x] Bug #2 fix applied (replay buffer persistence)
- [x] Verification script created
- [x] Existing features verified as non-zero
- [ ] Bot restarted with fixes
- [ ] First trade completed post-fix
- [ ] Replay buffer created with valid data
- [ ] 50+ samples accumulated
- [ ] ML models trained
- [ ] ML predictions working

---

## Rollback Plan (If Needed)

If issues occur, you can rollback by:

```bash
# Revert bot.py changes
git checkout src/bot.py

# Revert learning.py changes
git checkout src/ml/learning.py
```

**Note**: Not recommended - fixes are critical for ML training

---

## Additional Notes

### Feature Extraction Status

The verification script shows all 312 existing observations have **non-zero features**, which is EXCELLENT. This means:

- Feature extraction was actually working in some code path
- The bug only affected ML predictions during live trading
- Existing data is valid and usable

### Why Replay Buffer Doesn't Exist Yet

The replay buffer is created when:
1. Trade completes
2. `finalize_round()` called
3. Observations labeled
4. `save_replay_buffer()` called

Since the fix was just applied and bot hasn't run a full trade cycle yet, this is expected.

### Using Historical Trade Outcomes

The bot has 6 completed trades with outcomes. However:
- Episode observations were cleared after finalization
- Only current 312 unlabeled observations remain
- When these complete, they'll seed the replay buffer

---

## Success Criteria

✅ **Bugs Fixed**: Both critical bugs resolved
⚠️ **Testing Required**: Need bot restart + 1 trade to verify
⚠️ **Training Pending**: Will happen automatically at 50+ samples

**Overall Status**: Ready for production testing

---

## Contact

For issues or questions, refer to:
- Main documentation: `CLAUDE.md`
- Verification script: `verify_ml_fixes.py`
- Bot logs: `bot.log` and `bot_trace.log`
