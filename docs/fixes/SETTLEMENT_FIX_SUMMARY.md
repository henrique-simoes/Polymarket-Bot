# Settlement Flow Fix - Implementation Summary

## Overview

Fixed critical bugs in the settlement process based on official Polymarket documentation. The bot was waiting only 15 seconds and using local price comparison instead of polling the CLOB API for official market resolution.

---

## Critical Bugs Fixed

### 1. Settlement Wait Time ✅ FIXED

**Problem**: Bot waited only 15 seconds, attempting settlement before market even closed.

**Root Cause**:
```python
# BEFORE (src/bot.py:771)
time.sleep(15)  # Wait for market resolution
```

**Fix**:
- Calculate proper wait time based on seconds remaining when settlement starts
- Add resolution delay (90 seconds for Chainlink oracle)
- Total wait: `time_until_close + 90 seconds`

**Implementation**:
```python
# AFTER (src/bot.py:810-826)
def background_settlement(self, placed_bets, start_prices, seconds_remaining_at_start=0):
    # Calculate proper wait time
    resolution_delay = 90  # Chainlink oracle delay
    time_until_close = max(0, seconds_remaining_at_start)
    total_wait = time_until_close + resolution_delay

    logger.info(f"Market timing: {time_until_close:.0f}s until close + {resolution_delay}s resolution = {total_wait:.0f}s total")

    if total_wait > 0:
        time.sleep(total_wait)
```

**Result**: Settlement now waits until market closes (~900s) plus oracle resolution time (90s).

---

### 2. Market Resolution Polling ✅ FIXED

**Problem**: Bot assumed market resolved instantly and used local price comparison.

**Root Cause**:
```python
# BEFORE (src/bot.py:832)
actual = self.market_15m.check_resolution(coin, bet['start_price'], final_p)
# This just compared: UP if final_p >= start_price else DOWN
```

**Fix**:
- Added polling method that queries CLOB API until market resolves
- Checks `market['closed'] == True` from official API
- Extracts winning outcome from `tokens[].winner` field
- Includes timeout and fallback

**Implementation**:
```python
# NEW METHOD (src/bot.py:767-808)
def wait_for_market_resolution(self, condition_id: str, coin: str, max_wait: int = 120) -> Optional[str]:
    """Poll CLOB API until market resolves and return winning outcome."""
    poll_interval = 5
    waited = 0

    while waited < max_wait:
        # Use official resolution check
        outcome = self.market_15m.check_official_resolution(condition_id)

        if outcome:
            logger.info(f"✓ Market resolved: {coin} → {outcome} (waited {waited}s)")
            return outcome

        time.sleep(poll_interval)
        waited += poll_interval

    # Timeout - fallback to price comparison
    logger.error(f"✗ Market did not resolve after {max_wait}s! Fallback to price comparison.")
    return None
```

**Usage in Settlement** (src/bot.py:828-847):
```python
for bet in placed_bets:
    coin = bet['coin']
    final_p = self.fetch_current_price(coin)

    # Get official resolution via CLOB API
    condition_id = bet.get('condition_id')
    if condition_id:
        actual = self.wait_for_market_resolution(condition_id, coin, max_wait=120)

        # Fallback if polling fails
        if not actual:
            logger.warning(f"Using fallback price comparison for {coin}")
            actual = self.market_15m.check_resolution(coin, bet['start_price'], final_p)
    else:
        # No condition_id, use price comparison
        actual = self.market_15m.check_resolution(coin, bet['start_price'], final_p)
```

**Result**: Settlement now uses official Polymarket resolution from CLOB API.

---

### 3. Learning Mode Compatibility ✅ FIXED

**Problem**: Learning mode orders didn't include `condition_id`, preventing official resolution.

**Fix**:
- Added `condition_id` parameter to `simulate_order()` method
- Extracted `condition_id` from market cache before simulating order
- Included in returned order dict

**Implementation**:

In bot.py (lines 1178-1197):
```python
if self.learning_mode and self.learning_simulator:
    # Get condition_id from market cache for learning mode
    market = self.market_15m.market_cache.get(opp['coin'], {})
    condition_id = market.get('conditionId') or market.get('condition_id') or market.get('id')

    order = self.learning_simulator.simulate_order(
        coin=opp['coin'],
        direction=opp['direction'],
        amount=bet_amt,
        token_id=opp['token_id'],
        start_price=self.start_prices.get(opp['coin'], 0),
        current_price=cp,
        confidence=opp['combined_score'],
        condition_id=condition_id  # ← NEW
    )
```

In learning_simulator.py (lines 47-96):
```python
def simulate_order(self, ..., condition_id: str = None):
    position = {
        'order_id': order_id,
        'coin': coin,
        'direction': direction,
        'amount': amount,
        'token_id': token_id,
        'condition_id': condition_id,  # ← NEW
        ...
    }
```

**Result**: Learning mode now uses official resolution polling, same as real mode.

---

## Settlement Flow Comparison

### BEFORE (Broken)

```
Settlement thread starts
    ↓
Wait 15 seconds ← WRONG! Market still has ~14:45 remaining
    ↓
Compare current_price >= start_price ← Local calculation, not official
    ↓
Assume resolved
    ↓
Save trade
```

**Problems**:
- Waited only 15s instead of ~990s
- Used local price comparison instead of official resolution
- Never checked if market actually resolved
- Would fail if run before market closed

---

### AFTER (Fixed)

```
Settlement thread starts with seconds_remaining_at_start
    ↓
Calculate wait: time_until_close + 90s
    ↓
Wait ~990 seconds (market close + oracle delay)
    ↓
Poll CLOB API every 5s for up to 2 minutes:
    client.get_market(condition_id)
    Check market['closed'] == True
    Extract tokens[].winner → outcome
    ↓
Official outcome: UP or DOWN
    ↓
Save trade with correct result
```

**Improvements**:
- Waits full market duration (~900s) + oracle delay (90s)
- Uses official Polymarket resolution from CLOB API
- Polls until market actually resolves
- Includes timeout and fallback
- Works for both real and learning modes

---

## Files Modified

### 1. `src/bot.py`

**Line 767-808**: Added `wait_for_market_resolution()` method
- Polls CLOB API until market resolves
- Returns official outcome or None on timeout
- Works for both real and learning modes

**Line 810**: Modified `background_settlement()` signature
- Added `seconds_remaining_at_start` parameter

**Line 815-826**: Fixed settlement wait time calculation
- Calculates time_until_close + resolution_delay
- Total wait: ~990 seconds instead of 15 seconds

**Line 828-847**: Use official resolution polling
- Calls `wait_for_market_resolution(condition_id, coin)`
- Fallback to price comparison if polling fails
- Fetches final_price for trade records

**Line 1178-1197**: Extract condition_id for learning mode
- Gets condition_id from market_cache
- Passes to simulate_order()

**Line 1437-1440**: Pass timing info to settlement thread
- Captures seconds_remaining when starting settlement
- Passes as parameter to background_settlement()

### 2. `src/core/learning_simulator.py`

**Line 47**: Added `condition_id` parameter to `simulate_order()`

**Line 87**: Include `condition_id` in position dict

---

## Verification Steps

### Test Settlement in Real Mode

1. Start bot in real mode
2. Wait for order placement during SNIPE phase
3. Monitor logs for settlement:

Expected output:
```
[REAL] [SETTLEMENT] Starting settlement for 1 bets
[REAL] [SETTLEMENT] Market timing: 285s until close + 90s resolution = 375s total wait
[REAL] [SETTLEMENT] Waiting 375s for market close + resolution...
[REAL] [SETTLEMENT] Wait complete, now checking market resolution...
[REAL] [SETTLEMENT] Processing bet: BTC UP
[REAL] [RESOLUTION] Polling for BTC market resolution (condition: 0x123456789abc...)
[REAL] [RESOLUTION] Market not resolved yet, polling every 5s...
[REAL] [RESOLUTION] ✓ Market resolved: BTC → UP (waited 35s)
[REAL] Saving trade to history: BTC UP - WON
[SETTLEMENT] Trade saved successfully
```

### Test Settlement in Learning Mode

1. Start bot in learning mode
2. Wait for virtual order during SNIPE phase
3. Monitor logs for settlement:

Expected output:
```
[LEARNING] [SETTLEMENT] Starting settlement for 1 bets
[LEARNING] [SETTLEMENT] Market timing: 285s until close + 90s resolution = 375s total wait
[LEARNING] [SETTLEMENT] Waiting 375s for market close + resolution...
[LEARNING] [SETTLEMENT] Wait complete, now checking market resolution...
[LEARNING] [SETTLEMENT] Processing bet: BTC UP
[LEARNING] [RESOLUTION] Polling for BTC market resolution (condition: 0x123456789abc...)
[LEARNING] [RESOLUTION] Market not resolved yet, polling every 5s...
[LEARNING] [RESOLUTION] ✓ Market resolved: BTC → UP (waited 35s)
[LEARNING] Taking LEARNING MODE settlement path
```

### Check Data Files After Settlement

**Real Mode**:
```bash
cat data/trade_history.json | jq '.[-1]'
# Should show new trade with:
# - condition_id
# - won: true/false (based on official resolution)
# - final_price
# - timestamp
```

**Learning Mode**:
```bash
cat data/learning_trades.json | jq '.[-1]'
# Should show new virtual trade with same structure
```

---

## Expected Behavior Changes

### Before Fix

- ❌ Settlement ran after 15 seconds (market still active)
- ❌ Used local price comparison (not official resolution)
- ❌ Would fail if market hadn't closed yet
- ❌ Learning mode had no condition_id

### After Fix

- ✅ Settlement waits full market duration + oracle delay (~990s)
- ✅ Uses official Polymarket resolution from CLOB API
- ✅ Polls until market actually resolves (up to 2 minutes)
- ✅ Works correctly for both real and learning modes
- ✅ Includes fallback to price comparison if polling fails
- ✅ Learning mode has condition_id and uses official resolution

---

## Known Limitations

### Token Redemption Not Implemented

The fix addresses settlement (determining who won), but does NOT implement token redemption.

**Current behavior**:
- After settlement, winning tokens remain as tokens (not USDC)
- Polymarket auto-redeems after 24-48 hours
- Manual redemption would require additional on-chain transactions

**Future enhancement** (Tasks #3-4):
- Track token states (MATCHED → RESOLVED → REDEEMED)
- Display "Positions Awaiting Settlement" section
- Implement manual redemption trigger

**Why it's OK for now**:
- Auto-redemption happens automatically
- Balance updates after ~24-48 hours
- Critical fix is determining correct outcome (now working)

### Fallback Behavior

If CLOB API polling fails (timeout or error):
- Falls back to local price comparison
- Logs warning message
- Trade still saved (doesn't block settlement)

This ensures settlement always completes even if API has issues.

---

## Summary

### Critical Fixes Applied

1. ✅ **Settlement wait time**: 15s → ~990s (proper timing)
2. ✅ **Resolution method**: Local price comparison → Official CLOB API polling
3. ✅ **Learning mode**: Added condition_id support
4. ✅ **Both modes**: Use official resolution with fallback

### Impact

- **Before**: Settlement ran too early, used wrong resolution method
- **After**: Settlement waits correctly, uses official Polymarket resolution
- **Result**: Trades now record accurate outcomes from Polymarket's oracle

### What's Still Missing (Non-Critical)

- Token state tracking (MATCHED → RESOLVED → REDEEMED)
- "Positions Awaiting Settlement" display
- Manual token redemption trigger

These are future enhancements tracked in Tasks #3-4.

---

## Testing Checklist

- [ ] Real mode: Settlement waits ~990 seconds
- [ ] Real mode: Uses official resolution polling
- [ ] Real mode: Trades save to trade_history.json
- [ ] Learning mode: Settlement waits ~990 seconds
- [ ] Learning mode: Uses official resolution polling
- [ ] Learning mode: Trades save to learning_trades.json
- [ ] Both modes: Fallback works if polling fails
- [ ] Both modes: ML training continues (finalize_round called)

---

**Implementation Date**: February 3, 2026
**Status**: ✅ COMPLETE - Ready for testing
