# CLI Active Orders & Positions Awaiting Settlement - Complete Analysis

## Overview

Analyzing two key sections in the "Execution Log & Positions" panel:
1. **Active Orders** - Currently open positions
2. **Positions Awaiting Settlement** - Trades waiting for market resolution

---

## Section 1: Active Orders

### Display Location
**File**: `src/bot.py`, lines 376-410
**Panel**: "Execution Log & Positions"
**Subsection**: "Active Orders"

### Code Implementation

```python
# Get active orders based on mode
if self.learning_mode and self.learning_simulator:
    # Learning mode: Show virtual positions
    active_orders = list(self.learning_simulator.virtual_positions.values())
else:
    # Real mode: Show CLOB orders
    active_orders = self.order_tracker.get_active_orders() if hasattr(self, 'order_tracker') else []

if active_orders:
    for order in active_orders[:5]:  # Show top 5
        coin = order.get('coin', 'UNKNOWN')
        direction = order.get('direction', 'UP')
        amount = order.get('amount', 0)

        # Calculate age
        order_time = datetime.fromisoformat(order['timestamp'])
        age_seconds = int((datetime.now() - order_time).total_seconds())

        # Display with mode tag
        mode_tag = " [VIRTUAL]" if self.learning_mode else ""
        orders_text.append(
            f"{coin} {direction} ${amount:.2f} ({age_seconds}s ago){mode_tag}\n",
            style=color
        )
else:
    mode_prefix = "virtual " if self.learning_mode else ""
    orders_text = Text(f"No active {mode_prefix}orders", style="italic dim")
```

---

## Real Mode - Active Orders

### Data Source
**Source**: `order_tracker.active_orders`
**Type**: `Dict[str, Dict]` (order_id → order_data)

### Data Flow

```
Order placed via CLOB API
    ↓
order_tracker.track_order(order_id, coin, direction, amount, ...)
    ↓
Stored in: order_tracker.active_orders[order_id] = {
    'order_id': order_id,
    'coin': coin,
    'direction': direction,
    'amount': amount,
    'token_id': token_id,
    'start_price': start_price,
    'timestamp': datetime.now().isoformat(),
    'status': 'open'
}
    ↓
order_tracker.get_active_orders() → list(active_orders.values())
    ↓
Dashboard displays active orders
```

### Updates

**Added to tracker** (on order placement):
```python
# In process_coin_sniping():
if not self.learning_mode:
    self.order_tracker.track_order(
        order_id=order.get('order_id'),
        coin=coin,
        direction=direction,
        amount=bet_amt,
        token_id=token_id,
        start_price=self.start_prices.get(coin, 0)
    )
```

**Removed from tracker** (on settlement):
```python
# In background_settlement():
order_id = bet.get('order_id')
if order_id and hasattr(self, 'order_tracker'):
    if order_id in self.order_tracker.active_orders:
        del self.order_tracker.active_orders[order_id]
```

**Also removed** (on FILLED status):
```python
# In order_tracker.update_orders():
if order_status.get('status') == 'FILLED':
    del self.active_orders[order_id]
```

### Display Example
```
Active Orders:
  BTC UP $0.50 (45s ago)
  ETH DOWN $0.30 (12s ago)
```

### Status: ✅ **CORRECT**

**Verification**:
- ✅ Orders added when placed via CLOB API
- ✅ Orders removed when settled
- ✅ get_active_orders() returns current dict values
- ✅ Display shows coin, direction, amount, age
- ✅ No [VIRTUAL] tag in real mode

---

## Learning Mode - Active Orders

### Data Source
**Source**: `learning_simulator.virtual_positions`
**Type**: `Dict[str, Dict]` (order_id → position_data)

### Data Flow

```
Virtual order simulated
    ↓
learning_simulator.simulate_order(coin, direction, amount, ...)
    ↓
Stored in: learning_simulator.virtual_positions[order_id] = {
    'order_id': order_id,
    'coin': coin,
    'direction': direction,
    'amount': amount,
    'token_id': token_id,
    'start_price': start_price,
    'current_price': current_price,
    'confidence': confidence,
    'entry_price': estimated_price,
    'shares': estimated_shares,
    'timestamp': datetime.now().isoformat(),
    'status': 'simulated_open'
}
    ↓
list(virtual_positions.values()) → active_orders
    ↓
Dashboard displays virtual positions
```

### Updates

**Added to simulator** (on virtual order):
```python
# In process_coin_sniping():
if self.learning_mode and self.learning_simulator:
    order = self.learning_simulator.simulate_order(
        coin=coin,
        direction=direction,
        amount=bet_amt,
        ...
    )
    # Automatically added to virtual_positions
```

**Removed from simulator** (on settlement):
```python
# In learning_simulator.settle_position():
del self.virtual_positions[order_id]
```

### Display Example
```
Active Orders:
  BTC UP $0.50 (45s ago) [VIRTUAL]
  ETH DOWN $0.30 (12s ago) [VIRTUAL]
```

### Status: ✅ **CORRECT**

**Verification**:
- ✅ Virtual positions added when simulated
- ✅ Virtual positions removed when settled
- ✅ list(virtual_positions.values()) returns current positions
- ✅ Display shows coin, direction, amount, age
- ✅ Shows [VIRTUAL] tag in learning mode

---

## Section 2: Positions Awaiting Settlement

### Display Location
**File**: `src/bot.py`, lines 628-686
**Method**: `_get_pending_settlement_text()`
**Panel**: "Execution Log & Positions"
**Subsection**: "Positions Awaiting Settlement"

### Code Implementation

```python
def _get_pending_settlement_text(self) -> Text:
    """Get text showing positions waiting for market settlement"""
    text = Text()
    pending_positions = []

    # Check real trades
    if hasattr(self, 'history_manager'):
        recent_trades = self.history_manager.history[-20:]
        for trade in recent_trades:
            if 'final_price' not in trade or trade.get('final_price') is None:
                pending_positions.append({**trade, 'mode': 'REAL'})

    # Check learning trades
    if self.learning_mode and hasattr(self, 'learning_persistence'):
        recent_learning = self.learning_persistence.load_trades()[-20:]
        for trade in recent_learning:
            if 'final_price' not in trade or trade.get('final_price') is None:
                pending_positions.append({**trade, 'mode': 'VIRTUAL'})

    if pending_positions:
        for pos in pending_positions[-5:]:  # Show last 5
            coin = pos.get('coin', '?')
            direction = pos.get('prediction', '?')
            amount = pos.get('cost', 0.0)
            mode = pos.get('mode', 'REAL')

            mode_tag = " [VIRTUAL]" if mode == 'VIRTUAL' else ""
            text.append(
                f"  {coin} {direction} ${amount:.2f} (placed {age_str} ago){mode_tag}\n",
                style=color
            )
    else:
        text.append("  No positions awaiting settlement\n", style="dim italic")

    return text
```

---

## Real Mode - Positions Awaiting Settlement

### Data Source
**Source**: `history_manager.history` (last 20 trades)
**Filter**: Trades without `final_price` field

### Logic

**When trade is added** (on order placement):
```python
# Trade saved WITHOUT final_price
trade_data = {
    'coin': coin,
    'prediction': direction,
    'cost': amount,
    'timestamp': datetime.now().isoformat()
    # NO 'final_price' field
}
history_manager.save_trade(trade_data)
```

**When settlement happens** (15 minutes later):
```python
# Trade updated WITH final_price
trade_data = {
    **bet,
    'won': won,
    'final_price': final_p,  # ← Added here
    'timestamp': datetime.now().isoformat()
}
history_manager.save_trade(trade_data)
```

### Data Flow

```
Order placed
    ↓
Trade saved to history WITHOUT final_price
    ↓
Dashboard checks history[-20:] for trades missing final_price
    ↓
Displays as "Awaiting Settlement"
    ↓
Market closes (15 min)
    ↓
Settlement adds final_price
    ↓
No longer appears in "Awaiting Settlement"
```

### Status: ⚠️ **ISSUE FOUND**

**Problem**: Real mode trades are saved to history in **two stages**:

1. **Stage 1** (on placement): Partial trade data (no final_price)
2. **Stage 2** (on settlement): Complete trade data (with final_price)

**But looking at settlement code** (line 827-836):
```python
# Save trade with complete information including final_price
trade_data = {
    **bet,
    'won': won,
    'final_price': final_p,
    'timestamp': datetime.now().isoformat()
}
logger.info(f"[REAL] Saving trade to history: {coin} {bet.get('prediction')} - {'WON' if won else 'LOST'}")
self.history_manager.save_trade(trade_data)
```

**This only saves ONCE at settlement, not at placement!**

**Expected Behavior**:
- Trades should appear in "Awaiting Settlement" between placement and settlement

**Actual Behavior**:
- Trades saved only after settlement (with final_price already present)
- Will NOT appear in "Awaiting Settlement" section

### Verification

Let me check if trades are saved at placement anywhere:

```bash
grep -n "save_trade" src/bot.py
```

**Result**: Trade only saved at settlement (line 836), not at placement.

**Conclusion**: ❌ **Real mode trades will NOT appear in "Positions Awaiting Settlement"**

---

## Learning Mode - Positions Awaiting Settlement

### Data Source
**Source**: `learning_persistence.load_trades()` (last 20 trades)
**Filter**: Trades without `final_price` field

### Logic

**When virtual order placed**:
- NOT saved to learning_trades.json immediately
- Only saved during settlement

**When settlement happens**:
```python
# In background_settlement():
trade_record = self.learning_simulator.settle_position(
    order_id=order_id,
    final_price=final_p,
    start_price=bet['start_price']
)

# Trade record created WITH final_price already
if trade_record:
    self.learning_persistence.save_trade(trade_record)
```

**Trade record structure** (from learning_simulator.settle_position()):
```python
trade_record = {
    **position,
    'final_price': final_price,  # ← Already present
    'actual_outcome': actual_outcome,
    'won': won,
    'pnl': pnl,
    'settled_at': datetime.now().isoformat()
}
```

### Status: ❌ **SAME ISSUE**

**Problem**: Learning mode trades also saved only at settlement with final_price already present.

**Conclusion**: ❌ **Learning mode trades will NOT appear in "Positions Awaiting Settlement"**

---

## Summary Analysis

### Active Orders Section

| Aspect | Real Mode | Learning Mode | Status |
|--------|-----------|---------------|--------|
| **Data Source** | order_tracker.active_orders | learning_simulator.virtual_positions | ✅ |
| **Added When** | Order placed via CLOB | Virtual order simulated | ✅ |
| **Removed When** | Settlement OR FILLED status | Settlement | ✅ |
| **Display Format** | Coin, direction, amount, age | Same + [VIRTUAL] tag | ✅ |
| **Correct Linking** | YES | YES | ✅ |

**Verdict**: ✅ **WORKING CORRECTLY** - Both modes properly track active orders

---

### Positions Awaiting Settlement Section

| Aspect | Real Mode | Learning Mode | Status |
|--------|-----------|---------------|--------|
| **Data Source** | history_manager.history[-20:] | learning_persistence.load_trades()[-20:] | ✅ |
| **Filter Logic** | Missing 'final_price' | Missing 'final_price' | ✅ |
| **Trade Saved When** | ❌ Only at settlement | ❌ Only at settlement | ❌ |
| **Has final_price When Saved** | ✅ YES (always) | ✅ YES (always) | ❌ |
| **Will Display Trades** | ❌ NO (never missing final_price) | ❌ NO (never missing final_price) | ❌ |
| **Correct Linking** | ❌ NO (never populates) | ❌ NO (never populates) | ❌ |

**Verdict**: ❌ **NOT WORKING** - Section will always show "No positions awaiting settlement"

---

## Root Cause

### Design Intent vs Implementation

**Intended Flow**:
```
Order Placed
    ↓
Trade saved WITHOUT final_price ← Should happen here
    ↓
[Appears in "Awaiting Settlement" for 15 minutes]
    ↓
Market Closes
    ↓
Trade UPDATED with final_price
    ↓
[Removed from "Awaiting Settlement"]
```

**Actual Flow**:
```
Order Placed
    ↓
Tracked in active_orders (correct)
    ↓
[15 minutes pass]
    ↓
Market Closes
    ↓
Trade saved WITH final_price ← Happens here
    ↓
[Never appears in "Awaiting Settlement" because final_price already present]
```

### Why This Happens

**Real Mode** (`src/bot.py` lines 827-836):
```python
# Only place where trade is saved
trade_data = {
    **bet,
    'won': won,
    'final_price': final_p,  # ← Already included
    'timestamp': datetime.now().isoformat()
}
self.history_manager.save_trade(trade_data)
```

**Learning Mode** (`src/core/learning_simulator.py` lines 137-147):
```python
# Trade record created at settlement
trade_record = {
    **position,
    'final_price': final_price,  # ← Already included
    'actual_outcome': actual_outcome,
    'won': won,
    'pnl': pnl,
    ...
}
```

---

## Impact Assessment

### Functional Impact: **LOW**

**Why it's not critical**:
1. **Active Orders section works correctly** - Shows real-time open positions
2. **Trades are still tracked and saved correctly**
3. **Dashboard shows accurate data**
4. **"Awaiting Settlement" is supplementary info only**

### User Experience Impact: **MINOR**

**What users lose**:
- Can't see trades in "limbo" (placed but not settled)
- All trades appear instantly as settled (when saved)
- Less visibility into pending positions

**What users still have**:
- Active Orders (shows currently open)
- Recent Trades (shows completed)
- All stats are accurate

---

## Recommendations

### Option 1: Save Trades in Two Stages (Matches Design Intent)

#### Real Mode:
```python
# At order placement (in process_coin_sniping()):
if not self.learning_mode:
    # Save partial trade immediately
    partial_trade = {
        'order_id': order.get('order_id'),
        'coin': coin,
        'direction': direction,
        'cost': bet_amt,
        'timestamp': datetime.now().isoformat(),
        # NO final_price
    }
    self.history_manager.save_trade(partial_trade)

# At settlement (in background_settlement()):
# Update existing trade with final_price
for trade in self.history_manager.history:
    if trade.get('order_id') == order_id:
        trade['final_price'] = final_p
        trade['won'] = won
        break
self.history_manager._save_to_disk()
```

#### Learning Mode:
```python
# At virtual order (in process_coin_sniping()):
if self.learning_mode and self.learning_simulator:
    # Save partial trade immediately
    partial_trade = {
        'order_id': order.get('order_id'),
        'coin': coin,
        'direction': direction,
        'cost': bet_amt,
        'timestamp': datetime.now().isoformat(),
        # NO final_price
    }
    self.learning_persistence.save_trade(partial_trade)

# At settlement (in background_settlement()):
# Update existing trade with final_price
learning_trades = self.learning_persistence.load_trades()
for trade in learning_trades:
    if trade.get('order_id') == order_id:
        trade['final_price'] = final_p
        trade['won'] = won
        trade['pnl'] = pnl
        break
# Save updated list
```

### Option 2: Use Active Orders as "Awaiting Settlement" (Simpler)

Remove "Positions Awaiting Settlement" section entirely since "Active Orders" already shows this info.

**Rationale**:
- Active Orders = Orders placed but not settled
- This is the same as "Awaiting Settlement"
- No need for duplicate section

### Option 3: Keep Current Behavior (Do Nothing)

Accept that "Positions Awaiting Settlement" will always be empty.

**Rationale**:
- Low functional impact
- Active Orders provides same info
- Avoids complexity of two-stage saving

---

## Final Verdict

### Active Orders: ✅ **FULLY WORKING**
- Real mode: Correctly linked to order_tracker
- Learning mode: Correctly linked to virtual_positions
- Proper mode separation
- Accurate display

### Positions Awaiting Settlement: ❌ **NOT WORKING**
- Will always show "No positions awaiting settlement"
- Trades saved with final_price already present
- Never meets filter condition (missing final_price)
- Feature is non-functional in both modes

### Overall Status: ⚠️ **MOSTLY WORKING**
- Critical functionality (Active Orders) works perfectly
- Supplementary feature (Awaiting Settlement) doesn't work
- No data integrity issues
- Recommend: Keep as-is or remove non-functional section

---

## Conclusion

**Active Orders**: ✅ Production ready
**Positions Awaiting Settlement**: ❌ Non-functional but non-critical

The system correctly tracks and displays active orders in both modes. The "Positions Awaiting Settlement" section is a UI nicety that doesn't work due to trades being saved only at settlement (with final_price already present). This is a **minor cosmetic issue** that doesn't affect core functionality.
