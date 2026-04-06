# Time-Decay Analytics System

**Comprehensive tracking and visualization for Time-Decay Sniper mode**

---

## Overview

The Time-Decay Analytics System provides deep insights into ML training progress, Black-Scholes accuracy, and trading patterns. All analytics are displayed in a beautiful CLI panel below the main dashboard when running in Time-Decay Sniper mode (Mode D).

---

## What's Tracked

### 1. Feature Importance Evolution
- **What**: Tracks how ML values each of the 13 features over time
- **How**: Records feature importance percentages after each training run
- **Storage**: `data/time_decay_analytics.json` → `feature_importance_history[]`
- **Retention**: Last 20 training runs

**Tracked Features**:
1. `bs_edge` - Black-Scholes edge magnitude
2. `token_price` - Token price (60-90¢ range)
3. `time_remaining_norm` - Normalized time to expiry
4. `price_distance_pct` - Distance from strike price
5. `regime_bull` - BULL regime flag
6. `regime_bear` - BEAR regime flag
7. `regime_crisis` - CRISIS regime flag
8. `vol_ratio` - Realized/Assumed volatility ratio
9. `orderbook_imbalance` - Order flow imbalance
10. `bs_confidence` - How extreme BS prediction is
11. `vwap_deviation_pct` - Distance from VWAP (%)
12. `price_above_vwap` - Binary flag (above/below VWAP)
13. `vwap_trend` - VWAP slope (5min vs 10min)

### 2. Black-Scholes Edge Accuracy
- **What**: Correlation between BS predicted edge and actual outcomes
- **Metrics**:
  - Average BS edge for winners
  - Average BS edge for losers
  - Edge accuracy score (higher edge → higher win rate correlation)
- **Storage**: `bs_edge_accuracy[]` - tracks every trade with `{bs_edge, won, timestamp}`

**Purpose**: Understand if BS model is well-calibrated or overconfident/underconfident

### 3. ML Calibration Adjustments
- **What**: Tracks how ML adjusts BS predictions
- **Metrics**:
  - Average adjustment factor (BS prob → ML prob)
  - Average edge reduction percentage
  - Total calibrations performed
- **Storage**: `calibration_adjustments[]` - tracks `{bs_edge, ml_edge, adjustment_factor, timestamp}`
- **Retention**: Last 100 calibrations

**Purpose**: See if ML is making the bot more conservative or aggressive

### 4. Time-of-Day Patterns
- **What**: Win rates and trade counts by hour (0-23 UTC)
- **Metrics**:
  - Wins/losses per hour
  - Total BS edge per hour
  - Win rate percentage
- **Storage**: `trades_by_hour{}`
- **Analysis**: `get_best_hours(top_n=3)` returns top 3 hours by win rate (minimum 3 trades)

**Purpose**: Identify best times to trade (e.g., US market hours vs Asia hours)

### 5. Price Range Performance
- **What**: Win rates by token price ranges
- **Ranges**:
  - 60-65¢
  - 65-70¢
  - 70-75¢
  - 75-80¢
  - 80-85¢
  - 85-90¢
- **Metrics**:
  - Wins/losses per range
  - Average BS edge per range
  - Win rate percentage
- **Storage**: `trades_by_price_range{}`

**Purpose**: Find optimal entry price zones (e.g., 75-80¢ might have highest win rate)

### 6. Per-Coin Statistics
- **What**: Performance breakdown by coin (BTC, ETH, SOL)
- **Metrics**:
  - Wins/losses per coin
  - Average token price bought
  - Average BS edge
  - Win rate percentage
- **Storage**: `trades_by_coin{}`

**Purpose**: Identify which coins work best for Time-Decay strategy

### 7. Entry Window Performance ⭐ NEW
- **What**: Win rates by entry timing (time remaining when trade placed)
- **Metrics**:
  - Wins/losses per window (60s, 120s, 180s, etc.)
  - Average BS edge per window
  - Win rate percentage per window
- **Storage**: `bs_edge_accuracy[]` (includes `time_remaining` field)
- **Analysis**: `get_best_entry_windows()` returns top performing windows

**Purpose**: Dynamically optimize entry timing - learns whether 2min, 3min, 4min, or 5min is optimal

**Key Feature**: System automatically switches from default 300s to ML-learned optimal window after 20 trades!

---

## Dashboard Display

### Panel Structure (Bottom of Dashboard)

```
┌─ ⚡ Time-Decay Analytics ──────────────────────────────────┐
│                                                             │
│ ╔═══ FEATURE IMPORTANCE ═══╗                               │
│   1. bs_edge                  [████████████████░░░░] 32.1% │
│   2. regime_crisis            [███████████░░░░░░░░░] 18.5% │
│   3. vwap_deviation_pct       [██████████░░░░░░░░░░] 15.2% │
│   4. time_remaining_norm      [████████░░░░░░░░░░░░] 12.8% │
│   5. vol_ratio                [███████░░░░░░░░░░░░░] 10.9% │
│                                                             │
│ ╔═══ BLACK-SCHOLES ACCURACY ═══╗                           │
│   Total Trades:        47                                  │
│   Avg Edge (Winners):  +18.3%                              │
│   Avg Edge (Losers):   +12.1%                              │
│   Edge Accuracy:       64.2%                               │
│                                                             │
│ ╔═══ ML CALIBRATION ═══╗                                   │
│   Calibrations:        23                                  │
│   Avg Adjustment:      0.921x                              │
│   Avg Edge Reduction:  7.9%                                │
│                                                             │
│ ╔═══ BEST TRADING HOURS (UTC) ═══╗                         │
│   1. 14:00 → 78.5% (12 trades)                             │
│   2. 15:00 → 75.2% (8 trades)                              │
│   3. 16:00 → 72.1% (10 trades)                             │
│                                                             │
│ ╔═══ PRICE RANGE PERFORMANCE ═══╗                          │
│   70-75¢     → 80.0% WR | Edge: +16.2% (15)                │
│   75-80¢     → 76.3% WR | Edge: +14.8% (20)                │
│   65-70¢     → 71.4% WR | Edge: +18.1% (7)                 │
│                                                             │
│ ╔═══ ENTRY WINDOW PERFORMANCE ═══╗ ⭐ NEW                  │
│   Current Optimal: 180s (3min)                             │
│   1. 180s (3min) → 82.3% WR | Edge: +17.1% (17)            │
│   2. 240s (4min) → 73.3% WR | Edge: +16.0% (15)            │
│   3. 120s (2min) → 72.7% WR | Edge: +16.4% (11)            │
│                                                             │
│ ╔═══ COIN PERFORMANCE ═══╗                                 │
│   BTC  → 77.8% | Avg: 76¢ | Edge: +15.2% (27)              │
│   ETH  → 73.3% | Avg: 74¢ | Edge: +16.1% (15)              │
│   SOL  → 60.0% | Avg: 78¢ | Edge: +14.5% (5)               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Color Coding

**Feature Importance**:
- Green: ≥15% (highly predictive)
- Yellow: 8-15% (moderately predictive)
- White: <8% (low importance)

**Win Rates**:
- Green: ≥75% (excellent)
- Yellow: 65-75% (good)
- White: <65% (needs improvement)

**BS Edge Accuracy**:
- Green: ≥50% (well calibrated)
- Yellow: 30-50% (decent)
- Red: <30% (poorly calibrated)

**Calibration Adjustment**:
- Green: 0.9-1.1x (minor adjustments)
- Yellow: <0.9x or >1.1x (significant adjustments)

---

## Integration Flow

### 1. Initialization (Bot Startup)
```python
# In bot.py __init__()
self.time_decay_analytics = TimeDecayAnalytics()
self.time_decay_calibrator = TimeDecayCalibrator(analytics=self.time_decay_analytics)
```

### 2. During Training (Calibrator)
```python
# In time_decay_calibrator.py train()
if self.analytics:
    feature_importance_dict = {
        name: float(importance) for name, importance in zip(self.feature_names, importances)
    }
    self.analytics.record_feature_importance(feature_importance_dict)
```

### 3. During Calibration (Edge Calculation)
```python
# In time_decay_calibrator.py calibrate_edge()
if self.analytics:
    self.analytics.record_calibration(bs_edge, calibrated_edge, adjustment_factor)
```

### 4. After Trade Settlement (Bot)
```python
# In bot.py background_settlement()
if self.time_decay_sniper_mode and hasattr(self, 'time_decay_analytics'):
    analytics_data = {
        'coin': trade_record.get('coin'),
        'token_price': trade_record.get('price', 0.75),
        'bs_edge': trade_record.get('arb_edge', 0.0),
        'won': trade_record.get('won', False),
        'timestamp': trade_record.get('timestamp')
    }
    self.time_decay_analytics.record_trade(analytics_data)
```

### 5. Dashboard Rendering (Every Tick)
```python
# In bot.py update_dashboard()
if self.time_decay_sniper_mode:
    analytics_panel = self._create_time_decay_analytics_panel()
    layout["analytics"].update(analytics_panel)
```

---

## Files Modified/Created

### New Files
- `src/ml/time_decay_analytics.py` - Analytics tracking engine (339 lines)
- `TIME_DECAY_ANALYTICS_SYSTEM.md` - This documentation

### Modified Files
- `src/ml/time_decay_calibrator.py`:
  - Added `analytics` parameter to `__init__()`
  - Record feature importance after training (line ~276)
  - Record calibration adjustments during `calibrate_edge()` (line ~349)

- `src/bot.py`:
  - Added import: `from .ml.time_decay_analytics import TimeDecayAnalytics`
  - Initialize analytics tracker (line ~173)
  - Pass analytics to calibrator (line ~174)
  - Record trades after settlement (lines ~1050-1061 learning mode, ~1171-1182 real mode)
  - Added `_create_time_decay_analytics_panel()` method (line ~922)
  - Modified `make_layout()` to add analytics section when in Time-Decay mode (line ~408)
  - Modified `update_dashboard()` to populate analytics panel (line ~645)

---

## Data Storage

### File: `data/time_decay_analytics.json`

```json
{
  "trades_by_hour": {
    "14": {"wins": 9, "losses": 3, "total_edge": 1.95},
    "15": {"wins": 6, "losses": 2, "total_edge": 1.27},
    ...
  },
  "trades_by_price_range": {
    "70-75¢": {"wins": 12, "losses": 3, "total_edge": 2.43},
    "75-80¢": {"wins": 15, "losses": 5, "total_edge": 2.96},
    ...
  },
  "trades_by_coin": {
    "BTC": {"wins": 21, "losses": 6, "total_edge": 4.10, "avg_price": 0.76},
    "ETH": {"wins": 11, "losses": 4, "total_edge": 2.42, "avg_price": 0.74},
    "SOL": {"wins": 3, "losses": 2, "total_edge": 0.73, "avg_price": 0.78}
  },
  "bs_edge_accuracy": [
    {"bs_edge": 0.183, "won": true, "timestamp": "2026-02-04T14:23:15"},
    {"bs_edge": 0.156, "won": false, "timestamp": "2026-02-04T14:38:42"},
    ...
  ],
  "feature_importance_history": [
    {
      "timestamp": "2026-02-04T15:12:00",
      "features": {
        "bs_edge": 0.321,
        "regime_crisis": 0.185,
        "vwap_deviation_pct": 0.152,
        ...
      }
    }
  ],
  "calibration_adjustments": [
    {"bs_edge": 0.18, "ml_edge": 0.165, "adjustment_factor": 0.917, "timestamp": "..."},
    ...
  ]
}
```

**Persistence**: Automatically saved after each:
- `record_trade()` call
- `record_feature_importance()` call
- `record_calibration()` call

**Loading**: Automatically loaded on bot startup via `TimeDecayAnalytics.__init__()`

---

## API Reference

### TimeDecayAnalytics Class

#### `record_trade(trade_data: Dict)`
Records a completed trade for analytics.

**Parameters**:
```python
{
    'coin': str,           # BTC/ETH/SOL
    'token_price': float,  # Token price bought (0.60-0.90)
    'bs_edge': float,      # Black-Scholes edge
    'won': bool,           # True if won, False if lost
    'timestamp': str       # ISO format timestamp
}
```

#### `record_calibration(bs_edge: float, ml_edge: float, adjustment_factor: float)`
Records an ML calibration adjustment.

#### `record_feature_importance(features: Dict[str, float])`
Records feature importance from a training run.

**Parameters**: `{feature_name: importance_percentage}` (e.g., `{"bs_edge": 0.321, ...}`)

#### `get_best_hours(top_n: int = 3) -> List[tuple]`
Returns top N hours by win rate (minimum 3 trades per hour).

**Returns**: `[(hour, win_rate, trades_count), ...]`

#### `get_best_price_ranges() -> List[tuple]`
Returns all price ranges sorted by win rate.

**Returns**: `[(range_key, win_rate, trades_count, avg_edge), ...]`

#### `get_coin_performance() -> List[tuple]`
Returns per-coin performance sorted by trades count.

**Returns**: `[(coin, win_rate, trades_count, avg_price, avg_edge), ...]`

#### `get_bs_accuracy_stats() -> Dict`
Returns Black-Scholes edge accuracy statistics.

**Returns**:
```python
{
    'total_trades': int,
    'avg_edge_winners': float,
    'avg_edge_losers': float,
    'edge_accuracy': float  # correlation metric
}
```

#### `get_calibration_stats() -> Dict`
Returns ML calibration statistics.

**Returns**:
```python
{
    'total_calibrations': int,
    'avg_adjustment_factor': float,  # 1.0 = no adjustment
    'avg_reduction': float           # % reduction in edge
}
```

#### `get_latest_feature_importance() -> Optional[Dict[str, float]]`
Returns most recent feature importance from training.

**Returns**: `{feature_name: importance}` or `None` if no training runs yet

#### `get_feature_importance_trend(feature_name: str) -> List[float]`
Returns historical trend for a specific feature.

**Returns**: List of importance values over time (most recent last)

---

## Insights You Can Gain

### 1. Feature Importance Insights
**Questions Answered**:
- Which features does ML value most?
- Are VWAP features useful? (>5% importance = yes, <2% = no)
- Is BS edge the primary signal or are other factors important?

**Example Insights**:
- "BS edge is 32% of decision → strategy is fundamentally sound"
- "VWAP features total 3% → not very useful, consider removing"
- "Regime crisis flag is 18.5% → regime detection is critical"

### 2. BS Accuracy Insights
**Questions Answered**:
- Is Black-Scholes well-calibrated for 15-minute markets?
- Does higher BS edge actually correlate with higher win rate?
- How much overconfidence does BS have?

**Example Insights**:
- "Winners avg 18.3% edge, losers avg 12.1% edge → BS has predictive power"
- "Edge accuracy 64.2% → decent but not perfect correlation"
- "BS overconfidence +8.5% → predicts 8.5% higher win rate than actual"

### 3. ML Calibration Insights
**Questions Answered**:
- Is ML making the bot more conservative or aggressive?
- How much does ML adjust BS predictions?
- Is calibration consistent or volatile?

**Example Insights**:
- "Avg adjustment 0.92x → ML reduces BS confidence by 8%"
- "Edge reduction 7.9% → ML is conservatively skeptical"
- "Consistent adjustments → ML is well-trained and stable"

### 4. Time-of-Day Insights
**Questions Answered**:
- When is the best time to trade?
- Are there dead zones with poor performance?
- Do US market hours perform better than Asia hours?

**Example Insights**:
- "14:00-16:00 UTC (US market open) has 75%+ win rate"
- "03:00-06:00 UTC (Asia hours) has 55% win rate → avoid"
- "Most activity at 14:00 (12 trades) → liquidity peak"

### 5. Price Range Insights
**Questions Answered**:
- What's the sweet spot price range for Time-Decay?
- Do higher-priced tokens (closer to 90¢) perform better?
- Should we narrow the 60-90¢ filter?

**Example Insights**:
- "70-75¢ range has 80% win rate → optimal entry zone"
- "85-90¢ range has 65% win rate → too close to certainty, low edge"
- "60-65¢ range has low sample (7 trades) → rare opportunities"

### 6. Coin Performance Insights
**Questions Answered**:
- Which coin works best for Time-Decay strategy?
- Should we focus on one coin or diversify?
- Do different coins have different optimal price ranges?

**Example Insights**:
- "BTC: 77.8% win rate, 27 trades → most reliable"
- "SOL: 60% win rate, 5 trades → small sample, needs more data"
- "BTC avg price 76¢, ETH avg price 74¢ → similar entry zones"

---

## Recommended Actions Based on Analytics

### If VWAP Features Show Low Importance (<2%)
- **Action**: Remove VWAP features to simplify model
- **Reason**: Reduces complexity without losing predictive power
- **Files to Modify**: `time_decay_calibrator.py` (remove features 11-13)

### If Specific Hours Have Consistently Low Win Rate (<60%)
- **Action**: Add time-of-day filter to bot
- **Reason**: Avoid trading during unfavorable hours
- **Example**: Skip trades during 03:00-06:00 UTC if win rate <60%

### If Certain Price Range Dominates (e.g., 70-75¢ is 80%+)
- **Action**: Narrow price filter to focus on that range
- **Reason**: Maximize win rate by avoiding suboptimal ranges
- **Config Change**: Modify `is_time_decay_opportunity()` to check specific ranges

### If BS Overconfidence Is Consistently High (>10%)
- **Action**: Increase ML calibration weight in decision
- **Reason**: BS is too optimistic, need more ML skepticism
- **Code Change**: Adjust calibration adjustment factor in `calibrate_edge()`

### If One Coin Significantly Outperforms Others
- **Action**: Increase bet size on that coin, reduce on others
- **Reason**: Allocate capital to highest-performing asset
- **Config Change**: Add per-coin bet multipliers

---

## Monitoring Strategy

### Daily Review (After 24 Hours of Trading)
1. Check feature importance - Are VWAP features useful?
2. Check BS accuracy - Is edge accuracy >50%?
3. Check time-of-day - Any clear patterns emerging?

### Weekly Review (After 50+ Trades)
1. Analyze price range performance - Should we narrow filter?
2. Compare coin performance - Focus on specific coins?
3. Check ML calibration - Is adjustment factor stable?

### Monthly Review (After 200+ Trades)
1. Feature importance trends - Which features gaining/losing importance?
2. Time-of-day patterns - Statistically significant patterns?
3. Overall strategy effectiveness - Win rate meeting expectations (75%+)?

---

## Troubleshooting

### Panel Shows "Analytics not initialized"
**Cause**: Time-Decay mode not selected or analytics not created
**Fix**: Ensure Mode D (Time-Decay Sniper) is selected at startup

### Panel Shows Empty Sections
**Cause**: No trades recorded yet
**Fix**: Wait until first trades complete and settle

### Feature Importance Not Showing
**Cause**: ML model not trained yet (need 50+ trades)
**Fix**: Continue trading until 50 trades threshold is reached

### Analytics Data Not Persisting
**Cause**: Permissions issue or file write error
**Check**: `ls -la data/time_decay_analytics.json` - should exist and be writable
**Fix**: `chmod 644 data/time_decay_analytics.json`

---

## Summary

**What You Get**:
- ✅ Real-time feature importance visualization
- ✅ BS edge accuracy tracking and analysis
- ✅ ML calibration adjustment monitoring
- ✅ Time-of-day pattern detection
- ✅ Price range performance breakdown
- ✅ Per-coin statistics and comparisons

**How It Helps**:
- 📊 Verify ML is training correctly (feature importance evolving)
- 🎯 Validate BS model accuracy (edge correlation with outcomes)
- ⚙️ Monitor ML calibration effectiveness (adjustment factors)
- ⏰ Optimize trading hours (avoid low-win-rate periods)
- 💰 Identify best price ranges (focus on high-win-rate zones)
- 🪙 Compare coin performance (allocate capital optimally)

**Bottom Line**: You can now answer "How can we be sure ML is training and BS is working?" with comprehensive, real-time analytics! 🎉

---

**Built with Claude Code | February 2026**
