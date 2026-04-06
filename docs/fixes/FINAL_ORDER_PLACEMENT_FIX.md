# Final Order Placement Fix - Using Official API Correctly

## The Problem

We were using `MarketOrderArgs` which doesn't exist in the official Polymarket CLOB API documentation. This caused decimal precision errors.

## Official Documentation Approach

From https://docs.polymarket.com/developers/CLOB/orders/create-order:

> **"All orders are represented as 'limit' orders, but 'market' orders are also supported. To place a market order, simply ensure your price is marketable against current resting limit orders."**

**There is no separate "market order" type** - you create limit orders with aggressive prices!

---

## The Correct Way (Official Docs)

```python
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

# Create a limit order with marketable price
order_args = OrderArgs(
    price=0.01,      # Price per share (4 decimals max)
    size=5.0,        # Number of shares (4 decimals max)
    side=BUY,
    token_id="..."
)

# Sign the order
signed_order = client.create_order(order_args)

# Post the order
resp = client.post_order(signed_order, OrderType.FOK)  # FOK for immediate execution
```

---

## What We Changed

### 1. Removed MarketOrderArgs

**Before (WRONG):**
```python
from py_clob_client.clob_types import OrderArgs, OrderType, MarketOrderArgs

order_args = MarketOrderArgs(
    token_id=token_id,
    amount=amount_usdc,
    side=BUY,
    order_type=OrderType.FOK
)
order = self.client.create_market_order(order_args)
response = self.client.post_order(order, OrderType.FOK)
```

**After (CORRECT):**
```python
from py_clob_client.clob_types import OrderArgs, OrderType

order_args = OrderArgs(
    price=0.99,      # Aggressive buy price
    size=size,       # Calculated from USDC amount
    side=BUY,
    token_id=token_id
)
signed_order = self.client.create_order(order_args)
response = self.client.post_order(signed_order, OrderType.FOK)
```

### 2. Market Buy Orders - Use Aggressive Price

**For BUY orders**: Use price = 0.99 (willing to pay up to 99 cents per share)

```python
def create_market_buy_order(self, token_id: str, amount_usdc: float):
    # Calculate size from USDC amount
    price = 0.99  # Aggressive buy price
    size = amount_usdc / price

    # Round to 4 decimals each
    price = round(price, 4)
    size = round(size, 4)

    # Create limit order with marketable price
    order_args = OrderArgs(
        price=price,
        size=size,
        side=BUY,
        token_id=token_id
    )

    signed_order = self.client.create_order(order_args)
    response = self.client.post_order(signed_order, OrderType.FOK)
```

### 3. Market Sell Orders - Use Aggressive Price

**For SELL orders**: Use price = 0.01 (willing to sell for as low as 1 cent per share)

```python
def create_market_sell_order(self, token_id: str, size: float):
    # Use aggressive sell price
    price = 0.01

    # Round to 4 decimals each
    price = round(price, 4)
    size = round(size, 4)

    # Create limit order with marketable price
    order_args = OrderArgs(
        price=price,
        size=size,
        side=SELL,
        token_id=token_id
    )

    signed_order = self.client.create_order(order_args)
    response = self.client.post_order(signed_order, OrderType.FOK)
```

---

## Why This Fixes the Decimal Error

**The error was:**
```
invalid amounts, the buy orders maker amount supports a max accuracy of 4 decimals,
taker amount a max of 2 decimals
```

**Problem with MarketOrderArgs:**
- Internal conversion from `amount` to `makerAmount`/`takerAmount` had precision issues
- Library might not round correctly

**Solution with OrderArgs:**
- We explicitly provide `price` and `size` (both 4 decimals max)
- CLOB calculates `makerAmount` and `takerAmount` correctly
- Matches official documentation exactly

---

## Decimal Precision Summary

| Field | Max Decimals | Example |
|-------|--------------|---------|
| price | 4 | 0.9900 |
| size | 4 | 1.0101 |
| makerAmount | 4 (shares) | 1.0203 |
| takerAmount | 2 (USDC) | 1.02 |

**By using OrderArgs:**
- We set `price` and `size` to 4 decimals ✓
- CLOB API calculates amounts correctly ✓
- No decimal precision errors ✓

---

## Order Type: FOK (Fill-or-Kill)

From official docs:

> **FOK**: A Fill-Or-Kill order is a market order to buy (in dollars) or sell (in shares) that must be executed immediately in its entirety; otherwise, the entire order will be cancelled.

**Perfect for market orders:**
- Executes immediately ✓
- Either fills completely or cancels ✓
- No partial fills sitting in orderbook ✓

**vs GTC (Good-Til-Cancelled):**
- For passive limit orders
- Sits in orderbook until filled
- NOT appropriate for market orders

---

## Complete Flow

### Market BUY Order

```
1. User wants to spend: 1.00 USDC
2. Calculate shares: 1.00 / 0.99 = 1.0101 shares
3. Round: price=0.9900, size=1.0101
4. Create OrderArgs(price=0.9900, size=1.0101, side=BUY, token_id=...)
5. Sign: signed_order = client.create_order(order_args)
6. Post: client.post_order(signed_order, OrderType.FOK)
7. Result: Order executes immediately at best available price
```

### Market SELL Order

```
1. User wants to sell: 1.0101 shares
2. Use aggressive price: 0.01
3. Round: price=0.0100, size=1.0101
4. Create OrderArgs(price=0.0100, size=1.0101, side=SELL, token_id=...)
5. Sign: signed_order = client.create_order(order_args)
6. Post: client.post_order(signed_order, OrderType.FOK)
7. Result: Order executes immediately at best available price
```

---

## What Changed in Code

**File**: `src/core/polymarket.py`

### Changes:

1. ✅ Removed `MarketOrderArgs` import
2. ✅ Rewrote `create_market_buy_order()` to use `OrderArgs`
3. ✅ Rewrote `create_market_sell_order()` to use `OrderArgs`
4. ✅ Use aggressive prices (0.99 for BUY, 0.01 for SELL)
5. ✅ Round price and size to 4 decimals each
6. ✅ Use `create_order()` instead of `create_market_order()`
7. ✅ Use `FOK` order type for immediate execution

---

## Expected Output

**Before (ERROR):**
```
Creating market BUY order: 1.00 USDC for token 3494104851808530...
[ERROR] Error placing market buy order: PolyApiException[status_code=400,
error_message={'error': 'invalid amounts, the buy orders maker amount
supports a max accuracy of 4 decimals, taker amount a max of 2 decimals'}]
```

**After (SUCCESS):**
```
Creating market BUY order: 1.00 USDC for token 3494104851808530...
  Price: 0.9900, Size: 1.0101 shares
[OK] Market buy order placed: order_abc123def456
```

---

## Summary

**Root Issue:**
- Used non-standard `MarketOrderArgs` approach
- Not following official Polymarket documentation

**Solution:**
- ✅ Use official `OrderArgs` approach
- ✅ Create limit orders with aggressive prices
- ✅ Use `create_order()` + `post_order()` as documented
- ✅ Proper decimal rounding (4 decimals for price and size)
- ✅ Use `FOK` order type for immediate execution

**Following:**
- ✅ Official Polymarket CLOB API documentation
- ✅ Official py-clob-client examples
- ✅ Best practices for market order execution

**This should completely resolve the decimal precision error!**
