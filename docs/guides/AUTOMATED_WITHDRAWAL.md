# Automated Profit Withdrawal - Token Redemption

**Feature**: Automatic redemption of winning outcome tokens back to USDC

**Based on**: Official Polymarket CTF (Conditional Token Framework) documentation

---

## Overview

After winning a prediction market, you hold winning outcome tokens (YES or NO). These tokens need to be **redeemed** to convert them back to USDC. This process is now **fully automated**.

### How It Works

```
1. Bot places bet → Receives outcome tokens (YES or NO)
2. Market resolves → Winning outcome determined
3. Auto-redemption → Winning tokens burned, USDC received
```

**Key benefit**: Winning tokens (YES/NO) → USDC (1:1 ratio for winners)

---

## Implementation

### 1. Token Redemption via CTF Contract

**Contract**: `0x4d97dcd97ec945f40cf65f87097ace5ea0476045` (Polygon)

**Method**: `redeemPositions(collateralToken, parentCollectionId, conditionId, indexSets)`

**Parameters**:
- `collateralToken`: USDCe address (`0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`)
- `parentCollectionId`: `bytes(32)` (null/zero for Polymarket)
- `conditionId`: Market condition ID (bytes32)
- `indexSets`: `[1, 2]` (redeem both YES and NO, only winners pay out)

**Result**:
- Winning tokens → Burned
- Losing tokens → Worthless (nothing happens)
- USDC received = number of winning tokens × $1.00

---

## Code Implementation

### File: `src/core/polymarket.py`

#### New Methods Added

**1. `check_market_resolved(condition_id)`**
```python
# Check if market has been resolved and which outcome won
resolution = polymarket.check_market_resolved(condition_id)
# Returns: {'resolved': True, 'winning_outcome': 'YES', ...}
```

**2. `get_token_balance(token_id)`**
```python
# Get balance of specific outcome token
balance = polymarket.get_token_balance(token_id)
# Returns: Token balance as float (e.g., 1.5 tokens)
```

**3. `redeem_winning_tokens(condition_id)`**
```python
# Redeem winning tokens for USDC
result = polymarket.redeem_winning_tokens(condition_id)
# Returns: {'success': True, 'tx_hash': '0x...', 'winning_outcome': 'YES', ...}
```

**4. `merge_tokens_to_usdc(condition_id, amount, token_ids)`**
```python
# Merge equal amounts of YES + NO back to USDC (early exit)
result = polymarket.merge_tokens_to_usdc(condition_id, 1.0, {'yes': token_yes, 'no': token_no})
# Returns: {'success': True, 'amount_merged': 1.0, ...}
```

**5. `auto_redeem_all_winnings(trade_history)` ⭐ Main Method**
```python
# Automatically redeem all winning positions
results = polymarket.auto_redeem_all_winnings(trade_history)
# Returns: Summary dict with redemption counts
```

---

## Bot Integration

### File: `src/bot.py`

**When redemption happens**: After all trading rounds complete, before final report

```python
def print_final_report(self):
    # ... print stats ...

    # Auto-redeem all winning positions ⭐ NEW
    print("\n[WITHDRAWAL] Automatically redeeming winning positions...")
    redemption_results = self.polymarket.auto_redeem_all_winnings(self.trade_history)

    if redemption_results['redeemed'] > 0:
        print(f"\n[OK] Successfully withdrew {redemption_results['redeemed']} positions to USDC")
        print(f"Gas used: {redemption_results['total_gas_used']} units")

        # Refresh balance after redemption
        time.sleep(10)  # Wait for blockchain confirmation
        new_balance = self.wallet.get_usdt_balance()
        print(f"Updated Balance: {new_balance:.2f} USDC")
```

---

## Example Output

### During Redemption

```
================================================================================
AUTO-REDEEM ALL WINNINGS
================================================================================

Found 3 unique winning positions

Processing condition 0xabc123def456...

[REDEMPTION] Redeeming tokens for condition 0xabc123def456...
  [OK] Market resolved - Winner: YES
  [PENDING] Redemption transaction sent: 0x789...
  Waiting for confirmation...
  [OK] Tokens redeemed successfully!
  Transaction: https://polygonscan.com/tx/0x789...

Processing condition 0xdef789abc123...

[REDEMPTION] Redeeming tokens for condition 0xdef789abc123...
  [OK] Market resolved - Winner: NO
  [PENDING] Redemption transaction sent: 0x456...
  [OK] Tokens redeemed successfully!

================================================================================
REDEMPTION SUMMARY
================================================================================
Total Positions: 3
Successfully Redeemed: 3
Failed: 0
Not Yet Resolved: 0
Total Gas Used: 450000
================================================================================

[OK] Successfully withdrew 3 positions to USDC
Gas used: 450000 units

[BALANCE] Refreshing wallet balance after redemption...
Updated Balance: 13.45 USDC
```

---

## Redemption Flow

### Standard Flow (Winning Trade)

```
1. Place bet:
   - Send 1.00 USDC
   - Receive ~1.02 YES tokens (if price = 0.98)

2. Market resolves:
   - Actual outcome: YES (you win!)

3. Auto-redemption:
   - Call redeemPositions(conditionId)
   - Burn 1.02 YES tokens
   - Receive 1.02 USDC

4. Result:
   - Profit: 0.02 USDC
   - Tokens → USDC automatically
```

### Early Exit Flow (Position Monitoring)

If stop-loss or take-profit triggers:

```
1. Place bet:
   - 1.00 USDC → ~1.02 YES tokens

2. Position monitoring detects profit ≥ 50%:
   - Call merge_tokens_to_usdc() OR sell position
   - Exit early (before market resolution)

3. Market resolves later:
   - No tokens held → Nothing to redeem
```

---

## Gas Costs

**Redemption transaction**:
- Estimated gas: ~150,000 - 300,000 units
- Cost on Polygon: Very low (~$0.01 - $0.05)

**Merge transaction** (early exit):
- Estimated gas: ~200,000 - 300,000 units
- Cost: Similarly low

**Note**: Polygon has very low gas fees compared to Ethereum

---

## Error Handling

### Market Not Yet Resolved

```
[REDEMPTION] Redeeming tokens for condition 0xabc123...
  [ERROR] Market not yet resolved: Market closed but not yet resolved
```

**Action**: Wait for Polymarket to finalize resolution (usually within minutes to hours)

### No Balance to Redeem

```
[REDEMPTION] Redeeming tokens for condition 0xabc123...
  [OK] Market resolved - Winner: YES
  [INFO] No tokens to redeem (already redeemed or sold)
```

**Action**: None needed, tokens already converted or position was exited early

### Transaction Failed

```
[REDEMPTION] Redeeming tokens for condition 0xabc123...
  [PENDING] Redemption transaction sent: 0x789...
  [ERROR] Redemption transaction failed
```

**Action**: Check transaction on Polygonscan, may need manual intervention

---

## Manual Redemption (If Needed)

If auto-redemption fails, you can manually redeem:

```python
from src.core.polymarket import PolymarketMechanics

# Initialize client
pm = PolymarketMechanics()

# Redeem specific condition
result = pm.redeem_winning_tokens(condition_id='0xabc123def456...')

# Or redeem all from trade history
results = pm.auto_redeem_all_winnings(bot.trade_history)
```

---

## Configuration

**No configuration needed** - Automatic redemption is enabled by default

To disable (not recommended):

```python
# In src/bot.py, comment out the auto-redemption section:
# redemption_results = self.polymarket.auto_redeem_all_winnings(self.trade_history)
```

---

## Trade History Tracking

**Condition ID stored**: Every trade now stores the `condition_id` for redemption

```python
{
    'timestamp': '2026-01-31 14:30:22',
    'coin': 'BTC',
    'predicted': 'UP',
    'actual': 'UP',
    'won': True,
    'condition_id': '0xabc123def456...',  # ← Used for redemption
    'profit': 0.50,
    ...
}
```

---

## Benefits

✅ **Automatic**: No manual intervention needed
✅ **Efficient**: Redeems all winning positions in one batch
✅ **Safe**: Checks market resolution before attempting redemption
✅ **Transparent**: Clear logging of all redemption transactions
✅ **Cost-effective**: Low gas fees on Polygon

---

## Alternative Inventory Operations

### Merging Tokens (Early Exit)

Convert equal amounts of YES + NO back to USDC:

```python
# If you hold both YES and NO tokens and want to exit
result = pm.merge_tokens_to_usdc(
    condition_id='0xabc123...',
    amount=1.0,  # Merge 1 YES + 1 NO → 1 USDC
    token_ids={'yes': '0xyes...', 'no': '0xno...'}
)
```

**Use case**: Exit position before market resolution

---

## Verification

**Check redemption on Polygonscan**:

```
https://polygonscan.com/tx/{tx_hash}
```

**Verify USDC balance increased**:

```python
balance = wallet.get_usdt_balance()
print(f"Current balance: {balance:.2f} USDC")
```

---

## Summary

**What happens**:
1. Bot trades and accumulates winning tokens
2. Markets resolve
3. Bot automatically redeems all winning positions
4. USDC appears in wallet

**What you see**:
- Clear redemption logs
- Transaction hashes for verification
- Updated wallet balance

**What you do**:
- Nothing! It's fully automated 🎉

---

**Automated withdrawal implemented** ✅
**Based on official Polymarket CTF documentation** ✅
**Zero manual intervention required** ✅
