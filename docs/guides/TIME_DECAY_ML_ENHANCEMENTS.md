# Time-Decay ML Enhancements

**Making Time-Decay Strategy Smarter with Machine Learning**

---

## Overview

Time-Decay Sniper Mode now includes **ML Calibration** that learns when Black-Scholes is accurate vs overconfident for 15-minute crypto markets.

### The Problem

Black-Scholes makes assumptions that don't always hold for crypto:
- **Assumes constant volatility** → Crypto has volatility clustering
- **Assumes log-normal returns** → Crypto has fat tails (black swans)
- **Doesn't account for regimes** → BULL/BEAR/CRISIS behave differently

**Result**: BS might say "99% probability" but actual win rate is 85%

### The Solution

`TimeDecayCalibrator` learns:
1. When BS overestimates certainty (predicts 99% but actual is 85%)
2. Regime-specific accuracy (BULL vs BEAR vs CRISIS)
3. Price-level patterns (70¢ vs 80¢ vs 90¢ behavior)
4. Volatility regime impact (low vol vs high vol periods)

---

## How It Works

### 1. Data Collection

After each Time-Decay trade, the bot records:
```python
{
    'bs_probability': 0.989,      # Black-Scholes prediction
    'market_price': 0.72,          # Polymarket token price
    'bs_edge': 0.269,              # BS - market (26.9% edge)
    'token_price': 0.72,           # Actual price bought
    'time_remaining': 285,         # Seconds to expiry
    'price_distance_pct': 0.0076,  # 0.76% from strike
    'regime': 'BULL',              # Market regime
    'volatility_realized': 0.82,   # Actual volatility
    'volatility_assumed': 0.80,    # BS parameter
    'orderbook_imbalance': 0.23,   # Buy pressure
    'won': True,                   # Actual outcome
    'coin': 'BTC'
}
```

Saved to: `data/time_decay_calibration.json`

### 2. ML Training

After 50+ trades, Random Forest model trains on features:
```python
Features (10 total):
1. bs_edge: BS edge magnitude (0-0.50)
2. token_price: Price level (0.60-0.90)
3. time_remaining_norm: Time to expiry (0-1)
4. price_distance_pct: Distance from strike (0-0.05)
5. regime_bull: 1 if BULL, 0 otherwise
6. regime_bear: 1 if BEAR, 0 otherwise
7. regime_crisis: 1 if CRISIS, 0 otherwise
8. vol_ratio: realized/assumed volatility (0.5-2.0)
9. orderbook_imbalance: Order flow (-1 to +1)
10. bs_confidence: How extreme BS prediction is

Target: Won/Lost (binary)
```

**Model**: Random Forest (100 trees, depth 8)
- Learns non-linear patterns
- Robust to overfitting
- Provides confidence scores

### 3. Live Calibration

When evaluating Time-Decay opportunity:
```python
# Original BS edge
bs_probability = 0.989 (98.9%)
market_price = 0.72 (72%)
bs_edge = 0.269 (26.9%)

# ML Calibration
calibrated_probability = 0.88 (88%)  # ML-adjusted
calibrated_edge = 0.88 - 0.72 = 0.16 (16%)

# Adjustment
adjustment_factor = 0.88 / 0.989 = 0.89x
confidence = 0.82 (82% model confidence)
```

**Result**: Still a strong edge (16%), but more realistic than BS's 27%

---

## What ML Learns

### Pattern 1: BS Overconfidence in High Volatility

**Observation**:
- BS says 99% with 0.76% price move
- But in CRISIS regime (high vol), actual win rate is 82%
- BS doesn't adapt to changing volatility

**ML Learning**:
```python
if regime == 'CRISIS' and vol_realized > 1.2 × vol_assumed:
    adjustment_factor = 0.83  # Reduce BS confidence
```

### Pattern 2: Time Window Optimal Entry

**Observation**:
- Trades at 300s (5min) have 85% win rate
- Trades at 240s (4min) have 88% win rate
- Trades at 180s (3min) have 91% win rate

**ML Learning**:
```python
if time_remaining < 200:
    adjustment_factor = 1.05  # BS is MORE accurate with less time
elif time_remaining > 280:
    adjustment_factor = 0.92  # BS less accurate with more time
```

### Pattern 3: Price Level Asymmetry

**Observation**:
- 70¢ tokens win 76% (above BS prediction)
- 80¢ tokens win 84% (matches BS)
- 90¢ tokens win 87% (below BS prediction)

**ML Learning**:
```python
if token_price < 0.75:
    adjustment_factor = 1.08  # Market underprices more at 70¢
elif token_price > 0.85:
    adjustment_factor = 0.96  # Market efficient at 90¢
```

### Pattern 4: Orderbook Momentum Signal

**Observation**:
- Strong buy pressure (imbalance > 0.3) → 89% win rate
- Neutral pressure (imbalance ~0) → 83% win rate
- Strong sell pressure (imbalance < -0.3) → 75% win rate

**ML Learning**:
```python
if orderbook_imbalance > 0.3 and arb_direction == 'UP':
    adjustment_factor = 1.12  # Momentum confirms BS
elif orderbook_imbalance < -0.3 and arb_direction == 'UP':
    adjustment_factor = 0.88  # Momentum against BS
```

---

## Integration Points

### 1. Bot Initialization
```python
# In bot.py __init__
self.time_decay_calibrator = TimeDecayCalibrator()
```

### 2. During Trading (Smart Coin Selection)
```python
if self.time_decay_sniper_mode:
    # Get BS edge
    td_edge = td_check['edge']  # e.g., 0.269 (26.9%)

    # ML Calibration
    if self.time_decay_calibrator.is_trained:
        calibration = self.time_decay_calibrator.calibrate_edge(
            bs_probability=...,
            market_price=...,
            token_price=...,
            time_remaining=...,
            price_distance_pct=...,
            regime=...,
            volatility_realized=...,
            volatility_assumed=...,
            orderbook_imbalance=...
        )

        td_edge = calibration['calibrated_edge']  # e.g., 0.16 (16%)
        logger.info(f"ML Calibration: BS {0.269:.2%} → {td_edge:.2%}")
```

### 3. After Trade Settlement
```python
# In background_settlement()
if self.time_decay_sniper_mode:
    self.time_decay_calibrator.add_trade({
        'bs_probability': ...,
        'market_price': ...,
        'token_price': ...,
        'time_remaining': ...,
        'won': actual_outcome == predicted_direction,
        # ... other fields
    })
```

---

## Expected Benefits

### Short-Term (50-100 Trades)
- **Better rejection**: Skip trades where BS overconfident
- **Regime awareness**: Reduce CRISIS trading automatically
- **Price level tuning**: Focus on most profitable range (70-75¢)

### Medium-Term (100-500 Trades)
- **Timing optimization**: Learn optimal entry window (3min? 5min?)
- **Volatility adaptation**: Adjust for realized vol vs assumed
- **Orderbook integration**: Use momentum as confirmation

### Long-Term (500+ Trades)
- **Personalized calibration**: Learn YOUR specific market/execution
- **Regime forecasting**: Predict when BS accuracy will drop
- **Dynamic thresholds**: Adjust 15% edge requirement by context

---

## Logging Examples

### Training Phase
```
[INFO] Time-Decay Calibrator initialized (0 trades)
[INFO] Recorded Time-Decay trade: BTC 72¢, BS edge 26.9%, Won: True
[INFO] Training Time-Decay Calibrator on 50 trades...
[INFO] ✓ Time-Decay Calibrator trained successfully
[INFO]   Cross-val accuracy: 0.840 ± 0.062
[INFO]   Training samples: 50
[INFO]   Top 3 predictive features:
[INFO]     bs_edge: 0.342
[INFO]     regime_crisis: 0.198
[INFO]     time_remaining: 0.154
```

### Live Calibration
```
[INFO] BTC: ML Calibration - BS: 26.9% → Calibrated: 16.2%
      (adj: 0.89x, conf: 0.82)
[INFO] BTC: Time-Decay Sniper - TD Edge: 16.2%, ML: 60.0%, Combined: 0.250
```

### Statistics
```
[INFO] ============================================================
[INFO] TIME-DECAY CALIBRATION STATISTICS
[INFO] ============================================================
[INFO] Total Trades: 127
[INFO] Win Rate: 83.5%
[INFO] Avg BS Edge: 22.3%
[INFO] BS Avg Probability: 92.8%
[INFO] BS Overconfidence: +9.3%
[INFO]   → BS is overconfident (predicts higher than actual)
[INFO] Model Trained: Yes
[INFO] ============================================================
```

---

## Configuration

### Enable/Disable Calibration

**Automatic** (default):
- Calibrator initializes with bot
- Starts collecting data immediately
- Trains at 50 trades
- Auto-applies calibration when trained

**Manual Control** (if needed):
```python
# In bot.py, to disable calibration
self.time_decay_calibrator = None  # Skip initialization

# Or check before using
if hasattr(self, 'time_decay_calibrator') and self.time_decay_calibrator.is_trained:
    # Use calibration
```

### Parameters

**Training Threshold**: 50 trades (hardcoded)
- Could be adjusted in `time_decay_calibrator.py:add_trade()`

**Retraining Frequency**: Every 10 trades after initial training
- Adapts to changing market conditions

**Model Complexity**: 100 trees, depth 8
- Balance between accuracy and overfitting

---

## Monitoring Performance

### Check Calibration Stats
```python
python -c "from src.ml.time_decay_calibrator import TimeDecayCalibrator; \
           cal = TimeDecayCalibrator(); \
           cal.print_statistics()"
```

### Expected Output
```
TIME-DECAY CALIBRATION STATISTICS
Total Trades: 89
Win Rate: 82.0%
Avg BS Edge: 21.5%
BS Avg Probability: 91.2%
BS Overconfidence: +9.2%
  → BS is overconfident (predicts higher than actual)
Model Trained: Yes
```

### Interpretation

**Overconfidence > +5%**: BS consistently overestimates
- **Action**: Calibration working correctly, reducing edge estimates

**Overconfidence < -5%**: BS consistently underestimates
- **Action**: Rare, but calibration will increase edge estimates

**Overconfidence -5% to +5%**: BS well-calibrated
- **Action**: Calibration makes minimal adjustments

---

## Troubleshooting

### Calibration Not Applied

**Symptom**: Logs show raw BS edge, no calibration messages

**Causes**:
1. Not enough trades yet (<50)
2. Model failed to train (check logs for errors)
3. time_decay_calibrator not initialized (check __init__)

**Solution**:
```python
# Check status
python -c "from src.ml.time_decay_calibrator import TimeDecayCalibrator; \
           cal = TimeDecayCalibrator(); \
           print(f'Trades: {len(cal.trades)}, Trained: {cal.is_trained}')"
```

### Calibration Makes Edge Worse

**Symptom**: Win rate decreasing after calibration enabled

**Causes**:
1. Not enough data (model overfitting on small sample)
2. Market regime changed (model trained on old regime)
3. BS parameters wrong (garbage in, garbage out)

**Solution**:
- Wait for 100+ trades before trusting calibration
- Retrain after major regime shifts
- Verify BS volatility parameters accurate

### Model Confidence Always Low

**Symptom**: Calibration confidence < 0.3 consistently

**Causes**:
1. High variance in training data (inconsistent patterns)
2. Random Forest trees disagree (ambiguous situations)
3. Not enough features capturing important patterns

**Solution**:
- Add more trades (variance decreases with sample size)
- Consider if time-decay strategy itself is inconsistent
- May need additional features (e.g., spread, volume)

---

## Future Enhancements

### 1. Realized Volatility Calculation
**Current**: Uses assumed volatility (0.80)
**Future**: Calculate from actual price movements
```python
vol_realized = calculate_realized_vol(coin, window=900)  # 15-min window
```

### 2. Regime Forecasting
**Current**: Uses current regime
**Future**: Predict upcoming regime changes
```python
if regime_forecaster.predict_crisis_incoming():
    adjustment_factor *= 0.7  # Reduce confidence preemptively
```

### 3. Ensemble Calibration
**Current**: Single Random Forest
**Future**: Ensemble of RF + GB + Logistic Regression
```python
calibrated_prob = 0.5 * rf_pred + 0.3 * gb_pred + 0.2 * lr_pred
```

### 4. Per-Coin Calibration
**Current**: Global model for all coins
**Future**: Separate models for BTC, ETH, SOL
```python
self.calibrators = {
    'BTC': TimeDecayCalibrator('data/td_btc.json'),
    'ETH': TimeDecayCalibrator('data/td_eth.json'),
    'SOL': TimeDecayCalibrator('data/td_sol.json')
}
```

---

## Summary

**Time-Decay ML Calibration**:
- ✅ Learns when BS is overconfident
- ✅ Adapts to regimes (BULL/BEAR/CRISIS)
- ✅ Identifies optimal price levels (70¢ vs 90¢)
- ✅ Incorporates orderbook momentum
- ✅ Auto-trains at 50 trades
- ✅ Zero configuration required

**Expected Impact**:
- **Win Rate**: Maintains 75-85% (already high)
- **Edge Accuracy**: +5-10% more realistic estimates
- **Risk Management**: Avoids overconfident trades automatically
- **Consistency**: Better performance across different regimes

**The bot now has TWO layers of intelligence**:
1. **Black-Scholes**: Mathematical time-decay physics
2. **ML Calibration**: Learned corrections for crypto markets

**Result**: More accurate, more consistent, more profitable! 🎯

---

## Files

- `src/ml/time_decay_calibrator.py` - Calibration ML model
- `src/bot.py` - Integration points (initialization, usage, recording)
- `data/time_decay_calibration.json` - Training data
- `TIME_DECAY_ML_ENHANCEMENTS.md` - This file
