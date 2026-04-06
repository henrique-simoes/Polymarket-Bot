# VWAP Integration for Time-Decay Strategy

**Experimental feature**: Let ML decide if VWAP is useful

---

## What Was Added

✅ **VWAP Calculator** (`src/utils/vwap.py`)
- Calculates Volume-Weighted Average Price over 15-minute rolling window
- Maintains price/volume history for BTC, ETH, SOL
- Provides VWAP-based features for ML

✅ **3 New ML Features** (added to Time-Decay Calibrator)
1. `vwap_deviation_pct`: Distance from VWAP as percentage
2. `price_above_vwap`: Binary flag (1 if above, 0 if below)
3. `vwap_trend`: VWAP slope (5min vs 10min)

✅ **Automatic Integration**
- Initializes when Time-Decay mode selected
- Feeds price ticks every second
- Calculates VWAP features during calibration
- Logs VWAP values to `time_decay.log`

**Total ML Features**: 10 → 13 (VWAP adds 3)

---

## How VWAP is Calculated

```python
# Volume-Weighted Average Price
VWAP = Σ(Price × Volume) / Σ(Volume)

# Example:
# Trade 1: $79,000 × 100 volume = 7,900,000
# Trade 2: $79,200 × 50 volume  = 3,960,000
# Trade 3: $78,800 × 150 volume = 11,820,000
# -----------------------------------------
# Total: 23,680,000 / 300 volume = $78,933 VWAP
```

**For This Bot**:
- Uses **15-minute rolling window** (matches market duration)
- **Volume = 1.0 per tick** (no real-time volume from Binance spot)
- Effectively becomes time-weighted average price (TWAP) due to uniform volume
- Still useful for noise reduction and trend identification

---

## New Features Explained

### 1. vwap_deviation_pct

**What It Measures**: How far current price is from VWAP

```python
deviation = (current_price - vwap) / vwap

# Example:
# Current: $79,200
# VWAP: $79,000
# Deviation: +0.0025 (+0.25%)
```

**ML Can Learn**:
- Extreme deviations (>2%) might mean reversal coming
- Small deviations (<0.5%) suggest fair pricing
- Direction matters (above vs below)

### 2. price_above_vwap

**What It Measures**: Binary flag for position relative to VWAP

```python
above_vwap = 1.0 if current_price > vwap else 0.0
```

**ML Can Learn**:
- Institutional behavior (buy below VWAP, sell above)
- Support/resistance at VWAP level
- Momentum confirmation (trending above/below)

### 3. vwap_trend

**What It Measures**: VWAP slope (is it trending up/down?)

```python
vwap_5min = calculate_vwap(300s window)
vwap_10min = calculate_vwap(600s window)
trend = (vwap_5min - vwap_10min) / vwap_10min

# Example:
# 5min VWAP: $79,100
# 10min VWAP: $79,000
# Trend: +0.0013 (+0.13% upward slope)
```

**ML Can Learn**:
- VWAP rising = bullish institutional flow
- VWAP falling = bearish institutional flow
- Flat VWAP = choppy/sideways market

---

## Log Output Examples

### Initialization
```log
2026-02-04 14:20:00 [INFO] VWAP calculator initialized (15-minute rolling window)
```

### During Trading (Debug Level)
```log
2026-02-04 14:23:15 [DEBUG] [VWAP] BTC: VWAP=$79,000.00, Dev=+0.25%, Above=1
2026-02-04 14:23:15 [DEBUG] [VWAP] ETH: VWAP=$2,276.50, Dev=-0.18%, Above=0
2026-02-04 14:23:15 [DEBUG] [VWAP] SOL: VWAP=$97.65, Dev=+0.10%, Above=1
```

### First Training (Feature List)
```log
All Features Used by ML Model:
  ...
  11. vwap_deviation_pct          X.X% - VWAP: Price deviation from volume-weighted average (%)
  12. price_above_vwap            X.X% - VWAP: Binary flag - 1 if price above VWAP, 0 if below
  13. vwap_trend                  X.X% - VWAP: Trend direction (5min vs 10min VWAP slope)
```

### Feature Importance After Training

**Scenario 1: VWAP Is Useful**
```log
Top 5 Predictive Features:
  1. bs_edge                     32.1%
  2. regime_crisis               18.5%
  3. vwap_deviation_pct          15.2%  ← VWAP feature is important!
  4. time_remaining_norm         12.8%
  5. vol_ratio                   10.9%
```

**Scenario 2: VWAP Not Useful**
```log
Top 5 Predictive Features:
  1. bs_edge                     34.2%
  2. regime_crisis               19.8%
  3. time_remaining_norm         15.4%
  4. vol_ratio                   12.1%
  5. orderbook_imbalance          8.7%
  ...
  11. vwap_deviation_pct          0.8%  ← VWAP ignored by ML
  12. price_above_vwap            0.5%
  13. vwap_trend                  0.3%
```

---

## Research Context

### What Research Shows

❌ **VWAP does NOT improve Black-Scholes pricing** (no academic evidence)
❌ **VWAP does NOT create arbitrage opportunities** (it's an execution tool)
✅ **VWAP works for intraday trend-following** (5-15 minute timeframes)
✅ **VWAP used by 70-80% of institutions** (execution quality benchmark)

### Why We Added It Anyway

**Experimental Approach**:
1. ✅ VWAP reduces noise (volume-weighted vs single tick)
2. ✅ VWAP shows institutional consensus ("fair value")
3. ✅ VWAP might identify mispricing (deviation signals)
4. ✅ **Let ML decide** if it's useful (not us)

**If VWAP is useful**: Feature importance will be 10-20%
**If VWAP is useless**: Feature importance will be <2% (ML ignores it)

---

## Expected Outcomes

### Likely: VWAP Adds Marginal Value (5-10%)

**Reasoning**:
- Time-Decay strategy already works (time-decay physics sound)
- VWAP is correlated with spot price (not independent signal)
- 15-minute markets have low volume (VWAP less reliable)

**Expected Feature Importance**:
- `vwap_deviation_pct`: 3-8% (might catch extreme deviations)
- `price_above_vwap`: 1-3% (directional bias)
- `vwap_trend`: 1-2% (trend confirmation)

### Possible: VWAP Is Ignored (<2%)

**Why This Could Happen**:
- VWAP too correlated with other features (bs_edge, price_distance)
- Not enough signal in 15-minute windows
- Random Forest prefers other features

**What to Do**: Nothing - ML will ignore it automatically

### Unlikely: VWAP Is Key Feature (>15%)

**If This Happens**:
- VWAP deviation predicts reversals
- Institutional flow visible in VWAP trend
- Consider increasing VWAP weight in strategy

---

## Monitoring VWAP Effectiveness

### After 50 Trades (First Training)

Check feature importance in logs:
```bash
grep "All Features Used by ML Model" time_decay.log -A 15
```

Look for VWAP features (#11-13) and their importance %.

### After 100+ Trades (Statistically Significant)

Compare performance with/without VWAP:
- **With VWAP**: Current win rate
- **Without VWAP**: Would need A/B test (not practical)

**Better approach**: Trust ML feature selection
- If VWAP importance >5%: It's helping
- If VWAP importance <2%: It's not helping (but not hurting either)

---

## Technical Details

### Why Volume = 1.0?

Binance **spot prices** don't include volume per tick:
- WebSocket gives: `{price: 79200.50, timestamp: ...}`
- No volume field for spot markets

**Result**: VWAP becomes **TWAP** (Time-Weighted Average Price)
- Still useful for noise reduction
- Still shows price trend
- Less accurate than true VWAP with volume

**Alternative** (not implemented):
- Use Binance **order book depth** as volume proxy
- More complex, minimal benefit for this use case

### Rolling Window Size

**15 minutes (900s)** chosen to match market duration:
- Captures full market lifecycle
- Resets automatically each round (data ages out)
- Not too short (noisy) or too long (laggy)

**Could be adjusted**:
- 10 minutes (600s): Faster reaction, more noise
- 20 minutes (1200s): Smoother, more lag

---

## Configuration

**No configuration needed** - automatically enabled for Time-Decay mode.

**To disable** (if VWAP proves useless after testing):
```python
# In bot.py, comment out VWAP initialization:
# self.vwap_calculator = get_vwap_calculator(window_seconds=900)
# self.vwap_calculator = None
```

**To adjust window**:
```python
# Change window size (in seconds)
self.vwap_calculator = get_vwap_calculator(window_seconds=600)  # 10 minutes
```

---

## Files Modified/Created

### New Files
- `src/utils/vwap.py` - VWAP calculator (220 lines)
- `VWAP_INTEGRATION.md` - This documentation

### Modified Files
- `src/ml/time_decay_calibrator.py`:
  - Added 3 VWAP features
  - Updated feature descriptions
  - Updated extract_features() and calibrate_edge()
- `src/bot.py`:
  - Imported VWAP calculator
  - Initialized in Time-Decay mode
  - Feed price ticks to VWAP
  - Use VWAP features in calibration

---

## Next Steps

### 1. Collect 50 Trades

Run Time-Decay mode and let it collect 50 trades with VWAP features.

### 2. Review First Training

When ML trains, check feature importance:
```bash
grep "All Features Used by ML Model" time_decay.log -A 15
```

Look at VWAP feature percentages (#11-13).

### 3. Evaluate After 100 Trades

With statistical significance, determine:
- **VWAP helpful** (>5% importance): Keep it ✅
- **VWAP neutral** (<5% but >1%): Keep it (no harm) 🤷
- **VWAP ignored** (<1%): Consider removing to reduce complexity ❌

### 4. Iterate

If VWAP shows promise (>10% importance):
- Experiment with window sizes (10min, 20min)
- Add VWAP-based thresholds (only trade if |deviation| > X%)
- Use VWAP as Black-Scholes input (replace spot price)

If VWAP is useless (<1% importance):
- Remove features to simplify model
- Document findings for future reference

---

## Summary

**What We Did**: Added 3 VWAP features as experimental ML inputs

**Why**: Research doesn't support VWAP for arbitrage/BS, but worth testing

**Approach**: Let ML decide via feature importance (data-driven)

**Expected**: Marginal value (3-8%) or ignored (<2%)

**Outcome**: Know in 50 trades (first training), confirm in 100 trades

**Risk**: None - if useless, ML ignores it automatically

**Benefits**:
- Potential noise reduction
- Institutional consensus signal
- Deviation detection
- **Zero downside** (ML handles feature selection)

**Bottom Line**: Smart experimental approach - let the data decide! 📊
