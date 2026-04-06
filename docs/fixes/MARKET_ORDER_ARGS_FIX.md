# MarketOrderArgs Fix - Missing order_type Parameter

## The Error

```
[ERROR] Error placing market buy order: PolyApiException[status_code=400,
error_message={'error': 'invalid amounts, the buy orders maker amount supports
a max accuracy of 4 decimals, taker amount a max of 2 decimals'}]
```

## Root Cause

We were missing the **`order_type` parameter** in `MarketOrderArgs` constructor.

According to the official py-clob-client documentation, `MarketOrderArgs` requires:
- `token_id`
- `amount`
- `side`
- **`order_type`** ← WE WERE MISSING THIS!

---

## The Fix

### File: `src/core/polymarket.py`

#### Before (WRONG):

```python
order_args = MarketOrderArgs(
    token_id=token_id,
    amount=amount_usdc,
    side=BUY
    # Missing order_type!
)

order = self.client.create_market_order(order_args)
response = self.client.post_order(order, OrderType.GTC)
```

#### After (CORRECT):

```python
order_args = MarketOrderArgs(
    token_id=token_id,
    amount=amount_usdc,
    side=BUY,
    order_type=OrderType.FOK  # Fill-or-Kill for market orders
)

order = self.client.create_market_order(order_args)
response = self.client.post_order(order, OrderType.FOK)  # Match the order type
```

---

## Official Documentation

From py-clob-client GitHub README:

```python
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

mo = MarketOrderArgs(
    token_id="<token-id>",
    amount=25.0,
    side=BUY,
    order_type=OrderType.FOK  # ← This was required!
)
signed = client.create_market_order(mo)
resp = client.post_order(signed, OrderType.FOK)
```

---

## Why FOK Instead of GTC?

**FOK (Fill-or-Kill)**:
- Executes immediately at market price
- If can't fill completely, cancels entire order
- **Correct for market orders** (immediate execution)

**GTC (Good-Til-Canceled)**:
- Sits in orderbook until filled or manually canceled
- **Correct for limit orders** (passive orders)

We were incorrectly using GTC for market orders.

---

## What Changed

### 1. Market Buy Orders (`create_market_buy_order`)

**Line 244-248 (BEFORE):**
```python
order_args = MarketOrderArgs(
    token_id=token_id,
    amount=amount_usdc,
    side=BUY
)
```

**Line 244-251 (AFTER):**
```python
order_args = MarketOrderArgs(
    token_id=token_id,
    amount=amount_usdc,
    side=BUY,
    order_type=OrderType.FOK
)
```

**Line 255 (BEFORE):**
```python
response = self.client.post_order(order, OrderType.GTC)
```

**Line 258 (AFTER):**
```python
response = self.client.post_order(order, OrderType.FOK)
```

### 2. Market Sell Orders (`create_market_sell_order`)

Same changes applied to sell orders for consistency.

---

## Expected Behavior Now

**Before Fix:**
```
Creating market BUY order: 1.00 USDC...
[ERROR] Error placing market buy order: invalid amounts...
```

**After Fix:**
```
Creating market BUY order: 1.00 USDC...
[OK] Market buy order placed: order_abc123
```

---

## Summary

**The Issue:**
- Missing `order_type` parameter in `MarketOrderArgs`
- Using wrong order type (GTC instead of FOK)

**The Fix:**
- Added `order_type=OrderType.FOK` to `MarketOrderArgs`
- Changed from `OrderType.GTC` to `OrderType.FOK` when posting

**Applied to:**
- ✅ `create_market_buy_order()`
- ✅ `create_market_sell_order()`

**Following:**
- ✅ Official py-clob-client documentation
- ✅ GitHub README example
- ✅ Best practices for market orders

This should resolve the 400 error about invalid amounts!
