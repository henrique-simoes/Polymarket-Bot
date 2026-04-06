# Polymarket Price Display Issue - Analysis

## Problem

The "Mkt Price (YES token)" column in the Live Market Data table is stuck at $0.50 for all coins, indicating the CLOB API price fetching is failing silently.

**Location**: CLI dashboard, "Live Market Data" table
**Symptom**: All Polymarket prices show $0.50 (the default fallback value)
**Impact**: Cannot see real market prices, breaks arbitrage edge calculation

---

## Root Cause Analysis

### Display Code

**File**: `src/bot.py`, line 368

```python
pp = self.market_15m.get_current_price(coin) or 0.5
```

- Calls `market_15m.get_current_price(coin)`
- Defaults to 0.5 if it returns None
- Currently always returns None → always shows 0.5

---

### Price Fetching Chain

**1. market_15m.get_current_price()** (`src/core/market_15m.py:206-209`)

```python
def get_current_price(self, coin: str) -> Optional[float]:
    tokens = self.get_token_ids_for_coin(coin)
    if not tokens or 'yes' not in tokens: return None
    return self.client.get_midpoint_price(tokens['yes'])
```

**2. client.get_midpoint_price()** (`src/core/polymarket.py:141-147`)

```python
def get_midpoint_price(self, token_id):
    try:
        return float(self.client.get_midpoint(token_id))  # ← BUG HERE!
    except Exception as e:
        # Debug logging commented out
        # print(f"[DEBUG] Midpoint fetch failed for {token_id}: {e}")
        return None
```

**3. py-clob-client get_midpoint()** (`examples/.../client.py:359-363`)

```python
def get_midpoint(self, token_id):
    """Get the mid market price for the given market"""
    return get("{}{}?token_id={}".format(self.host, MID_POINT, token_id))
```

---

## The Bug 🐛

**File**: `src/core/polymarket.py`, line 143

```python
return float(self.client.get_midpoint(token_id))  # ← WRONG!
```

**Problem**: `client.get_midpoint()` returns a **dict**, not a number!

**Example Response** (from official example):
```python
{'mid': '0.55'}
```

**What happens**:
1. `get_midpoint()` returns `{'mid': '0.55'}`
2. Code tries: `float({'mid': '0.55'})`
3. Raises `TypeError: float() argument must be a string or a number, not 'dict'`
4. Exception caught, returns `None`
5. Dashboard uses fallback: `0.5`

**Result**: All prices show $0.50

---

## Evidence from Official Documentation

### Example: `get_mid_market_price.py`

```python
resp = client.get_midpoint(
    "71321045679252212594626385532706912750332728571942532289631379312455583992563"
)
# Response: {'mid': '0.55'}
print(resp)
```

**Comment in example**:
```python
# {'mid': '0.55'}
```

This confirms the response is a dict with a 'mid' key containing the price as a string.

---

## The Fix

**File**: `src/core/polymarket.py`, line 141-147

**Current (Broken)**:
```python
def get_midpoint_price(self, token_id):
    try:
        return float(self.client.get_midpoint(token_id))  # ← Tries to convert dict to float
    except Exception as e:
        # print(f"[DEBUG] Midpoint fetch failed for {token_id}: {e}")
        return None
```

**Fixed**:
```python
def get_midpoint_price(self, token_id):
    try:
        result = self.client.get_midpoint(token_id)
        if result and 'mid' in result:
            return float(result['mid'])
        return None
    except Exception as e:
        logger.error(f"Failed to get midpoint price for {token_id}: {e}")
        return None
```

**Changes**:
1. ✅ Extract dict result first
2. ✅ Check if 'mid' key exists
3. ✅ Convert `result['mid']` string to float
4. ✅ Uncomment and improve error logging (use logger instead of print)
5. ✅ Return None if 'mid' key missing

---

## Expected Behavior After Fix

### Before (Current)

```
Live Market Data
Coin │ Strike        │ Mkt Price │ Real Price │ Edge   │ Signal │ Time Left
─────┼───────────────┼───────────┼────────────┼────────┼────────┼──────────
BTC  │ $79,000 (OFF) │ $0.50     │ $79,200    │ +3.2%  │ UP     │ 285s
ETH  │ $3,450 (OFF)  │ $0.50     │ $3,455     │ +1.8%  │ UP     │ 285s
SOL  │ $98.50 (OFF)  │ $0.50     │ $98.75     │ +2.5%  │ UP     │ 285s
```

**Issues**:
- All Mkt Price stuck at $0.50
- Edge calculation may be wrong (based on 0.5 default)

---

### After (Fixed)

```
Live Market Data
Coin │ Strike        │ Mkt Price │ Real Price │ Edge   │ Signal │ Time Left
─────┼───────────────┼───────────┼────────────┼────────┼────────┼──────────
BTC  │ $79,000 (OFF) │ $0.52     │ $79,200    │ +3.8%  │ UP     │ 285s
ETH  │ $3,450 (OFF)  │ $0.48     │ $3,455     │ +1.2%  │ UP     │ 285s
SOL  │ $98.50 (OFF)  │ $0.51     │ $98.75     │ +2.4%  │ UP     │ 285s
```

**Improvements**:
- ✅ Real market prices displayed
- ✅ Accurate edge calculation
- ✅ Better trading signals

---

## Side Effects of the Bug

### 1. Arbitrage Edge Calculation

**Affected Code**: Wherever `get_current_price()` is used

Arbitrage edge is calculated based on the difference between:
- Polymarket implied probability (from YES token price)
- Real probability (from crypto price vs strike)

If Polymarket price is always 0.5, edge calculation is wrong!

**Example**:
- Real price: $79,200
- Strike: $79,000
- Real should be UP (>50% probability)
- Polymarket shows: 0.5 (50%)
- Calculated edge: 0% (wrong!)

**Actual** (if Polymarket shows 0.52):
- Edge: +2% (Polymarket underpricing UP)

### 2. Order Placement

**File**: `src/core/market_15m.py`, line 222

```python
price = self.client.get_midpoint_price(token_id) or 0.5
```

This also uses `get_midpoint_price()` and defaults to 0.5!

**Impact**: When placing orders, estimated shares calculation uses 0.5 if price fetch fails.

### 3. Display Everywhere

All dashboard displays showing Polymarket prices are affected.

---

## Testing After Fix

### Test 1: Check Price Fetching

```python
# In Python console or test script
from src.core.polymarket import PolymarketMechanics

pm = PolymarketMechanics(...)
# Get token ID for BTC YES token
token_id = "..."  # From market

price = pm.get_midpoint_price(token_id)
print(f"Price: ${price:.2f}")
# Should show something like: Price: $0.52 (not $0.50 always)
```

### Test 2: Check Dashboard Display

Start bot and verify:
- [ ] Mkt Price column shows varying prices (not all 0.50)
- [ ] Prices change over time as market moves
- [ ] Prices are reasonable (between 0.01 and 0.99)
- [ ] Edge calculation makes sense

### Test 3: Check Logs

After fix, if price fetch fails, should see error logs:
```
[ERROR] Failed to get midpoint price for 0x123...: [error message]
```

Currently, errors are silent (logging commented out).

---

## Additional Improvements

### 1. Enable Error Logging

The try/except currently swallows all errors silently. After fix:

```python
except Exception as e:
    logger.error(f"Failed to get midpoint price for {token_id}: {e}")
    return None
```

This helps debug future issues.

### 2. Add Response Validation

```python
if result and 'mid' in result:
    return float(result['mid'])
else:
    logger.warning(f"Invalid response from get_midpoint: {result}")
    return None
```

### 3. Cache Midpoint Prices (Optional)

If API calls are slow, could add short-term caching (5-10 seconds):

```python
self.midpoint_cache = {}  # token_id -> (price, timestamp)

def get_midpoint_price(self, token_id):
    # Check cache first
    if token_id in self.midpoint_cache:
        price, timestamp = self.midpoint_cache[token_id]
        if time.time() - timestamp < 5:  # 5 second cache
            return price

    # Fetch from API
    try:
        result = self.client.get_midpoint(token_id)
        if result and 'mid' in result:
            price = float(result['mid'])
            self.midpoint_cache[token_id] = (price, time.time())
            return price
    except Exception as e:
        logger.error(f"Failed to get midpoint price: {e}")

    return None
```

---

## Why This Bug Exists

### 1. Incorrect Assumption

Developer assumed `get_midpoint()` returns a float/string, but it returns a dict.

### 2. Silent Failures

The try/except catches the error but returns None silently. Debug logging was commented out:

```python
# print(f"[DEBUG] Midpoint fetch failed for {token_id}: {e}")
```

This made it impossible to detect the bug during development.

### 3. Fallback Masks the Issue

The `or 0.5` fallback means the dashboard still displays *something*, so the bug isn't immediately obvious:

```python
pp = self.market_15m.get_current_price(coin) or 0.5
```

Without the fallback, it would show `None` or crash, making the bug more visible.

---

## Verification Checklist

After applying fix:

- [ ] **Price Display**: Mkt Price shows varying values (not all 0.50)
- [ ] **Price Range**: Prices between $0.01 - $0.99 (reasonable)
- [ ] **Price Changes**: Prices update over time (not static)
- [ ] **Edge Calculation**: Edge values make sense
- [ ] **No Errors**: No midpoint fetch errors in logs (unless API issue)
- [ ] **Order Placement**: Still works correctly

---

## Related Files

All files that call `get_midpoint_price()`:

1. ✅ `src/core/polymarket.py:141-147` - The wrapper (NEEDS FIX)
2. `src/core/market_15m.py:209` - Calls wrapper
3. `src/core/market_15m.py:222` - Order placement
4. `src/bot.py:368` - Dashboard display
5. `src/bot.py:1102` - Arbitrage calculation
6. `src/bot.py:1359` - Arbitrage calculation
7. `src/ml/position_tracker.py:207` - Position tracking

**Only 1 file needs fixing**: `src/core/polymarket.py`

All other files will automatically work once the wrapper is fixed.

---

## Conclusion

**Status**: 🔴 **CRITICAL BUG**

**Impact**:
- High - Breaks price display and arbitrage calculations
- All Polymarket prices show as $0.50

**Priority**: **URGENT** - Core functionality broken

**Fix Complexity**: Simple - 5 lines of code
**Testing Time**: 2-3 minutes

**Recommended Action**: Apply fix immediately and verify with next market update.

---

**Analysis Date**: February 3, 2026
**Status**: 🐛 BUG IDENTIFIED - Fix Required
