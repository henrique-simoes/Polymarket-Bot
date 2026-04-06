# Market Timing Fixes - acceptingOrders Check

## Problem

Orders were failing with 404 errors:
```
PolyApiException[status_code=404, error_message={'error': 'No orderbook exists for the requested token id'}]
```

**Root Cause**: Markets stop accepting orders BEFORE their `endDate`. The bot was placing orders at the 13:00 mark (13 minutes into 15-minute window), but markets had already closed for trading.

---

## Key Findings from Documentation

### Gamma API Market Fields

Every market has these critical status fields:
- **`acceptingOrders`**: `true`/`false` - Whether market is currently accepting new orders
- **`active`**: `true`/`false` - Whether market is active
- **`closed`**: `true`/`false` - Whether market is closed
- **`endDate`**: Market resolution time (e.g., "2026-01-30T13:30:00Z")

**Critical Insight**: `acceptingOrders` can be `false` even when `endDate` hasn't been reached yet!

Markets may close for trading several minutes before resolution to allow:
- Order settlement
- Oracle price fetching
- Market resolution preparation

---

## Fixes Applied

### 1. Real-Time Market Status Check (`market_15m.py`)

Added `is_market_accepting_orders()` method that:
1. Re-fetches fresh market data from Gamma API
2. Checks `acceptingOrders`, `active`, and `closed` fields
3. Shows detailed timing info (current time vs endDate)
4. Returns `True` only if market is ready to accept orders

**File**: `src/core/market_15m.py:220`

```python
def is_market_accepting_orders(self, coin: str) -> bool:
    """Check if market is currently accepting orders"""
    # Fetch fresh market data
    response = requests.get(f"{self.gamma_api}/markets/{market_id}")
    fresh_market = response.json()

    accepting = fresh_market.get('acceptingOrders', False)
    active = fresh_market.get('active', False)
    closed = fresh_market.get('closed', True)

    # Show timing info
    print(f"  [{coin}] Market status check:")
    print(f"       Current time: {now_utc.strftime('%H:%M:%S')} UTC")
    print(f"       Market ends:  {end_date}")
    print(f"       acceptingOrders={accepting}, active={active}, closed={closed}")

    return accepting and active and not closed
```

### 2. Pre-Order Validation (`market_15m.py`)

Updated `place_prediction()` to check market status BEFORE placing orders:

**File**: `src/core/market_15m.py:252`

```python
def place_prediction(self, coin: str, prediction: str, amount_usdc: float):
    # Check if market is still accepting orders
    if not self.is_market_accepting_orders(coin):
        print(f"[ERROR] Market is NOT accepting orders (may have closed for trading)")
        return None

    # Proceed with order placement...
```

### 3. Earlier Betting Time (`bot.py`)

Changed betting time from 13:00 to 10:00 (10 minutes into 15-minute window):

**Before**:
- Monitor for 780 seconds (13 minutes)
- Place bets at 13:00
- Only 2 minutes buffer before end

**After**:
- Monitor for 600 seconds (10 minutes)
- Place bets at 10:00
- 5 minutes buffer for market closure

**File**: `src/bot.py:270`

```python
# Place bets at 10:00 (600 seconds into 900 second window)
# This leaves 5 minutes buffer for market closure and order execution
# Markets may stop accepting orders before endDate for settlement
monitoring_duration = min(window_info['seconds_remaining'] - 300, 600)
```

---

## How It Works Now

### Timeline (15-minute market: 06:30-06:45)

```
06:30 - Market opens (eventStartTime)
06:31 - Bot starts monitoring
...
06:40 - Bot places bets ← NEW: 10:00 mark
06:40 - Market status check: acceptingOrders=true ✓
06:41 - Orders execute successfully
...
06:43 - Market MAY close for trading (acceptingOrders=false)
06:45 - Market resolves (endDate)
06:45 - Payouts distributed
```

### Order Placement Flow

```
1. Bot reaches 10:00 mark (10 minutes into window)
2. Call is_market_accepting_orders()
   - Fetches fresh market data
   - Checks acceptingOrders field
   - Shows current time vs end time
3. If acceptingOrders=false:
   - Log warning with market status
   - Skip order placement
   - No 404 error!
4. If acceptingOrders=true:
   - Proceed with order placement
   - Create MarketOrderArgs
   - Post order with GTC
5. Order executes successfully
```

---

## Benefits

### ✅ Prevents 404 Errors
- Checks market status BEFORE placing orders
- Gracefully handles markets that closed early
- No more "No orderbook exists" errors

### ✅ Better Timing
- 10:00 instead of 13:00 gives 5-minute buffer
- More likely to catch market while still accepting orders
- Leaves time for market closure and settlement

### ✅ Diagnostic Information
- Shows exact market status when placing bets
- Displays current time vs end time
- Logs acceptingOrders, active, closed fields
- Helps understand when markets actually close

### ✅ Graceful Degradation
- If one market closed early, others can still trade
- Bot doesn't crash on 404 errors
- Clear logging shows which markets were skipped

---

## Expected Output

**Successful order**:
```
[BTC] Market status check:
     Current time: 06:40:23 UTC
     Market ends:  2026-01-30T06:45:00Z
     acceptingOrders=True, active=True, closed=False
[OK] Market BTC is accepting orders

Creating market BUY order: 1.34 USDC for token...
[OK] Market buy order placed: order_id_here
```

**Market closed early**:
```
[ETH] Market status check:
     Current time: 06:43:15 UTC
     Market ends:  2026-01-30T06:45:00Z
     acceptingOrders=False, active=True, closed=False
[WARN] Market ETH status: acceptingOrders=False, active=True, closed=False
[ERROR] Market is NOT accepting orders (may have closed for trading)
```

---

## Testing Checklist

Run the bot and verify:

1. ✅ Bot monitors for 10 minutes (600 seconds)
2. ✅ Places bets at 10:00 mark
3. ✅ Checks `acceptingOrders` before each order
4. ✅ Shows detailed market status in logs
5. ✅ Successfully places orders if market accepting
6. ✅ Gracefully skips if market closed
7. ✅ No more 404 errors from closed markets

---

## Summary

**Problem**: Markets close for trading before `endDate`, causing 404 errors

**Solution**:
1. Check `acceptingOrders` field in real-time before placing orders
2. Bet earlier (10:00 instead of 13:00) for more buffer time
3. Show detailed market status and timing information

**Result**: Bot now knows when markets are closed and handles it gracefully!
