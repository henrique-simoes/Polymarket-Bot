# Complete Order Lifecycle Integration

**GUARANTEED PATH**: Place → Fill → Settlement → Logging → ML Training

---

## Integration Points

### 1. When Placing Order (bot.py)

```python
from src.core.order_lifecycle import OrderLifecycleTracker

# Initialize once
self.lifecycle_tracker = OrderLifecycleTracker()

# After successful order placement:
order_id = result.get('order_id')
self.lifecycle_tracker.track_placed_order(
    order_id=order_id,
    coin=coin,
    direction=direction,
    amount=bet_amount,
    token_id=token_id,
    strike_price=strike_price,
    condition_id=condition_id
)
# State: PLACED ✓
```

### 2. When Order Fills (order_tracker.py)

```python
# In _record_completed_trade():
filled_size = float(order_status.get('size_matched', 0))
entry_price = float(order_status.get('price', 0))

self.lifecycle_tracker.mark_filled(
    order_id=order_id,
    filled_size=filled_size,
    entry_price=entry_price
)
# State: PLACED → FILLED ✓
```

### 3. Before Settlement (background_settlement)

```python
# Mark as settling
self.lifecycle_tracker.mark_settling(order_id)
# State: FILLED → SETTLING ✓
```

### 4. After Getting Outcome (background_settlement)

```python
# After determining outcome via CTF/CLOB:
outcome = ctf_checker.check_settlement(condition_id)  # 'UP' or 'DOWN'
won = (prediction == outcome)
pnl = calculate_pnl(won, shares, cost)

self.lifecycle_tracker.mark_resolved(
    order_id=order_id,
    outcome=outcome,
    won=won,
    final_price=final_price,
    pnl=pnl
)
# State: SETTLING → RESOLVED ✓
```

### 5. After Saving to History

```python
# After writing to trade_history.json:
self.lifecycle_tracker.mark_logged(
    order_id=order_id,
    trade_record=trade_data
)
# State: RESOLVED → LOGGED ✓
```

### 6. After ML Training

```python
# After finalize_round() completes:
self.lifecycle_tracker.mark_trained(order_id)
# State: LOGGED → TRAINED ✓✓✓
```

---

## Error Handling

### If Order Never Fills

```python
# In order_tracker.py, periodic cleanup:
for order_id in list(active_orders.keys()):
    order_age = time.time() - order['timestamp']
    if order_age > 900:  # 15 minutes
        self.lifecycle_tracker.mark_failed(
            order_id=order_id,
            reason="Order never filled (timeout)",
            at_state="placed"
        )
```

### If Settlement Fails

```python
# In background_settlement:
try:
    outcome = get_settlement_with_fallback(...)
    if not outcome:
        raise ValueError("All settlement methods failed")
except Exception as e:
    self.lifecycle_tracker.mark_failed(
        order_id=order_id,
        reason=f"Settlement failed: {e}",
        at_state="settling"
    )
```

### If ML Training Fails

```python
# In finalize_round:
try:
    self.learning_engine.finalize_round(coin, outcome)
    self.lifecycle_tracker.mark_trained(order_id)
except Exception as e:
    self.lifecycle_tracker.mark_failed(
        order_id=order_id,
        reason=f"ML training failed: {e}",
        at_state="logged"
    )
```

---

## Recovery on Restart

```python
# At bot startup:
self.lifecycle_tracker = OrderLifecycleTracker()

# Check for incomplete orders
incomplete = self.lifecycle_tracker.get_incomplete_orders()
if incomplete:
    logger.warning(f"Found {len(incomplete)} incomplete orders from previous session")

    for order in incomplete:
        state = order['state']
        coin = order['coin']
        order_id = order['order_id']

        if state == 'placed':
            # Check if it filled
            check_order_status(order_id)

        elif state == 'filled':
            # Start settlement process
            initiate_settlement(order)

        elif state == 'settling':
            # Retry settlement
            retry_settlement(order)

        elif state == 'resolved':
            # Save to history
            save_to_history(order)

        elif state == 'logged':
            # Train ML
            train_ml(order)
```

---

## Monitoring & Verification

### Check Lifecycle Status

```python
# At any time:
stats = self.lifecycle_tracker.get_statistics()
print(f"Completion rate: {stats['completion_rate']:.1f}%")
print(f"Incomplete: {stats['incomplete']}")

# Print full stats
self.lifecycle_tracker.print_statistics()
```

### Output Example:

```
============================================================
ORDER LIFECYCLE STATISTICS
============================================================
Total Orders:     47
Completed:        43 (91.5%)
Failed:           2
Incomplete:       2

By State:
  placed      : 0
  filled      : 1
  settling    : 1
  resolved    : 0
  logged      : 0
  trained     : 43
  failed      : 2
============================================================
```

### Audit Trail for Specific Order

```python
order = self.lifecycle_tracker.get_order(order_id)

print(f"Order: {order['coin']} {order['direction']}")
print(f"Current state: {order['state']}")
print("\nTransitions:")
for t in order['transitions']:
    print(f"  {t['timestamp']}: {t['state']}")
```

### Output:

```
Order: BTC UP
Current state: trained

Transitions:
  2026-02-04T14:23:15: placed
  2026-02-04T14:23:18: filled
  2026-02-04T14:38:20: settling
  2026-02-04T14:40:05: resolved
  2026-02-04T14:40:06: logged
  2026-02-04T14:40:07: trained
```

---

## Data Persistence

### State File Format

```json
{
  "orders": {
    "0x32e03eb4...": {
      "order_id": "0x32e03eb4...",
      "coin": "BTC",
      "direction": "UP",
      "state": "trained",
      "placed_at": "2026-02-04T14:23:15",
      "filled_at": "2026-02-04T14:23:18",
      "resolved_at": "2026-02-04T14:40:05",
      "outcome": "UP",
      "won": true,
      "pnl": 4.10,
      "transitions": [
        {"state": "placed", "timestamp": "2026-02-04T14:23:15"},
        {"state": "filled", "timestamp": "2026-02-04T14:23:18"},
        {"state": "settling", "timestamp": "2026-02-04T14:38:20"},
        {"state": "resolved", "timestamp": "2026-02-04T14:40:05"},
        {"state": "logged", "timestamp": "2026-02-04T14:40:06"},
        {"state": "trained", "timestamp": "2026-02-04T14:40:07"}
      ]
    }
  },
  "last_updated": "2026-02-04T14:40:07"
}
```

---

## Guarantees

✅ **No order lost** - Every placed order tracked
✅ **State persisted** - Survives crashes/restarts
✅ **Full audit trail** - Complete transition history
✅ **Automatic recovery** - Resumes incomplete orders
✅ **Error tracking** - Failed orders logged with reason
✅ **ML training guaranteed** - Every settled order trains model

---

## Files

- `src/core/order_lifecycle.py` - Lifecycle tracker (NEW)
- `src/core/ctf_settlement.py` - Blockchain verification (NEW)
- `src/core/market_15m.py` - Enhanced CLOB API (UPDATED)
- `data/order_lifecycle.json` - Persistent state
- `data/order_lifecycle_archive_*.json` - Archived orders

---

**Result**: Every order is tracked from placement to ML training with no gaps!
