# Decimal Precision Fix

## Issue

Orders were failing with error:
```
invalid amounts, the buy orders maker amount supports a max accuracy of 4 decimals,
taker amount a max of 2 decimals
```

**Example failed amounts:** 1.34, 1.98, 1.92 USDC

Even though these appear to have 2 decimals, floating-point arithmetic can create numbers with more precision (e.g., `1.3400000000000001`).

---

## Root Cause

Polymarket API has strict decimal precision requirements:
- **Taker amount** (USDC spent in market orders): Max 2 decimals
- **Maker amount** (shares/price in limit orders): Max 4 decimals

The bot was passing raw float values without rounding, causing precision errors.

---

## Fix Applied

### 1. Market Buy Orders (`create_market_buy_order`)

**File:** `src/core/polymarket.py:228`

**Before:**
```python
order_args = MarketOrderArgs(
    token_id=token_id,
    amount=amount_usdc,  # Could have >2 decimals
    side=BUY
)
```

**After:**
```python
# Round amount to 2 decimals (Polymarket taker amount max precision)
amount_usdc = round(amount_usdc, 2)

order_args = MarketOrderArgs(
    token_id=token_id,
    amount=amount_usdc,  # Now exactly 2 decimals
    side=BUY
)
```

---

### 2. Limit Orders (`create_limit_order`)

**File:** `src/core/polymarket.py:272`

**Before:**
```python
order_args = OrderArgs(
    price=price,
    size=size,
    side=BUY if side == "BUY" else SELL,
    token_id=token_id
)
```

**After:**
```python
# Round to Polymarket precision requirements (maker amount max 4 decimals)
price = round(price, 4)
size = round(size, 4)

order_args = OrderArgs(
    price=price,
    size=size,
    side=BUY if side == "BUY" else SELL,
    token_id=token_id
)
```

---

## Testing

Run the bot and verify orders execute successfully:

```bash
python run_bot.py
```

**Expected output:**
```
Creating market BUY order: 1.34 USDC for token...
[OK] Market buy order placed: order_id_here
```

**No more errors:**
- ❌ "invalid amounts, the buy orders maker amount supports a max accuracy of 4 decimals"
- ❌ Decimal precision errors

---

## Summary

✅ Market orders: Round USDC amount to 2 decimals
✅ Limit orders: Round price and size to 4 decimals
✅ Complies with Polymarket API requirements
✅ Orders should now execute successfully

---

## Next Steps

1. Run bot for full 15-minute cycle
2. Verify orders execute at 13:00
3. Confirm meta-learning strategy tracking records trades
4. Monitor for successful resolution at 15:00
