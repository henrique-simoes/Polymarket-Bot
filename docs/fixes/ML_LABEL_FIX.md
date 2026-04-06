# ML Training Label Fix - Critical Update

## Problem Fixed

The ML model was learning the **wrong question**.

### Before (Incorrect)

**Model learned:** "Will price go up in the next 60 seconds?"

```python
# WRONG: Compares to price 1 minute ago
price_1min_ago = self.price_history_this_candle[coin][-60]
direction = 1 if current_price > price_1min_ago else 0
```

**This predicted short-term momentum, not the actual market outcome!**

### After (Correct)

**Model learns:** "Will price be higher than the opening price?"

```python
# CORRECT: Compares to candle opening price
opening_price = self.candle_start_price[coin]
direction = 1 if current_price > opening_price else 0
```

**This matches the exact question the market asks and resolves on!**

---

## Why This Matters

### Market Question (from 15M markets)

**"Will [COIN] price be higher in 15 minutes?"**

Resolves by comparing:
- **Opening price** at 00:00 (market start)
- **Closing price** at 15:00 (market end)

If closing > opening → **YES wins**
If closing < opening → **NO wins**

### Old Model Behavior (BROKEN)

**Example:**
```
00:00 - Market opens, BTC = $100 (opening)
08:00 - BTC = $105
08:01 - BTC = $106
        Old model sees: $105 → $106 (1-min UP)
        Learns: direction = 1 (UP)
        But this is IRRELEVANT to final outcome!

10:00 - BTC = $107, model predicts UP (based on recent momentum)
        Bot bets: YES
15:00 - BTC = $98 (crashed after bet)
        Market resolves: $98 < $100 → NO wins
        Bot LOSES despite model's "correct" short-term prediction
```

**Problem:** Model learned patterns that don't predict the actual outcome!

### New Model Behavior (FIXED)

**Same example:**
```
00:00 - Market opens, BTC = $100 (opening)
08:00 - BTC = $105
        New model sees: $105 > $100 (above opening)
        Learns: direction = 1 (UP relative to opening)

08:01 - BTC = $106
        New model sees: $106 > $100 (still above opening)
        Learns: direction = 1 (UP relative to opening)

10:00 - BTC = $107
        Model predicts: UP (price has been above opening)
        Bot bets: YES

10:30 - BTC drops to $102
        New model sees: $102 > $100 (still above opening)
        Learns: direction = 1 (STILL UP relative to opening!)

15:00 - BTC = $102
        Market resolves: $102 > $100 → YES wins
        Bot WINS! Model correctly predicted final outcome
```

**Solution:** Model learns patterns that ACTUALLY predict the market question!

---

## Technical Changes

### File Modified

`src/core/monitoring.py` - Lines 70-78

### Before
```python
# Learn from 1-minute price direction (if we have enough data)
if len(self.price_history_this_candle[coin]) >= 60:
    price_1min_ago = self.price_history_this_candle[coin][-60]

    # Direction: 1 if price increased, 0 if decreased
    direction = 1 if current_price > price_1min_ago else 0

    # THIS IS WHERE CONTINUOUS LEARNING HAPPENS!
    self.learning_engine.add_observation(coin, features, direction)
```

### After
```python
# Learn from CANDLE DIRECTION (opening price vs current price)
# This matches the actual market question: "Will price be higher at end than at start?"
if len(self.price_history_this_candle[coin]) >= 10:  # Need at least 10 observations
    opening_price = self.candle_start_price[coin]

    # Direction: 1 if price is above opening, 0 if below
    # This is what the market ACTUALLY resolves on!
    direction = 1 if current_price > opening_price else 0

    # THIS IS WHERE CONTINUOUS LEARNING HAPPENS!
    self.learning_engine.add_observation(coin, features, direction)
```

### Key Differences

1. **Reference point**: Opening price (00:00) instead of price 1-minute ago
2. **Minimum observations**: 10 instead of 60 (starts learning earlier)
3. **Question alignment**: Now matches actual market resolution logic

---

## Impact on Model Training

### Training Labels Now Represent

**Each observation during the candle:**
- If current price > opening → label = 1 (UP)
- If current price < opening → label = 0 (DOWN)

**Example during one candle:**
```
00:00 - Opening: $100
00:10 - $101 → label: 1 (UP)
01:00 - $102 → label: 1 (UP)
02:00 - $99  → label: 0 (DOWN) ← Price below opening
03:00 - $98  → label: 0 (DOWN)
05:00 - $101 → label: 1 (UP)  ← Price back above
10:00 - $103 → label: 1 (UP)  ← Betting time
```

**Model learns:** When features show patterns like this, final price tends to be above opening.

### Training Timeline

- **After 10 seconds**: First observation added
- **After 15 seconds**: First retrain (5 observations)
- **After 30 seconds**: Has 20+ observations (solid training data)
- **By 10:00**: Has 590+ observations all labeled correctly

**Each observation now directly relates to the market outcome!**

---

## Expected Improvements

### Prediction Accuracy

**Before:**
- Model could predict short-term moves correctly
- But be completely wrong about final outcome
- Win rate: likely <50% (worse than random)

**After:**
- Model learns what features predict final > opening
- Predictions directly relate to market question
- Win rate: should be >50% (better than random if ML works)

### Strategy Alignment

**Before:**
```
Market asks: "Will closing > opening?"
Model predicts: "Will next minute be up?"
❌ MISMATCH
```

**After:**
```
Market asks: "Will closing > opening?"
Model predicts: "Will price stay above opening?"
✅ ALIGNED
```

### Real-World Example

**Scenario:** Bitcoin steady uptrend

```
Old model:
  - Sees small dip: $105 → $104 in last minute
  - Predicts: DOWN (based on recent movement)
  - Bets: NO
  - Reality: Still at $104 > $100 opening
  - Outcome: YES wins
  - Result: BOT LOSES ❌

New model:
  - Sees: $104 > $100 opening
  - Predicts: UP (based on opening comparison)
  - Bets: YES
  - Reality: $104 > $100 opening
  - Outcome: YES wins
  - Result: BOT WINS ✅
```

---

## Testing Checklist

When you run the bot next, verify:

### 1. Early Learning
```
[BTC] Model updated | Samples: 10 | Recent accuracy: 60.0%
```
Should start appearing after ~30 seconds instead of 60+ seconds

### 2. Accuracy Metrics
```
[BTC] Model updated | Samples: 500 | Recent accuracy: 65.0%
```
Watch if accuracy increases (should be >50% if model learns real patterns)

### 3. Predictions Make Sense
```
[BTC] 8m0s - $105.23 | UP | ML: 72.0% UP
```
If price is above opening and trending up, ML should predict high % UP

```
[BTC] 9m0s - $97.50 | DOWN | ML: 28.0% UP
```
If price is below opening and trending down, ML should predict low % UP

### 4. Win Rate Improvement

Track over multiple rounds:
- Bets placed vs outcomes
- Should see >50% win rate if ML is effective
- Compare to old win rate (was it <50%?)

---

## Remaining Risks

**This fix addresses the ML question mismatch, but:**

### Still Missing

1. **Position monitoring**: No tracking after bet placed
2. **Risk management**: Can't exit if price crashes post-bet
3. **Stop-loss**: Can't cut losses early
4. **Take-profit**: Can't lock in gains early

### Example Still-Risky Scenario

```
10:00 - BTC = $105, ML predicts 70% UP → Bot bets YES
10:01 - BTC crashes to $95
15:00 - BTC = $95 < $100 opening → NO wins
        Bot LOSES
```

**With current fix:** Model is predicting the right question, so it might predict lower probability of UP when seeing unstable patterns.

**With full risk management:** Bot could SELL the YES shares at $102 (small loss) instead of holding to $95 (big loss).

---

## Next Steps

### Immediate (Done ✅)
- ✅ Fixed ML training label
- ✅ Model now learns correct question
- ✅ Starts learning earlier (10 obs vs 60)

### High Priority (Should Do Next)
1. **Add position monitoring** - Track price after bet
2. **Implement stop-loss** - Exit if 10%+ adverse move
3. **Implement take-profit** - Exit if 50%+ favorable move

### Medium Priority
4. **Backtest the fix** - Compare old vs new model on historical data
5. **Optimize bet sizing** - Bet more when confident, less when uncertain
6. **Dynamic timing** - Find latest safe time to bet

---

## Summary

**What changed:**
- ML model now learns "price above opening?" instead of "price up in 60s?"
- Training labels match actual market resolution logic
- Model can start learning earlier (10s vs 60s)

**What this fixes:**
- ✅ Model predictions now relate to market outcome
- ✅ Features that predict final outcome get learned
- ✅ Bot strategy aligns with market question

**What still needs work:**
- ❌ No position monitoring post-bet
- ❌ No risk management (stop-loss/take-profit)
- ❌ No ability to exit early if price reverses

**Expected result:**
- Bot should place orders successfully (404 fix working)
- Predictions should be more accurate for final outcome
- Win rate should improve toward >50%
- But still exposed to post-bet price reversals
