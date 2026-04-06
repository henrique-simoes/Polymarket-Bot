# Polymarket Order Size Limits - Official Documentation

## Summary

Based on official Polymarket documentation, **YES, there are minimum order size requirements** that vary by market.

---

## Key Findings from Official Docs

### 1. Minimum Order Size Field

Markets return a `minimum_order_size` field in two places:

**From Gamma API (Market Metadata):**
```typescript
interface Market {
  minimum_order_size: number;  // Minimum shares required
  minimum_tick_size: number;   // Minimum price increment
  // ... other fields
}
```

**From CLOB API (Orderbook):**
```python
@dataclass
class OrderBookSummary:
    min_order_size: str  # Minimum shares for this market
    tick_size: str       # e.g., "0.01", "0.001"
    # ... other fields
```

### 2. Error Code

If order is too small:
- **Error:** `INVALID_ORDER_MIN_SIZE`
- **Message:** "order is invalid. Size lower than the minimum"
- **Description:** "order size must meet min size threshold requirement"

### 3. How It Works

**The minimum is in SHARES, not dollars:**
- If `minimum_order_size = 5` and price is $0.90/share
- Minimum cost = 5 shares × $0.90 = **$4.50**
- You **cannot** buy just $1 worth (only ~1.11 shares)

**Example Scenario:**
```
Market: BTC 15-minute
minimum_order_size: 5 shares
Current price: $0.90/share

User wants to buy $1 worth:
  - $1 / $0.90 = 1.11 shares
  - ❌ REJECTED: 1.11 < 5 (minimum)

User wants to buy $5 worth:
  - $5 / $0.90 = 5.55 shares  
  - ✓ ACCEPTED: 5.55 > 5 (minimum)
```

### 4. Official Documentation Quote

From `page-2026-02-02-01-46-27.md` (lines 707-718):

> "Minimum order size: Orders must meet a minimum size threshold (you'll get `INVALID_ORDER_MIN_SIZE` error if too small). The `min_order_size` is returned in the `get-book` endpoint response."
>
> "The website may handle these requirements automatically, while the API requires you to explicitly meet minimum size requirements."

---

## Current Bot Behavior

### What Bot Does Now

**File:** `src/bot.py` (lines 286-288)
```python
market_data = self.market_15m.market_cache.get(coin, {})
min_shares = market_data.get('orderMinSize', 1.1)  # ❌ WRONG FIELD NAME
min_cost = min_shares * price
```

**Problems:**
1. **Wrong field name:** Looks for `orderMinSize` but API returns `minimum_order_size`
2. **Defaults to 1.1:** If field not found, uses 1.1 shares (arbitrary guess)
3. **May violate minimum:** Could place orders that will be rejected

### Market Cache Source

**File:** `src/core/market_15m.py` (line 193)
```python
# Fetches from Gamma API and stores raw market data
self.market_cache[coin] = best_market
```

The Gamma API returns markets with `minimum_order_size` field.

---

## Fix Required

### Option 1: Read from Market Cache (Recommended)

Update field name to match API:

```python
# src/bot.py line 287
min_shares = market_data.get('minimum_order_size', 5.0)  # Use correct field name
```

### Option 2: Fetch from Orderbook (More Accurate)

Get live minimum from orderbook:

```python
def validate_trade(self, coin, price):
    # Get token ID
    tokens = self.market_15m.get_token_ids_for_coin(coin)
    if not tokens:
        return False
    
    # Get orderbook with minimum size
    token_id = tokens.get('yes') or tokens.get('no')
    orderbook = self.polymarket.get_orderbook(token_id)
    
    if orderbook and orderbook.min_order_size:
        min_shares = float(orderbook.min_order_size)
    else:
        min_shares = 5.0  # Conservative default
    
    min_cost = min_shares * price
    
    # Check if order meets minimum
    if min_cost > self.user_max_bet:
        logger.info(f"Skipped {coin}: Min cost ${min_cost:.2f} > Budget")
        return False
    
    return True
```

---

## Real-World Implications

### Scenario: User Sets $3 Budget, 3 Coins

**If minimum_order_size = 5 shares:**

| Coin | Price | Min Shares | Min Cost | Budget | Can Trade? |
|------|-------|------------|----------|--------|------------|
| BTC  | $0.90 | 5          | $4.50    | $1.00  | ❌ NO      |
| ETH  | $0.50 | 5          | $2.50    | $1.00  | ❌ NO      |
| SOL  | $0.15 | 5          | $0.75    | $1.00  | ✓ YES      |

**Result:** Only SOL can trade with $1 per-coin budget!

**If minimum_order_size = 1 share:**

| Coin | Price | Min Shares | Min Cost | Budget | Can Trade? |
|------|-------|------------|----------|--------|------------|
| BTC  | $0.90 | 1          | $0.90    | $1.00  | ✓ YES      |
| ETH  | $0.50 | 1          | $0.50    | $1.00  | ✓ YES      |
| SOL  | $0.15 | 1          | $0.15    | $1.00  | ✓ YES      |

**Result:** All coins can trade!

### Recommendation

1. **Always check `minimum_order_size` before placing order**
2. **Warn user if budget too small** for minimum order size
3. **Skip coins** that don't meet minimum instead of failing silently
4. **Display minimum cost** in UI so user can adjust budget

---

## Testing

To verify minimum order size for a market:

```python
from py_clob_client.client import ClobClient

client = ClobClient("https://clob.polymarket.com", key=private_key, chain_id=137)

# Get orderbook for a token
orderbook = client.get_order_book(token_id)

print(f"Min Order Size: {orderbook.min_order_size} shares")
print(f"Tick Size: {orderbook.tick_size}")

# Calculate minimum cost
price = 0.90  # Current market price
min_cost = float(orderbook.min_order_size) * price
print(f"Minimum cost at ${price}: ${min_cost:.2f}")
```

---

## Typical Minimum Values

Based on documentation searches:
- **Common minimum:** 1-5 shares
- **May vary by market type** (sports, crypto, politics)
- **Check per market** - don't hardcode

---

**Status:** ⚠️ NEEDS FIX
**Priority:** HIGH - Orders may be rejected
**Recommended Action:** Update field name from `orderMinSize` to `minimum_order_size`
