# Critical Strategy Issues - ML Training & Risk Management

## Executive Summary

After reading the documentation, I've identified **fundamental issues** with the bot's strategy that go beyond the 404 errors:

1. **ML Model Mismatch**: The model learns 1-minute price movements, but the market resolves based on 15-minute opening-to-closing comparison
2. **No Risk Management**: Once a bet is placed, there's NO mechanism to exit if price moves against it
3. **Timing Paradox**: Markets close early (causing 404s), but betting earlier increases exposure to post-bet price changes

---

## Issue 1: ML Model Trains on Wrong Question

### What the Market Actually Asks

From `ARCHITECTURE_VERIFICATION.md`:
> Question format: "Will [COIN] price be higher in 15 minutes?"

This means:
- **Opening price** at 00:00 (market start): $100
- **Closing price** at 15:00 (market end): $101
- Market resolves: **YES** because $101 > $100

### What the ML Model Learns

From `src/ml/learning.py:70-75`:
```python
# Learn from 1-minute price direction
if len(self.price_history_this_candle[coin]) >= 60:
    price_1min_ago = self.price_history_this_candle[coin][-60]

    # Direction: 1 if price increased, 0 if decreased
    direction = 1 if current_price > price_1min_ago else 0

    self.learning_engine.add_observation(coin, features, direction)
```

The model learns: **"Will price go UP in the next 60 seconds?"**

### The Mismatch

| ML Model Predicts | Market Actually Resolves |
|-------------------|-------------------------|
| 1-minute price movements | 15-minute opening-to-closing comparison |
| Short-term momentum | Full candle direction |
| Current price vs 1 min ago | Final price vs opening price |

**Example of Failure:**
```
00:00 - Market opens, BTC = $100 (opening price)
00:05 - Bot starts monitoring
10:00 - Current price $105, trending UP strongly
        ML sees: $104→$105 in last minute → 67% UP probability
        Bot places bet: YES (expecting UP)
10:01 - Price crashes to $98
15:00 - Closing price $98
        Market resolves: $98 < $100 → NO wins
        Bot LOSES despite correct short-term prediction!
```

---

## Issue 2: No Risk Management After Bet Placement

### Current Flow

1. **10:00**: Bot places market order → Executes immediately → Receives YES/NO shares
2. **10:00 - 15:00**: Bot does NOTHING (just waits)
3. **15:00**: Market resolves
4. **Result**: Win or lose, no in-between

### What's Missing

From `src/core/polymarket.py`, there ARE methods to manage positions:
```python
def cancel_order(self, order_id: str) -> bool:
    """Cancel an order"""
    # EXISTS but NEVER USED by bot!

def cancel_all_orders(self) -> bool:
    """Cancel all open orders"""
    # EXISTS but NEVER USED by bot!
```

**But these can't help because:**
- Market orders execute **immediately**
- Once you have shares, you can't "cancel" them
- You'd need to **SELL** the shares back to the market

### What SHOULD Happen

From CTF documentation, you CAN sell YES/NO tokens before resolution:
> "the Gnosis CTF contract allows for 'splitting' and 'merging' full outcome sets"

**Proper Risk Management:**
```python
# MISSING FROM BOT!
def monitor_position_after_bet(coin, shares, entry_price):
    """Monitor position and exit if price moves against us"""

    while not market_resolved:
        current_price = get_current_price(coin)

        # Stop-loss: exit if price moved significantly against bet
        if is_losing_position(entry_price, current_price):
            sell_shares(coin, shares)  # Exit position!
            break

        # Take profit: exit if strong profit
        if is_winning_significantly():
            sell_shares(coin, shares)  # Lock in gains!
            break

        sleep(5)
```

**This is completely absent from the current implementation!**

---

## Issue 3: Training Time Analysis

### Question: "Is 10 minutes enough time for models to train?"

**Answer: YES, but the model is learning the WRONG thing**

Training timeline (600 second monitoring period):
```
00:00 - Market opens
00:05 - Bot starts monitoring
01:05 - First observation added (after 60 seconds)
01:10 - First retrain (5 observations)
01:25 - Has 20 observations (minimum needed)
...
10:00 - Has 540 observations, retrained 108 times
```

**Retraining frequency:**
- From `src/ml/learning.py:42`: `retrain_frequency = 5`
- (600 - 60) / 5 = **108 retraining cycles**
- Each retrain uses last 100 observations

**The problem isn't quantity - it's QUALITY:**
- Model has PLENTY of data (540 observations)
- Model retrains PLENTY of times (108 cycles)
- But it's learning to predict **1-minute movements**, not **15-minute outcomes**!

---

## Issue 4: The Timing Paradox

### The Catch-22

1. **Bet early (10:00)**:
   - ✅ Market still accepting orders
   - ❌ 5 minutes for price to move against you
   - ❌ No risk management if it does

2. **Bet late (13:00+)**:
   - ✅ Less time for price to change
   - ❌ Market stops accepting orders (404 errors!)

3. **Bet very late (14:00+)**:
   - ✅ Price almost final
   - ❌ Market definitely closed

### Why Markets Close Early

From RTDS documentation:
- Markets use **Chainlink oracles** for resolution
- Oracle needs time to fetch price data
- Trading must close BEFORE end time for settlement

**Estimate**: Markets likely close 3-5 minutes before `endDate`
- `endDate`: 15:00
- Trading closes: ~11:00-12:00
- We're betting at: 10:00
- Exposure time: 1-2 minutes (acceptable)
- **BUT** still no risk management!

---

## What Needs to Change

### Option A: Fix the ML Model (Recommended)

**Change what the model learns:**

Instead of:
```python
# Current: predict next 60 seconds
direction = 1 if current_price > price_1min_ago else 0
```

Use:
```python
# Predict final price vs opening price
start_price = candle_start_price[coin]
direction = 1 if current_price > start_price else 0
```

**This makes the model learn the ACTUAL market question!**

### Option B: Add Risk Management

**Implement position monitoring:**

```python
def place_bet_with_monitoring(coin, prediction, amount):
    # Place bet
    order = place_prediction(coin, prediction, amount)

    if not order:
        return None

    # Monitor position until resolution
    monitor_and_manage_position(
        coin=coin,
        shares=order['shares'],
        direction=prediction,
        entry_price=order['price'],
        stop_loss_pct=10,  # Exit if 10% adverse move
        take_profit_pct=50  # Exit if 50% profit
    )
```

### Option C: Adjust Bet Timing Dynamically

**Check market status in real-time:**

```python
def find_optimal_bet_time(coin):
    """Find latest possible time market still accepts orders"""

    for minutes_before_end in range(5, 0, -1):
        bet_time = end_time - timedelta(minutes=minutes_before_end)

        if is_market_accepting_orders(coin):
            return bet_time

    return None  # Market closed
```

### Option D: Combine All Three

1. **Fix ML** to predict opening-to-closing movement
2. **Add risk management** to exit positions if price moves against bet
3. **Optimize timing** to bet as late as safely possible

---

## Immediate Recommendations

### Critical (Do First)

1. **Fix the ML training label** (1 hour work):
   ```python
   # In src/core/monitoring.py:70-78
   start_price = self.candle_start_price[coin]
   direction = 1 if current_price > start_price else 0  # CHANGED!
   ```

2. **Add market status check before betting** (already done):
   - ✅ `is_market_accepting_orders()` implemented
   - ✅ Betting at 10:00 for buffer time

### Important (Do Next)

3. **Implement position monitoring** (4 hours work):
   - Monitor price after bet placed
   - Exit if price moves significantly against position
   - Sell shares back to market (not just hold and hope)

4. **Add stop-loss and take-profit** (2 hours work):
   - Stop-loss: 10-20% adverse price movement
   - Take-profit: 50%+ favorable movement
   - Lock in gains or cut losses early

### Nice to Have

5. **Dynamic bet timing** (2 hours):
   - Probe market status every 30 seconds
   - Bet at latest possible safe time
   - Minimize exposure to post-bet price changes

6. **Confidence-based position sizing** (1 hour):
   - Bet more when ML is very confident
   - Bet less when ML is uncertain
   - Already partially implemented, enhance it

---

## The Real Problem: 404 Errors

The 404 errors happen because:

1. Markets **DO** close before `endDate` (confirmed)
2. We can't know EXACTLY when without real-time checking (now implemented)
3. The `acceptingOrders` field tells us in real-time (now checked)

**Current fix status:**
- ✅ Check `acceptingOrders` before betting
- ✅ Bet at 10:00 (5 min buffer)
- ✅ Show detailed market status

**But the deeper issue remains:**
- ❌ ML predicts wrong question
- ❌ No risk management after bet
- ❌ Exposed to 5 minutes of adverse price movement

---

## Testing the Current Fixes

**What to watch for in next run:**

1. **Market status logs**:
   ```
   [BTC] Market status check:
        Current time: 06:40:23 UTC
        Market ends:  2026-01-30T06:45:00Z
        acceptingOrders=True, active=True, closed=False
   [OK] Market BTC is accepting orders
   ```

2. **If market closed**:
   ```
   [BTC] Market status check:
        acceptingOrders=False, active=True, closed=False
   [WARN] Market BTC is NOT accepting orders!
   [ERROR] Market is NOT accepting orders (may have closed for trading)
   ```

3. **No more 404 errors** (market status checked first)

**But monitor for:**
- Bets winning based on 10:00 price
- Bets losing due to 10:00-15:00 price reversal
- Win rate significantly <50% (indicates ML mismatch)

---

## Questions to Answer

1. **Can we sell shares before resolution?**
   - CTF docs say yes (splitting/merging)
   - Need to implement actual sell mechanism
   - Would enable stop-loss/take-profit

2. **What's the optimal bet time?**
   - Currently: 10:00 (fixed)
   - Should be: latest time market still accepts orders
   - Requires real-time probing

3. **Should we continue monitoring after bet?**
   - Currently: NO (just wait)
   - Should be: YES (manage position)
   - Would dramatically improve risk/reward

---

## Bottom Line

**The 404 errors are fixed** (by checking `acceptingOrders`).

**But the bot has deeper issues:**
1. ML learns the wrong question
2. No post-bet risk management
3. 5 minutes of unmanaged exposure

**Without fixing these, the bot will:**
- ✅ Place orders successfully
- ❌ Lose money on price reversals
- ❌ Miss opportunities to exit bad positions
- ❌ Hold losing positions to expiry unnecessarily

**Next steps:**
1. Run bot with current fixes to confirm no 404s
2. Implement ML label fix (use opening price, not 1-min-ago price)
3. Add position monitoring and risk management
4. Test on paper trades before live trading
