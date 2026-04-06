# Polymarket Settlement Flow - Official Documentation vs Bot Implementation

## Understanding the Official Settlement Process

Based on the official Polymarket documentation, here's how the **actual** order and settlement flow works:

---

## Phase 1: Order Placement

### Official Process
```python
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs
from py_clob_client.constants import BUY

# 1. Place order via CLOB API
order = client.create_and_post_order(OrderArgs(
    token_id=token_id,
    price=0.50,
    size=10,  # shares
    side=BUY
))

# Order is now OPEN
# Response includes: order_id, status="LIVE"
```

**Key Points**:
- Order placed immediately returns order_id
- Status: `LIVE` (open) → `MATCHED` (filled) → Market closes → `closed=true`
- USDC deducted immediately (cost = price × size)
- You receive outcome tokens (YES or NO)

---

## Phase 2: Order Tracking (Active Orders)

### Official Process
```python
# Get order status
order_status = client.get_order(order_id)

# Possible statuses:
# - "LIVE": Order is open (not filled yet)
# - "MATCHED": Order has been filled
# - "CANCELLED": Order was cancelled
```

**Key Points**:
- Active orders are those with status `LIVE` or `MATCHED` but market not closed yet
- Once MATCHED, you hold outcome tokens (not USDC)
- Tokens are worth $0 until market resolves

---

## Phase 3: Market Resolution (Settlement)

### Official Process - Wait Time Required!

```python
# Step 1: Wait for market to close (15 minutes for 15m markets)
# Markets don't resolve instantly!

# Step 2: Check if market is resolved
market = client.get_market(condition_id)

if market["closed"]:
    # Market has resolved
    for token in market["tokens"]:
        if token["winner"]:
            print(f"Winning outcome: {token['outcome']}")  # "Yes" or "No"
            print(f"Winning token_id: {token['token_id']}")
```

**CRITICAL: Resolution Wait Time**
- After 15 minutes, market **does not resolve instantly**
- There is a **delay** while Chainlink oracle fetches final price
- According to docs: Resolution can take **30-90 seconds** after market close
- Bot should **wait and poll** for resolution

---

## Phase 4: Redemption (Getting USDC Back)

### Official Process

```python
# If you hold winning tokens, redeem them for USDC
# This is a SEPARATE on-chain transaction!

# Option 1: Use CTF to redeem (for proxy wallets)
from encode import encodeRedeem

# Redeem winning tokens for USDC
redeem_data = encodeRedeem(USDC_ADDRESS, condition_id)
# Execute via proxy wallet...

# Option 2: Polymarket auto-redeems after ~24-48 hours
# But for immediate access, must redeem manually
```

**Key Points**:
- Winning tokens ≠ USDC automatically
- Must call `redeem()` to convert tokens → USDC
- Redemption is an on-chain transaction (costs gas for EOA wallets)
- Proxy wallets have automatic redemption after delay

---

## Complete Official Flow Diagram

```
┌─────────────────────────────────────────────────────┐
│ Phase 1: Order Placement                            │
└─────────────────────────────────────────────────────┘
User places order via CLOB API
    ↓
Order status: LIVE (open)
    ↓
Order gets MATCHED (filled)
    ↓
USDC deducted, Outcome tokens received
    ↓
Status: MATCHED, Market: open

┌─────────────────────────────────────────────────────┐
│ Phase 2: Active Orders (0-15 minutes)               │
└─────────────────────────────────────────────────────┘
Hold outcome tokens (YES or NO)
    ↓
Tokens currently worth $0 (no resolution yet)
    ↓
Can sell tokens before market closes for early exit
    ↓
Market countdown: 15:00 → 14:00 → ... → 0:00

┌─────────────────────────────────────────────────────┐
│ Phase 3: Market Close → Resolution (30-90s delay)   │
└─────────────────────────────────────────────────────┘
Market timer reaches 0:00
    ↓
⏱️ WAIT: Chainlink oracle fetches final price (30-90s)
    ↓
Market status: closed=false → closed=true
    ↓
Winning outcome determined (UP or DOWN)
    ↓
Winner token marked: tokens[].winner=true

┌─────────────────────────────────────────────────────┐
│ Phase 4: Redemption (Manual or Auto)                │
└─────────────────────────────────────────────────────┘
If holding winning tokens:
    ↓
Option A: Manual redemption (immediate)
    ├─ Call redeem() via CTF contract
    ├─ Winning tokens → USDC (1 token = $1)
    └─ Gas cost: ~$0.02 (EOA) or $0 (proxy)
    ↓
Option B: Auto-redemption (24-48h delay)
    └─ Polymarket redeems automatically

If holding losing tokens:
    └─ Tokens worth $0, cannot redeem
```

---

## Bot Current Implementation vs Official Flow

### ✅ What Bot Does Correctly

| Phase | Official Flow | Bot Implementation | Status |
|-------|--------------|-------------------|--------|
| **Order Placement** | create_and_post_order() | market_15m.place_prediction() | ✅ |
| **Order Tracking** | get_order(order_id) | order_tracker.track_order() | ✅ |
| **Active Orders** | Status=MATCHED & market.closed=false | order_tracker.active_orders | ✅ |

### ❌ What Bot Does Incorrectly

| Phase | Official Flow | Bot Implementation | Problem |
|-------|--------------|-------------------|---------|
| **Resolution Wait** | Wait 30-90s after close | time.sleep(15) TOTAL | ❌ Too short |
| **Resolution Check** | Poll market.closed & winner | Assumed instant | ❌ No polling |
| **Positions Awaiting** | Tokens held until redeemed | Not tracked | ❌ Missing phase |
| **Balance Update** | After redemption | Assumed immediate | ❌ Wrong timing |

---

## Critical Issues in Bot

### Issue 1: Insufficient Wait Time ❌

**Current Code** (`src/bot.py:771`):
```python
def background_settlement(self, placed_bets, start_prices):
    logger.info(f"[SETTLEMENT] Starting settlement for {len(placed_bets)} bets")
    time.sleep(15)  # Wait for market resolution
    logger.info(f"[SETTLEMENT] Waited 15s, now settling...")
```

**Problem**: Only waits 15 seconds total!

**Official Flow**:
- 15 minutes = market duration (900 seconds)
- +30-90 seconds = resolution delay
- **Total: 930-990 seconds from market start**

**Bot starts settlement thread at order placement, so should wait**:
- If placed at second 0: Wait 900s (market duration) + 60s (resolution) = 960s
- If placed at second 600: Wait 300s (remaining) + 60s (resolution) = 360s

### Issue 2: No Resolution Polling ❌

**Current Code**:
```python
# After 15s wait, assumes market is resolved
actual = self.market_15m.check_resolution(coin, bet['start_price'], final_p)
```

**Problem**: Doesn't check if market.closed=true!

**Correct Implementation** (from docs):
```python
# Poll until market resolves
max_wait = 120  # 2 minutes max wait
poll_interval = 5  # Check every 5s
waited = 0

while waited < max_wait:
    market = client.get_market(condition_id)
    if market["closed"]:
        # Market resolved!
        for token in market["tokens"]:
            if token["winner"]:
                winning_outcome = token["outcome"]  # "Yes" or "No"
                break
        break
    time.sleep(poll_interval)
    waited += poll_interval

if not market["closed"]:
    logger.error("Market did not resolve in time!")
```

### Issue 3: Missing "Positions Awaiting Settlement" ❌

**Current State**: This section never populates because:
1. Bot doesn't track tokens held (outcome tokens)
2. Bot saves trades only after assumed resolution
3. No intermediate "awaiting redemption" state

**Correct State Machine**:
```
OPEN → MATCHED → AWAITING_RESOLUTION → RESOLVED → AWAITING_REDEMPTION → REDEEMED
```

**Bot's State Machine**:
```
OPEN → MATCHED → [assumes instant resolution] → SAVED
```

Missing states: AWAITING_RESOLUTION, AWAITING_REDEMPTION

### Issue 4: Balance Update Timing ❌

**Current Code**:
```python
# Assumes balance updates immediately after resolution check
self.balance = self.wallet.get_usdc_balance()
```

**Problem**: Balance only updates after redemption (not resolution)!

**Correct Flow**:
1. Order placed: USDC -$X (immediate)
2. Market resolves: Balance unchanged (hold tokens)
3. Redeem tokens: USDC +$Y (if won)
4. Check balance: Now reflects redemption

**Bot needs**:
- Track tokens held (not just USDC balance)
- Wait for redemption (manual or auto)
- Then update balance

---

## Recommended Fix: Correct Settlement Flow

### Step 1: Calculate Proper Wait Time

```python
def background_settlement(self, placed_bets, start_prices):
    """
    Settlement timeline:
    - Orders placed during SNIPE phase (last 5-10 min)
    - Market duration: 15 minutes (900s) from start
    - Resolution delay: ~60-90s after market close
    """

    # Calculate time until market close
    market_start_time = self.active_round_end - 900  # 15 min before round end
    time_elapsed = time.time() - market_start_time
    time_until_close = max(0, 900 - time_elapsed)

    # Add resolution delay
    resolution_delay = 90  # Conservative: 90s
    total_wait = time_until_close + resolution_delay

    logger.info(f"[SETTLEMENT] Waiting {total_wait:.0f}s for market close + resolution")
    time.sleep(total_wait)
```

### Step 2: Poll for Resolution

```python
def wait_for_market_resolution(self, condition_id, max_wait=120):
    """Poll CLOB API until market resolves"""
    poll_interval = 5
    waited = 0

    while waited < max_wait:
        try:
            market = self.polymarket.client.get_market(condition_id)

            if market.get("closed"):
                # Market resolved!
                winning_outcome = None
                for token in market.get("tokens", []):
                    if token.get("winner"):
                        winning_outcome = token.get("outcome")  # "Yes" or "No"
                        break

                logger.info(f"Market resolved: Winner = {winning_outcome}")
                return winning_outcome

        except Exception as e:
            logger.error(f"Error checking market resolution: {e}")

        time.sleep(poll_interval)
        waited += poll_interval

    logger.error(f"Market did not resolve after {max_wait}s")
    return None
```

### Step 3: Track Tokens Held (Positions Awaiting Settlement)

```python
def track_tokens_held(self, order_id, token_id, shares):
    """Track outcome tokens held (not yet redeemed)"""
    self.tokens_held[order_id] = {
        'token_id': token_id,
        'shares': shares,
        'timestamp': datetime.now().isoformat(),
        'status': 'awaiting_resolution'
    }

def update_tokens_status(self, order_id, status):
    """Update token status: awaiting_resolution → resolved → redeemed"""
    if order_id in self.tokens_held:
        self.tokens_held[order_id]['status'] = status
```

### Step 4: Display Tokens in "Positions Awaiting Settlement"

```python
def _get_pending_settlement_text(self) -> Text:
    """Show tokens held awaiting resolution or redemption"""
    text = Text()

    # Tokens awaiting resolution (market not closed yet)
    awaiting_resolution = [
        t for t in self.tokens_held.values()
        if t['status'] == 'awaiting_resolution'
    ]

    # Tokens awaiting redemption (market closed, tokens not redeemed)
    awaiting_redemption = [
        t for t in self.tokens_held.values()
        if t['status'] == 'resolved'
    ]

    if awaiting_resolution:
        text.append("Awaiting Market Resolution:\n", style="bold yellow")
        for token in awaiting_resolution:
            text.append(f"  {token['coin']} {token['direction']}")
            text.append(f" ({token['shares']:.2f} tokens)\n", style="cyan")

    if awaiting_redemption:
        text.append("\nAwaiting Redemption:\n", style="bold green")
        for token in awaiting_redemption:
            text.append(f"  {token['coin']} {token['direction']}")
            text.append(f" (Won! {token['shares']:.2f} → ${token['shares']:.2f})\n", style="green")

    return text
```

---

## Summary: What Needs to Change

### Critical Fixes Required

1. **✅ Active Orders** - Already working correctly

2. **❌ Settlement Wait Time** - FIX REQUIRED
   - Current: 15s total
   - Correct: ~900s (time until market close) + 90s (resolution delay)

3. **❌ Resolution Polling** - FIX REQUIRED
   - Current: Assumes instant resolution
   - Correct: Poll `get_market()` until `closed=true`

4. **❌ Positions Awaiting Settlement** - FIX REQUIRED
   - Current: Never populates
   - Correct: Track tokens from MATCHED → RESOLVED → REDEEMED

5. **❌ Balance Update Timing** - FIX REQUIRED
   - Current: Checks immediately after "resolution"
   - Correct: Check after redemption (or accept 24-48h delay)

---

## Bot Flow Comparison

### Current Bot (Incorrect)
```
Order placed
    ↓
[Active Orders shows order]
    ↓
Wait 15s
    ↓
Assume resolved
    ↓
Save trade
    ↓
Check balance (wrong timing!)
```

### Correct Flow (Per Official Docs)
```
Order placed
    ↓
[Active Orders: status=MATCHED, tokens held]
    ↓
Wait until market close (900s from start)
    ↓
Wait for resolution (30-90s)
    ↓
[Positions Awaiting Settlement: tokens awaiting redemption]
    ↓
Poll get_market() until closed=true
    ↓
Get winning outcome
    ↓
[Positions Awaiting Settlement: won X tokens, awaiting redemption]
    ↓
Redeem tokens (manual or auto 24-48h)
    ↓
Balance updates
    ↓
Save trade with final P&L
```

---

## Implementation Priority

### High Priority (Breaks Functionality)
1. **Fix settlement wait time** - Currently wrong by 900+ seconds
2. **Add resolution polling** - Currently assumes instant (fails)
3. **Track token states** - Currently missing entire phase

### Medium Priority (UX Issues)
1. **Display tokens awaiting settlement** - Section never populates
2. **Balance update after redemption** - Currently checks too early

### Low Priority (Nice to Have)
1. **Auto-redemption tracking** - Know when Polymarket will redeem
2. **Manual redemption trigger** - Redeem immediately vs wait

---

## Conclusion

The bot's **Active Orders tracking is correct**, but the **settlement process is fundamentally broken** because it:

1. **Waits too short** (15s vs 900s+)
2. **Doesn't poll for resolution** (assumes instant)
3. **Missing token tracking phase** (MATCHED → RESOLVED → REDEEMED)
4. **Checks balance at wrong time** (before redemption)

The official documentation makes clear that:
- Markets don't resolve instantly (30-90s delay)
- Must poll `get_market()` to check resolution
- Tokens must be redeemed before balance updates
- There are distinct phases that bot currently collapses into one

**This explains why "Positions Awaiting Settlement" never shows anything** - the bot is missing 2-3 entire phases of the official flow!
