# Time-Decay Mode: Logging & ML Display Enhancements

**Dedicated logging file + ML stats tailored for Time-Decay Sniper mode**

---

## What Was Implemented

✅ **Separate log file for Time-Decay mode** (`time_decay.log`)
✅ **Dashboard ML section shows Time-Decay calibrator stats** (not general ML)
✅ **Training progress tracker** (shows runs count, accuracy percentage)
✅ **Feature list output** (all 10 features displayed on first training)
✅ **Enhanced rejection logging** (clear reasons why opportunities rejected)

---

## 1. Dedicated Log File

### File: `time_decay.log`

**Location**: Root directory (same level as `bot.log`)

**What Gets Logged**:
- ✅ Opportunity detection (when 60-90¢ tokens with 15%+ edge found)
- ✅ Rejection reasons (why opportunities skipped)
- ✅ ML calibration adjustments (BS edge → Calibrated edge)
- ✅ Combined scoring (TD + ML = final score)
- ✅ Order placement (when trades executed)
- ✅ Trade results (win/loss after settlement)
- ✅ Training events (when ML model trains, accuracy %, features)

**What DOESN'T Get Logged**:
- General bot operations (those go to `bot.log`)
- Standard ML training (goes to `bot.log`)
- Other trading modes (Arbitrage, Standard ML)

### Example Log Output

```log
2026-02-04 14:23:15 [INFO] [OPPORTUNITY] BTC: ✓ Time: 285s | Price: 72¢ | Edge: 26.9% | Move: 0.76% from strike
2026-02-04 14:23:16 [INFO] [CALIBRATION] BTC: BS 26.9% → ML 16.2% (adj: 0.89x, conf: 0.82)
2026-02-04 14:23:16 [INFO] [SCORE] BTC: TD Edge 16.2% + ML 60.0% = Combined 0.250
2026-02-04 14:23:17 [INFO]
============================================================
[ORDER] [REAL] Placing: BTC UP $1.50
  Price: 72¢ | TD Edge: 16.2% | ML: 60.0%
  Combined Score: 0.250
============================================================

2026-02-04 14:38:45 [INFO] [TRADE #23] BTC @ 72¢ | BS Edge: 16.2% | ✓ WON
2026-02-04 14:38:45 [INFO]   Progress to ML training: 23/50 (27 more trades needed)
```

### When Training Happens (50 trades)

```log
2026-02-04 15:42:10 [INFO] [TRADE #50] ETH @ 75¢ | BS Edge: 18.5% | ✓ WON
2026-02-04 15:42:10 [INFO]
======================================================================
THRESHOLD REACHED: 50 trades collected - Starting ML training!
======================================================================

2026-02-04 15:42:12 [INFO] ======================================================================
2026-02-04 15:42:12 [INFO] ✓ TIME-DECAY ML TRAINING COMPLETE (Run #1)
2026-02-04 15:42:12 [INFO] ======================================================================
2026-02-04 15:42:12 [INFO]   Training Samples:    50 trades
2026-02-04 15:42:12 [INFO]   Accuracy:            84.0% ± 6.2%
2026-02-04 15:42:12 [INFO]   Win Rate (data):     78.0%
2026-02-04 15:42:12 [INFO]
2026-02-04 15:42:12 [INFO]   Top 5 Predictive Features:
2026-02-04 15:42:12 [INFO]     1. bs_edge                     34.2%
2026-02-04 15:42:12 [INFO]     2. regime_crisis               19.8%
2026-02-04 15:42:12 [INFO]     3. time_remaining_norm         15.4%
2026-02-04 15:42:12 [INFO]     4. vol_ratio                   12.1%
2026-02-04 15:42:12 [INFO]     5. orderbook_imbalance          8.7%
2026-02-04 15:42:12 [INFO]
2026-02-04 15:42:12 [INFO]   All Features Used by ML Model:
2026-02-04 15:42:12 [INFO]      1. bs_edge                      34.2% - Black-Scholes edge magnitude (fair_value - market_price)
2026-02-04 15:42:12 [INFO]      2. token_price                   3.1% - Token price bought (60-90¢ range)
2026-02-04 15:42:12 [INFO]      3. time_remaining_norm          15.4% - Time to expiry normalized (0-1, where 1=300s)
2026-02-04 15:42:12 [INFO]      4. price_distance_pct            4.8% - Distance from strike price (% move)
2026-02-04 15:42:12 [INFO]      5. regime_bull                   2.3% - Binary flag: 1 if BULL regime, 0 otherwise
2026-02-04 15:42:12 [INFO]      6. regime_bear                   3.9% - Binary flag: 1 if BEAR regime, 0 otherwise
2026-02-04 15:42:12 [INFO]      7. regime_crisis                19.8% - Binary flag: 1 if CRISIS regime, 0 otherwise
2026-02-04 15:42:12 [INFO]      8. vol_ratio                    12.1% - Realized volatility / Assumed volatility ratio
2026-02-04 15:42:12 [INFO]      9. orderbook_imbalance           8.7% - Order flow imbalance (-1=sell pressure, +1=buy pressure)
2026-02-04 15:42:12 [INFO]     10. bs_confidence                 5.7% - How extreme BS prediction is (distance from 50%)
2026-02-04 15:42:12 [INFO] ======================================================================
```

### Rejection Examples

```log
2026-02-04 14:28:30 [WARNING] [REJECT] BTC: Price too low (need ≥60¢, have 1¢)
2026-02-04 14:28:30 [WARNING] [REJECT] ETH: Price too low (need ≥60¢, have 3¢)
2026-02-04 14:28:30 [WARNING] [REJECT] SOL: Edge too small (need ≥15%, have 7.4%)
2026-02-04 14:28:30 [WARNING]
============================================================
NO OPPORTUNITIES FOUND THIS ROUND
============================================================
Rejection summary:
Waiting for 60-90¢ tokens with 15%+ Black-Scholes edge...
============================================================
```

---

## 2. Dashboard ML Stats (Time-Decay Specific)

### When in Time-Decay Mode

**Before Training (< 50 trades)**:
```
┌─ TIME-DECAY ML CALIBRATOR ──────────────────────────────┐
│                                                          │
│ Calibration Trades:                                      │
│   23 trades                                              │
│   [███████░░░░░░░░] 46%                                 │
│   23/50 to train                                         │
│   Status: COLLECTING DATA                                │
│                                                          │
│ PERFORMANCE:                                             │
│                                                          │
│   Win Rate: 78.3%                                        │
│   Avg BS Edge: 19.2%                                     │
└──────────────────────────────────────────────────────────┘
```

**After Training (≥ 50 trades)**:
```
┌─ TIME-DECAY ML CALIBRATOR ──────────────────────────────┐
│                                                          │
│ Calibration Trades:                                      │
│   127 trades                                             │
│   Status: TRAINED ✓                                      │
│                                                          │
│   Training Runs: 8                                       │
│   Last Accuracy: 84.0%                                   │
│                                                          │
│ PERFORMANCE:                                             │
│                                                          │
│   Win Rate: 83.5%                                        │
│   Avg BS Edge: 22.3%                                     │
│   BS Overconfidence: +9.3% (BS too optimistic)           │
└──────────────────────────────────────────────────────────┘
```

### Interpretation

**Training Runs**: How many times ML model has retrained
- First training at 50 trades
- Retrains every 10 trades after (60, 70, 80, ...)

**Last Accuracy**: Cross-validation accuracy from most recent training
- **Green (≥80%)**: Excellent - model is highly predictive
- **Yellow (70-79%)**: Good - model has signal
- **Red (<70%)**: Weak - model struggling to find patterns

**Win Rate**: Actual outcomes in collected data
- **Green (≥75%)**: Time-Decay strategy working well
- **Yellow (65-74%)**: Marginal profitability
- **Red (<65%)**: Below expected, may need adjustments

**BS Overconfidence**: How much Black-Scholes overestimates
- **Positive (>+5%)**: BS predicts higher than actual (ML reduces estimates)
- **Neutral (-5% to +5%)**: BS well-calibrated
- **Negative (<-5%)**: BS predicts lower than actual (rare)

---

## 3. Feature List Output

### All 10 Features Used by ML Calibrator

When ML trains for the first time, it outputs the complete feature list with descriptions and importance percentages:

```
All Features Used by ML Model:
  1. bs_edge                      34.2% - Black-Scholes edge magnitude (fair_value - market_price)
  2. token_price                   3.1% - Token price bought (60-90¢ range)
  3. time_remaining_norm          15.4% - Time to expiry normalized (0-1, where 1=300s)
  4. price_distance_pct            4.8% - Distance from strike price (% move)
  5. regime_bull                   2.3% - Binary flag: 1 if BULL regime, 0 otherwise
  6. regime_bear                   3.9% - Binary flag: 1 if BEAR regime, 0 otherwise
  7. regime_crisis                19.8% - Binary flag: 1 if CRISIS regime, 0 otherwise
  8. vol_ratio                    12.1% - Realized volatility / Assumed volatility ratio
  9. orderbook_imbalance           8.7% - Order flow imbalance (-1=sell pressure, +1=buy pressure)
 10. bs_confidence                 5.7% - How extreme BS prediction is (distance from 50%)
```

### Feature Importance Interpretation

**High Importance (>15%)**:
- These features are the primary drivers of calibration
- Example: `bs_edge` at 34.2% means it's the most predictive single feature

**Medium Importance (5-15%)**:
- These features add meaningful signal
- Example: `time_remaining_norm` at 15.4% - shorter time = higher certainty

**Low Importance (<5%)**:
- These features contribute marginally
- May be candidates for removal if overfitting occurs

**Combined Totals = 100%**: All feature importances sum to 100%

---

## 4. Training Progress Display

### Progress Tracking

Every trade added shows progress toward training threshold:

```log
[TRADE #23] BTC @ 72¢ | BS Edge: 16.2% | ✓ WON
  Progress to ML training: 23/50 (27 more trades needed)
```

**At 50 trades**: Automatic training trigger
```log
THRESHOLD REACHED: 50 trades collected - Starting ML training!
```

**Every 10 trades after**: Retraining
```log
[RETRAIN] 60 trades reached - Retraining ML model...
```

### Accuracy Tracking

Each training run shows:
- **Samples used**: Total trades in training set
- **Accuracy %**: Cross-validation accuracy (5-fold)
- **Win Rate**: Actual win rate in data
- **Feature rankings**: Top predictive features

---

## 5. How to Use

### View Time-Decay Log in Real-Time

```bash
# Follow Time-Decay log (separate from main bot log)
tail -f time_decay.log

# Or filter for specific events
grep "OPPORTUNITY" time_decay.log
grep "CALIBRATION" time_decay.log
grep "TRAINING" time_decay.log
grep "WON\|LOST" time_decay.log
```

### Monitor Training Progress

```bash
# Check how many trades collected
grep "Progress to ML training" time_decay.log | tail -1

# Check if trained
grep "TRAINING COMPLETE" time_decay.log

# View accuracy history
grep "Accuracy:" time_decay.log
```

### Analyze Performance

```bash
# Win rate
grep "WON\|LOST" time_decay.log | tail -50 | grep -c "WON"

# Average edges
grep "BS Edge:" time_decay.log | awk '{print $9}' | sed 's/%//' | awk '{sum+=$1} END {print sum/NR}'

# Calibration adjustments
grep "CALIBRATION.*→" time_decay.log | tail -20
```

---

## 6. Dashboard Comparison

### Standard ML Mode (Modes A, B, C)

Shows per-coin training status:
```
ML TRAINING STATUS

Labeled Samples:
  127 samples
  Status: TRAINING ACTIVE ✓

Pending: 89 obs

MODEL STATUS:

BTC: ✓ 52.3% acc [MED]
  89 pending obs

ETH: ✓ 54.1% acc [MED]
  89 pending obs

SOL: ✗ NOT TRAINED
  Need 0 more | 89 pending
```

### Time-Decay Mode (Mode D)

Shows calibrator-specific stats:
```
TIME-DECAY ML CALIBRATOR

Calibration Trades:
  127 trades
  Status: TRAINED ✓

  Training Runs: 8
  Last Accuracy: 84.0%

PERFORMANCE:

  Win Rate: 83.5%
  Avg BS Edge: 22.3%
  BS Overconfidence: +9.3% (BS too optimistic)
```

**Key Differences**:
- Time-Decay shows **calibrator stats** (not per-coin models)
- Focuses on **edge accuracy** rather than directional prediction
- Shows **BS overconfidence** (unique to TD mode)
- Displays **training runs** (retraining frequency)

---

## 7. File Summary

### Modified Files

1. **`src/bot.py`**:
   - Added `td_logger` (dedicated Time-Decay logger)
   - Updated dashboard ML stats (shows calibrator stats in TD mode)
   - Added TD-specific logging throughout

2. **`src/ml/time_decay_calibrator.py`**:
   - Added training progress logging
   - Enhanced training output (accuracy %, feature list)
   - Added feature descriptions
   - Added trade-by-trade logging

### New Log Files

- **`time_decay.log`**: All Time-Decay mode activity
- **`bot.log`**: Standard bot operations (unchanged)
- **`bot_trace.log`**: Debug trace (unchanged)

---

## 8. Benefits

### For Debugging
- ✅ Separate log file = easier to diagnose Time-Decay issues
- ✅ Clear rejection reasons = understand why opportunities skipped
- ✅ Calibration tracking = see how ML adjusts BS predictions

### For Analysis
- ✅ Feature importance = know what drives ML decisions
- ✅ Accuracy tracking = monitor ML performance over time
- ✅ Win rate history = verify strategy profitability

### For Monitoring
- ✅ Progress bars = see training progress in dashboard
- ✅ Real-time stats = know exactly when ML becomes active
- ✅ Overconfidence metric = understand BS vs reality gap

---

## 9. Example Full Session Log

```log
# Bot starts in Time-Decay mode
2026-02-04 14:20:00 [INFO] Time-Decay Calibrator initialized (22 trades, 0 training runs)

# Round starts, looks for opportunities
2026-02-04 14:23:15 [WARNING] [REJECT] BTC: Price too low (need ≥60¢, have 1¢)
2026-02-04 14:23:15 [WARNING] [REJECT] ETH: Price too low (need ≥60¢, have 3¢)
2026-02-04 14:23:15 [INFO] [OPPORTUNITY] SOL: ✓ Time: 285s | Price: 75¢ | Edge: 19.2% | Move: 1.2% from strike

# ML calibration happens (if trained)
2026-02-04 14:23:16 [INFO] [CALIBRATION] SOL: BS 19.2% → ML 14.8% (adj: 0.92x, conf: 0.75)

# Combined scoring
2026-02-04 14:23:16 [INFO] [SCORE] SOL: TD Edge 14.8% + ML 55.0% = Combined 0.228

# Order placed
2026-02-04 14:23:17 [INFO]
============================================================
[ORDER] [REAL] Placing: SOL UP $1.50
  Price: 75¢ | TD Edge: 14.8% | ML: 55.0%
  Combined Score: 0.228
============================================================

# Market settles
2026-02-04 14:38:30 [INFO] [TRADE #23] SOL @ 75¢ | BS Edge: 14.8% | ✓ WON
2026-02-04 14:38:30 [INFO]   Progress to ML training: 23/50 (27 more trades needed)

# ... 27 more trades later ...

# Training triggered at 50 trades
2026-02-04 16:15:42 [INFO] [TRADE #50] BTC @ 72¢ | BS Edge: 16.2% | ✓ WON
2026-02-04 16:15:42 [INFO]
======================================================================
THRESHOLD REACHED: 50 trades collected - Starting ML training!
======================================================================

2026-02-04 16:15:44 [INFO] ======================================================================
2026-02-04 16:15:44 [INFO] ✓ TIME-DECAY ML TRAINING COMPLETE (Run #1)
2026-02-04 16:15:44 [INFO] ======================================================================
2026-02-04 16:15:44 [INFO]   Training Samples:    50 trades
2026-02-04 16:15:44 [INFO]   Accuracy:            82.0% ± 7.1%
2026-02-04 16:15:44 [INFO]   Win Rate (data):     76.0%
2026-02-04 16:15:44 [INFO]
2026-02-04 16:15:44 [INFO]   Top 5 Predictive Features:
2026-02-04 16:15:44 [INFO]     1. bs_edge                     36.8%
2026-02-04 16:15:44 [INFO]     2. regime_crisis               22.1%
2026-02-04 16:15:44 [INFO]     3. time_remaining_norm         14.2%
2026-02-04 16:15:44 [INFO]     4. vol_ratio                   11.5%
2026-02-04 16:15:44 [INFO]     5. orderbook_imbalance          7.9%
2026-02-04 16:15:44 [INFO]
2026-02-04 16:15:44 [INFO]   All Features Used by ML Model:
[... complete feature list with descriptions ...]
2026-02-04 16:15:44 [INFO] ======================================================================

# From now on, calibration is active and adjusts all edges
```

---

**Everything Time-Decay related is now in one place: `time_decay.log`!** 🎯
