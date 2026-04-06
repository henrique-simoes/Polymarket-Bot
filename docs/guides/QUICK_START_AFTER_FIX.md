# Quick Start Guide - After ML Fixes

## TL;DR

Two critical bugs have been fixed. Follow these steps to get ML training working:

### 1. Restart the Bot

```bash
cd [PROJECT_ROOT]
python3 -m src.bot
```

Choose your trading mode (recommend: **C - Learning Mode** to collect data safely)

### 2. Let It Run

- **Minimum**: 1-2 hours (to complete 1 trade and verify fix)
- **Optimal**: 3-6 hours (to accumulate 50+ samples and train first models)
- **Best**: 1-2 days (to get 200+ samples for production-ready ML)

### 3. Monitor Progress

```bash
# Check if replay buffer is being created
ls -la data/replay_buffer.json

# Check observations count
python3 verify_ml_fixes.py

# Check logs for training
tail -f bot.log | grep "Training model"
```

### 4. Verify After First Trade

```bash
# Should show labeled samples
cat data/replay_buffer.json | python3 -c "import json, sys; print(len(json.load(sys.stdin)), 'samples')"

# Should show non-zero features
python3 verify_ml_fixes.py
```

### 5. Wait for Models

After 50+ samples in replay buffer:
- Models automatically train
- Check `data/models/` for `.pkl` files
- Bot starts using ML predictions

---

## What Was Fixed

### Bug #1: Feature Extraction
- **Was**: Calling `extract_features(coin, remaining)` - missing 2 arguments
- **Now**: Calling `extract_features(coin, start_price, orderbook, remaining)` - all arguments provided
- **Impact**: ML predictions now work (no more 7,238 errors)

### Bug #2: Replay Buffer Persistence
- **Was**: Labeled training data lost on restart
- **Now**: Saved to `data/replay_buffer.json` after each trade
- **Impact**: Training data accumulates across sessions

---

## Expected Results

### After 1 Trade (~1-2 hours):
- ✅ `replay_buffer.json` created
- ✅ ~75 labeled samples (1 trade worth)
- ✅ Features are non-zero
- ⚠️ Not enough samples to train yet

### After 50+ Samples (~3-6 hours):
- ✅ ML models trained (files in `data/models/`)
- ✅ Bot starts making ML predictions
- ✅ Combined arbitrage + ML strategy active
- ⚠️ Early predictions may be uncertain

### After 200+ Samples (~1-2 days):
- ✅ ML models well-trained
- ✅ High-confidence predictions
- ✅ Ready for live trading (if in learning mode)
- ✅ Can enable early betting

---

## Troubleshooting

### Issue: Bot still shows "missing argument" errors

**Fix**: Make sure you restarted the bot after applying fixes

```bash
# Kill any running bot instances
pkill -f "python.*src.bot"

# Start fresh
python3 -m src.bot
```

### Issue: Replay buffer not created after trade

**Check**: Did trade actually complete and settle?

```bash
# Check trade history
cat data/trade_history.json | python3 -c "import json, sys; print(len(json.load(sys.stdin)), 'trades')"

# Check logs
grep "finalize_round" bot.log
```

### Issue: Features still zero in replay buffer

**This shouldn't happen** - verification showed features are already non-zero. If it does:

```bash
# Check feature sample
cat data/replay_buffer.json | python3 -c "import json, sys; data=json.load(sys.stdin); print('Features:', data[0]['features'][:10])"

# Should show numbers like: [0.234, 0.567, -0.123, ...]
# NOT: [0.0, 0.0, 0.0, ...]
```

---

## Current Data Status

**Before fixes applied**:
- 312 observations collected (✓ good!)
- 6 trades completed (✓ good!)
- Features were non-zero (✓ excellent!)
- But: Replay buffer never created (❌ bug #2)
- And: ML predictions failing (❌ bug #1)

**After fixes applied**:
- Same 312 observations (unlabeled)
- When next trade completes: Replay buffer will be created
- ML predictions will work during trading
- Training will start at 50+ samples

---

## Next Steps

1. **Immediate**: Restart bot with fixes
2. **1-2 hours**: Verify replay buffer created
3. **3-6 hours**: Check for model files
4. **1-2 days**: Ready for live trading

**Then**: Bot will train continuously and improve over time!

---

## Questions?

- Read full details: `ML_FIXES_APPLIED.md`
- Run verification: `python3 verify_ml_fixes.py`
- Check main docs: `CLAUDE.md`
- View logs: `tail -f bot.log`

---

**Status**: Ready to start! 🚀
