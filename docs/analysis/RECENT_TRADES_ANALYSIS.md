# Recent Trades CLI Section - Complete Analysis

## Overview

Analyzing the "Recent Trades" table in the CLI dashboard to verify it works correctly after settlement fixes.

**Location**: `src/bot.py`, lines 534-626

---

## Data Sources

### Real Mode
```python
# Line 551-554
if hasattr(self, 'history_manager'):
    real_trades = self.history_manager.history[-50:]
    for trade in real_trades:
        all_trades.append({**trade, 'mode': 'REAL'})
```

**Source**: `data/trade_history.json` via `TradeHistoryManager`

### Learning Mode
```python
# Line 557-560
if self.learning_mode and hasattr(self, 'learning_persistence'):
    learning_trades = self.learning_persistence.load_trades()[-50:]
    for trade in learning_trades:
        all_trades.append({**trade, 'mode': 'VIRTUAL'})
```

**Source**: `data/learning_trades.json` via `LearningPersistence`

---

## Display Fields

The Recent Trades table shows:

| Column | Field Used | Description |
|--------|-----------|-------------|
| # | Index | Row number (1-15) |
| Time | `timestamp` | HH:MM format |
| Coin | `coin` | BTC/ETH/SOL |
| Dir | `prediction` | UP/DOWN |
| Entry Price | `price` | Token entry price |
| Cost (USDC) | `cost` | Amount spent |
| Outcome | `won` | ✓ WIN / ✗ LOSS |
| P&L (USDC) | `profit` | Profit/loss |
| Status | `final_price` presence | SETTLED/PENDING |

---

## Trade Data Structure Comparison

### Real Mode Trade Structure

**Created by**: `market_15m.place_prediction()` (lines 224-229)
```python
{
    'coin': coin,
    'prediction': prediction,  # ✅
    'token_id': token_id,
    'condition_id': condition_id,
    'price': price,  # ✅ Token entry price
    'shares': shares,
    'cost': amount_usdc,  # ✅
    'order_id': order_id,
    'timestamp': datetime.now(timezone.utc)
}
```

**Added in settlement** (`bot.py` lines 898-903):
```python
trade_data = {
    **bet,  # All above fields
    'won': won,  # ✅
    'final_price': final_p,  # ✅
    'timestamp': datetime.now().isoformat(),  # Overwritten
    'start_price': bet.get('start_price')  # Added before settlement
}
```

**MISSING**: `profit` field ❌

---

### Learning Mode Trade Structure

**Created by**: `learning_simulator.simulate_order()` (lines 81-94)
```python
{
    'order_id': order_id,
    'coin': coin,  # ✅
    'direction': direction,  # ❌ NOT 'prediction'
    'amount': amount,  # ❌ NOT 'cost'
    'token_id': token_id,
    'condition_id': condition_id,
    'start_price': start_price,
    'current_price': current_price,
    'confidence': confidence,
    'entry_price': estimated_price,  # ❌ NOT 'price'
    'shares': estimated_shares,
    'timestamp': datetime.now().isoformat(),
    'status': 'simulated_open'
}
```

**Added in settlement** (`learning_simulator.py` lines 140-149):
```python
trade_record = {
    **position,  # All above fields
    'final_price': final_price,  # ✅
    'actual_outcome': actual_outcome,
    'won': won,  # ✅
    'pnl': pnl,  # ❌ NOT 'profit'
    'settled_at': settled_at,
    'mode': 'learning',
    'virtual_balance_after': virtual_balance
}
```

---

## Critical Field Mismatches

### 1. Direction Field ❌

| Mode | Field Name | Dashboard Expects |
|------|-----------|------------------|
| Real | `prediction` | `prediction` ✅ |
| Learning | `direction` | `prediction` ❌ |

**Code** (line 579):
```python
direction = trade.get('prediction', '?')
```

**Impact**: Learning mode trades show "?" for direction instead of UP/DOWN

**Example Display**:
```
# Time   Coin Dir  Entry  Cost    Outcome  P&L     Status
1 14:32  BTC  ?    $0.48  $0.50   ✓ WIN    $0.00   SETTLED
```

---

### 2. Entry Price Field ❌

| Mode | Field Name | Dashboard Expects |
|------|-----------|------------------|
| Real | `price` | `price` ✅ |
| Learning | `entry_price` | `price` ❌ |

**Code** (line 580):
```python
price = trade.get('price', 0.0)
```

**Impact**: Learning mode trades show $0.00 for entry price

---

### 3. Cost Field ❌

| Mode | Field Name | Dashboard Expects |
|------|-----------|------------------|
| Real | `cost` | `cost` ✅ |
| Learning | `amount` | `cost` ❌ |

**Code** (line 581):
```python
amount = trade.get('cost', 0.0)
```

**Impact**: Learning mode trades show $0.00 for cost

---

### 4. Profit Field ❌ (BOTH MODES BROKEN!)

| Mode | Field Name | Dashboard Expects |
|------|-----------|------------------|
| Real | ❌ MISSING | `profit` ❌ |
| Learning | `pnl` | `profit` ❌ |

**Code** (line 583):
```python
profit = trade.get('profit', 0.0)
```

**Impact**:
- Real mode: Shows $0.00 for P&L (field never calculated!)
- Learning mode: Shows $0.00 for P&L (field named 'pnl' instead)

**Stats Calculation** (persistence.py line 53):
```python
pnl = sum(t.get('profit', 0) for t in trades)
```

**Impact on Stats**: All P&L stats show $0.00 because 'profit' field doesn't exist!

---

## Status Field Analysis ✅

**Code** (line 587-596):
```python
if 'final_price' in trade:
    status = "SETTLED"
    outcome = "✓ WIN" if won else "✗ LOSS"
else:
    status = "PENDING"
    outcome = "..."
```

**Real Mode**: Trades saved with `final_price` already present (line 901)
**Learning Mode**: Trades saved with `final_price` already present (line 142)

**Result**: All trades show as "SETTLED" (correct behavior for current implementation)

**Note**: As documented in `CLI_ORDERS_SETTLEMENT_ANALYSIS.md`, trades are only saved AFTER settlement, so "PENDING" status never appears. This is by design - trades without final_price are tracked in "Active Orders" instead.

---

## Bugs Summary

### Real Mode Trades ⚠️

| Field | Status | Impact |
|-------|--------|--------|
| `coin` | ✅ Working | Shows correct coin |
| `prediction` | ✅ Working | Shows UP/DOWN correctly |
| `price` | ✅ Working | Shows entry price |
| `cost` | ✅ Working | Shows bet amount |
| `won` | ✅ Working | Shows WIN/LOSS |
| `profit` | ❌ **MISSING** | Shows $0.00 instead of actual P&L |
| `final_price` | ✅ Working | Determines SETTLED status |
| `timestamp` | ✅ Working | Shows time correctly |

**Critical Bug**: Profit never calculated for real mode!

---

### Learning Mode Trades ❌

| Field | Status | Impact |
|-------|--------|--------|
| `coin` | ✅ Working | Shows correct coin |
| `prediction` | ❌ Uses `direction` | Shows "?" instead of UP/DOWN |
| `price` | ❌ Uses `entry_price` | Shows $0.00 instead of entry price |
| `cost` | ❌ Uses `amount` | Shows $0.00 instead of bet amount |
| `won` | ✅ Working | Shows WIN/LOSS correctly |
| `profit` | ❌ Uses `pnl` | Shows $0.00 instead of actual P&L |
| `final_price` | ✅ Working | Determines SETTLED status |
| `timestamp` | ✅ Working | Shows time correctly |

**Critical Bugs**: 4 field mismatches break most of the display!

---

## Example Display (Current vs Expected)

### Current (Broken)

**Real Mode**:
```
# Time   Coin Dir  Entry  Cost    Outcome  P&L     Status
1 14:32  BTC  UP   $0.48  $0.50   ✓ WIN    $0.00   SETTLED  ← P&L wrong
2 14:17  ETH  UP   $0.52  $0.30   ✗ LOSS   $0.00   SETTLED  ← P&L wrong
```

**Learning Mode**:
```
# Time   Coin Dir  Entry  Cost    Outcome  P&L     Status
1 14:32  BTC  ?    $0.00  $0.00   ✓ WIN    $0.00   SETTLED  ← Everything broken!
2 14:17  ETH  ?    $0.00  $0.00   ✗ LOSS   $0.00   SETTLED  ← Everything broken!
```

---

### Expected (After Fix)

**Real Mode**:
```
# Time   Coin Dir  Entry  Cost    Outcome  P&L     Status
1 14:32  BTC  UP   $0.48  $0.50   ✓ WIN    +$0.42  SETTLED  ← P&L calculated
2 14:17  ETH  UP   $0.52  $0.30   ✗ LOSS   -$0.30  SETTLED  ← P&L calculated
```

**Learning Mode**:
```
# Time   Coin Dir  Entry  Cost    Outcome  P&L     Status
1 14:32  BTC  UP   $0.48  $0.50   ✓ WIN    +$0.42  SETTLED  ← All fields correct
2 14:17  ETH  UP   $0.52  $0.30   ✗ LOSS   -$0.30  SETTLED  ← All fields correct
```

---

## Fixes Required

### Fix 1: Calculate Profit for Real Mode ✅ CRITICAL

**Location**: `src/bot.py`, settlement code (around line 898-903)

**Current**:
```python
trade_data = {
    **bet,
    'won': won,
    'final_price': final_p,
    'timestamp': datetime.now().isoformat()
}
```

**Should be**:
```python
# Calculate profit
if won:
    # Win: (shares * 1.0) - cost = profit
    profit = bet.get('shares', 0) - bet.get('cost', 0)
else:
    # Loss: -cost
    profit = -bet.get('cost', 0)

trade_data = {
    **bet,
    'won': won,
    'final_price': final_p,
    'profit': profit,  # ← ADD THIS
    'timestamp': datetime.now().isoformat()
}
```

---

### Fix 2: Standardize Learning Mode Field Names ✅ CRITICAL

**Option A: Change learning_simulator to match real mode** (RECOMMENDED)

In `src/core/learning_simulator.py`, line 81-94:
```python
position = {
    'order_id': order_id,
    'coin': coin,
    'prediction': direction,  # ← RENAME from 'direction'
    'amount': amount,
    'token_id': token_id,
    'condition_id': condition_id,
    'start_price': start_price,
    'current_price': current_price,
    'confidence': confidence,
    'price': estimated_price,  # ← RENAME from 'entry_price'
    'cost': amount,  # ← ADD (duplicate of 'amount' for compatibility)
    'shares': estimated_shares,
    'timestamp': datetime.now().isoformat(),
    'status': 'simulated_open'
}
```

In `src/core/learning_simulator.py`, line 140-149:
```python
trade_record = {
    **position,
    'final_price': final_price,
    'actual_outcome': actual_outcome,
    'won': won,
    'profit': pnl,  # ← RENAME from 'pnl'
    'settled_at': datetime.now().isoformat(),
    'mode': 'learning',
    'virtual_balance_after': self.virtual_balance
}
```

**Option B: Update dashboard to handle both field names**

In `src/bot.py`, line 578-584:
```python
coin = trade.get('coin', '?')
direction = trade.get('prediction') or trade.get('direction', '?')  # ← Handle both
price = trade.get('price') or trade.get('entry_price', 0.0)  # ← Handle both
amount = trade.get('cost') or trade.get('amount', 0.0)  # ← Handle both
won = trade.get('won')
profit = trade.get('profit') or trade.get('pnl', 0.0)  # ← Handle both
```

**Recommendation**: Use Option A (standardize learning mode fields) for cleaner codebase.

---

### Fix 3: Update Stats Calculation (Already Broken)

**Location**: `src/core/persistence.py`, line 53

**Current**:
```python
pnl = sum(t.get('profit', 0) for t in trades)
```

**After Fix 1 & 2**: Will work correctly once 'profit' field exists

**Note**: Stats currently show $0.00 for all P&L because 'profit' field missing!

---

## Testing Checklist

After applying fixes:

### Real Mode
- [ ] Place real order during SNIPE phase
- [ ] Wait for settlement (~990 seconds)
- [ ] Check Recent Trades:
  - [ ] Direction shows UP or DOWN
  - [ ] Entry price shows actual token price (e.g., $0.48)
  - [ ] Cost shows bet amount (e.g., $0.50)
  - [ ] Outcome shows ✓ WIN or ✗ LOSS
  - [ ] P&L shows calculated profit (e.g., +$0.42 or -$0.50)
  - [ ] Status shows SETTLED

### Learning Mode
- [ ] Place virtual order during SNIPE phase
- [ ] Wait for settlement (~990 seconds)
- [ ] Check Recent Trades:
  - [ ] Direction shows UP or DOWN (not "?")
  - [ ] Entry price shows estimated price (e.g., $0.48)
  - [ ] Cost shows bet amount (e.g., $0.50)
  - [ ] Outcome shows ✓ WIN or ✗ LOSS
  - [ ] P&L shows calculated P&L (e.g., +$0.42 or -$0.50)
  - [ ] Status shows SETTLED (dimmed)

### Stats Panel
- [ ] All Time P&L shows non-zero value (if trades exist)
- [ ] 1 Hour P&L shows correct sum
- [ ] 24 Hours P&L shows correct sum

---

## Root Cause Analysis

### Why These Bugs Exist

1. **Profit never calculated for real mode**:
   - Settlement code just spreads `**bet` without calculating P&L
   - TradingStrategy class has profit logic but is never used
   - Stats and dashboard expect 'profit' field that doesn't exist

2. **Learning mode field name mismatches**:
   - Learning simulator was developed separately
   - Used different field names ('direction' vs 'prediction', 'pnl' vs 'profit')
   - Dashboard assumes all trades have same structure

3. **No validation or testing**:
   - No tests verify trade data structure
   - Dashboard code has no error handling for missing fields
   - Stats calculation silently returns 0 for missing 'profit'

---

## Impact Assessment

### Current State

**Real Mode**:
- ⚠️ **Medium Impact**: Trades display correctly EXCEPT P&L shows $0.00
- ⚠️ **High Impact**: All P&L stats show $0.00 (meaningless)

**Learning Mode**:
- ❌ **Critical Impact**: Recent Trades nearly unusable (4/8 fields broken)
- ❌ **High Impact**: Stats show $0.00 despite having 'pnl' field

### After Fix

**Both Modes**:
- ✅ All fields display correctly
- ✅ P&L stats accurate
- ✅ Recent Trades fully functional

---

## Conclusion

**Current Status**: ❌ **BROKEN FOR BOTH MODES**

**Real Mode**:
- Trades display correctly EXCEPT P&L
- Missing profit calculation

**Learning Mode**:
- Trades display incorrectly (4 field mismatches)
- Has P&L data but wrong field name

**Priority**: **HIGH** - This affects core user visibility into trading performance

**Recommended Action**:
1. Apply Fix 1 (calculate profit for real mode) - 5 minutes
2. Apply Fix 2 Option A (standardize learning mode fields) - 10 minutes
3. Test both modes - 20 minutes

**Total Effort**: ~35 minutes to fix completely

---

**Analysis Date**: February 3, 2026
**Status**: 🔴 CRITICAL BUGS FOUND - Fixes Required
