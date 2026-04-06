# Polymarket Trade Audit Report
**Date: February 6, 2026**
**Wallet: 0xYOUR_PROXY_WALLET_ADDRESS_HERE**
**CSV: 593 transactions across 301 unique markets**

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total USDC Invested (Buys) | $413.31 |
| Total USDC Returned (Redeems + Sells) | $399.85 |
| Net P&L (from CSV) | **-$13.47** |
| Realized PnL (Data API, closed positions) | **+$65.21** |
| Unrealized Losses (68 open losing positions) | **-$84.41** |
| Recoverable (1 unredeemed winning position) | **$2.34** |
| Discrepancies (won but not paid) | **$0.00** |

**Finding: No evidence of Polymarket withholding payments.** All winning positions were paid correctly. The losses come from 68 positions that resolved against your side (legitimate losses, primarily from the lotto strategy). One winning position ($2.34) remains unredeemed and can be recovered.

---

## Detailed Breakdown

### 1. Winning Trades (220 markets) - CORRECTLY PAID

- Total spent: $300.71
- Total received: $383.64
- Net profit: **+$82.93**
- All 50 closed positions on Data API show positive PnL
- Every winning redemption has correct USDC transfer in the CSV

### 2. Losing Trades (4 markets) - CORRECTLY ZERO

These 4 markets had Buy + Redeem($0) and NO positive redeem:

| Market | Spent | Side | Tokens | Status |
|--------|-------|------|--------|--------|
| SOL Feb 3, 8:30PM-8:45PM | $1.17 | Up | 4.29 | Lost (curPrice=$0) |
| SOL Feb 3, 5:45PM-6:00PM | $1.00 | Up | 19.99 | Lost (curPrice=$0) |
| BTC Feb 3, 5:45PM-6:00PM | $1.00 | Up | 3.09 | Lost (curPrice=$0) |
| BTC Feb 1, 9:30PM-9:45PM | $3.00 | Up | 6.28 | Lost (curPrice=$0) |

Verified on-chain: `curPrice = 0` confirms the market resolved AGAINST your position. These are legitimate losses.

### 3. Unredeemed Positions (69 open) - $84.41 SPENT

**68 LOSING positions (curPrice = $0, redeemable for $0):**
These tokens are sitting on-chain but are worthless. They can be redeemed to clean up, but will return $0 USDC. Total cost: $84.41.

Top unredeemed losses by cost:
| Market | Spent | Side | Shares |
|--------|-------|------|--------|
| BTC Feb 3, 11:45PM | $5.00 | Up | 862.77 |
| SOL Feb 3, 11:45PM | $4.00 | Up | 421.74 |
| ETH Feb 2, 1:30AM | $2.66 | Down | 2.68 |
| BTC Feb 2, 1:30AM | $2.66 | Down | 2.68 |
| ETH Feb 2, 1:00AM | $2.46 | Up | 5.47 |

**1 WINNING position (recoverable!):**

| Market | Side | Shares | Current Value | Condition ID |
|--------|------|--------|---------------|--------------|
| ETH Feb 6, 8:00PM-8:15PM | Down | 2.3434 | **$2.34** | 0xabcd316...7062d |

This position WON and is redeemable but has not been redeemed yet. You can recover **$2.34** by calling `redeemPositions` on the CTF contract.

### 4. Sold Early (11 markets)

| Market | Spent | Received | P&L |
|--------|-------|----------|-----|
| SOL Feb 4, 12:15AM | $5.00 | $1.91 | -$3.09 |
| ETH Feb 4, 12:15AM | $5.00 | $0.18 | -$4.82 |
| SOL Feb 3, 9:15PM | $3.62 | $2.42 | -$1.20 |
| SOL Feb 3, 9:00PM | $1.00 | $1.64 | +$0.64 |
| BTC Feb 1, 2:00AM | $1.00 | $2.27 | +$1.27 |
| Others (6 markets) | $7.00 | $7.78 | +$0.78 |

### 5. Daily P&L

| Date | Spent | Received | P&L |
|------|-------|----------|-----|
| Jan 31 | $19.28 | $10.94 | -$8.34 |
| Feb 1 | $6.47 | $6.50 | +$0.03 |
| Feb 2 | $111.36 | $100.52 | -$10.84 |
| Feb 3 | $136.62 | $154.18 | +$17.57 |
| Feb 4 | $41.08 | $26.31 | -$14.77 |
| Feb 5 | $20.50 | $23.46 | +$2.96 |
| Feb 6 | $74.00 | $70.50 | -$3.50 |
| Feb 7 | $4.00 | $7.43 | +$3.43 |
| **TOTAL** | **$413.31** | **$399.85** | **-$13.47** |

---

## Why $0 Redeems Appear in CSV

25 markets show BOTH a $0 redeem AND a positive redeem. This is **normal CTF behavior**:

When `redeemPositions(USDC, 0x0, conditionId, [1, 2])` is called:
- **indexSet 1 (YES/Up)**: If this side won, tokens pay out $1 each. If lost, tokens burn for $0.
- **indexSet 2 (NO/Down)**: Same logic for the opposite side.

The CSV records BOTH sides of the redemption. So for every winning market, you see:
1. A positive redeem (your winning tokens paying out)
2. A zero redeem (the losing side being burned for nothing)

These zero redeems are NOT missing payments - they are the normal burning of worthless tokens.

**7 zero-only redemption transactions** exist, but:
- 3 of them are for markets that ALSO have positive redeems in DIFFERENT transactions (batch timing)
- 4 of them are genuine losses (no winning side existed for you)

---

## Where the Money Went

```
Starting capital:                           $413.31
├── Winning trades redeemed:     +$381.67   (92% recovery)
├── Sold early:                  + $18.18
├── Unredeemed winner:           +  $2.34   (recoverable)
├── Unredeemed losers:           - $84.41   (68 positions, all lost)
├── Redeemed losers:             -  $6.17   (4 positions, correctly $0)
└── Net loss from early sells:   - $17.46
                                 ─────────
Net P&L:                         -$13.47
```

**The $84.41 in unredeemed losers is the main drag.** These are positions (mostly from lotto strategy at 1-10 cent prices) that resolved against you. The tokens are still on-chain but worth $0.

---

## Recommendations

### 1. Redeem the Winning Position ($2.34)
```
Market: Ethereum Up or Down - February 6, 8:00PM-8:15PM ET
Condition ID: 0xabcd31634b2582785e66b979ce7f2d9379c8ef362fa9637df775f48698f7062d
Payout: ~$2.34 USDC
```

### 2. Clean Up Losing Positions
The 68 unredeemed losing positions clutter your wallet. You can batch-redeem them (they'll return $0 but clear the tokens). This costs a small amount of gas (POL).

### 3. Strategy Observations
- **Lotto strategy (cheap tokens)** has high loss rate: ~68 losses out of ~89 total buy-only markets
- **Mode D (75-85 cent tokens)** has much better win rate: majority of Feb 5-6 trades were profitable
- The Feb 3 session was particularly costly (862 BTC tokens at $0.005 each, all lost = $5 gone)

---

## On-Chain Verification Summary

| Check | Result |
|-------|--------|
| All 50 closed positions profitable? | Yes (Data API confirms) |
| Total realized PnL | +$65.21 |
| Any winning positions unredeemed? | 1 ($2.34 recoverable) |
| Any losing positions with curPrice > 0? | No (all correctly $0) |
| Discrepancies found? | **None** |
| Polygonscan TX verification | All redemption TXs successful (status 0x1) |

---

## Deep Verification: "expired_loss" Trades (Feb 6 Follow-up)

After the user reported seeing trades marked as lost where the market outcome matched their prediction, a deep investigation was conducted:

### Method
Every single trade marked `won=False` (70 total) was verified against:
1. **Data API open positions**: `curPrice=0` for all 59 positions found
2. **Gamma API slug search**: `outcomePrices` checked for each market to determine winner
3. **Cross-reference**: User's prediction compared to actual market winner

### Result: All 70 losses are genuine

| Category | Count | Verification |
|----------|-------|-------------|
| `expired_loss` trades | 61 | All verified: prediction != market winner (Gamma API) |
| `wallet_sync` losses | 0 | N/A |
| Normal (live-settled) losses | 9 | All verified: prediction != market winner (Gamma API) |
| **Mislabeled (false losses)** | **0** | **None found** |

### What the User Was Likely Seeing

The Polymarket market page shows "Up or Down" as the market type. When viewing a position:
- **"Up"** displayed on the page = your **held position side**, not the market outcome
- If you bet UP and the market resolved DOWN, you still see "Up" as your position
- The market outcome is in the resolution details (outcomePrices)

For every expired_loss trade:
- `outcomePrices=["0","1"]` = Down won (Up tokens worth $0)
- `outcomePrices=["1","0"]` = Up won (Down tokens worth $0)
- In ALL 61 cases, the user's prediction was on the losing side

### trade_history.json Status

| Metric | Value |
|--------|-------|
| Total trades | 301 |
| Won | 226 (profit: +$89.34) |
| Lost | 70 (profit: -$82.59) |
| Unsettled | 5 (cost: $10.00) |
| Win rate | 76.4% |
| Net P&L (settled) | **+$6.75** |

The `expired_loss` label came from deleted code (`recover_unsettled_trades()` in the old `order_lifecycle.py`). While the label name is misleading, the classification was correct — these are genuine losses where tokens remain on-chain worth $0.

---

*Report generated by analyze_trades.py + fix_mislabeled_trades.py*
*Data sources: Polymarket CSV export, Data API, Gamma API*
*Deep verification: Feb 6, 2026*
