# Market Making Mode - User Guide

## What is Market Making?

Market making is a **low-risk, steady income** strategy where you provide liquidity to markets by placing limit orders on both sides of the orderbook. Instead of taking liquidity (paying fees), you **provide** liquidity and earn rebates.

**Key Differences from Arbitrage**:
- ❌ No directional prediction needed
- ❌ No timing required (orders sit in orderbook)
- ✅ Earn maker rebates: 0.5-3.15% per trade
- ✅ Profit from spread: Buy low, sell high
- ✅ Lower risk (neutral position)

---

## How It Works

### 1. Identify Wide Spreads
Look for markets where bid-ask spread > 2%:
```
Current Orderbook:
  Best Bid: $0.47 (someone willing to buy at 47 cents)
  Best Ask: $0.53 (someone willing to sell at 53 cents)
  Spread: $0.06 (6% / $0.47 = 12.8% spread)
```

### 2. Place Limit Orders on Both Sides
You become the new best bid/ask:
```
Your Bid:  $0.49 (buy at 49 cents)
Your Ask:  $0.51 (sell at 51 cents)
Your Spread: $0.02 (2% / $0.49 = 4% spread)
```

### 3. Wait for Orders to Fill
- Someone sells to you at $0.49 (you buy)
- Someone buys from you at $0.51 (you sell)
- **Spread profit**: $0.02 per share
- **Maker rebates**: 1.5% × 2 sides = 3% additional

### 4. Profit Calculation
```
Trade size: 10 shares

Spread Profit:
  Buy 10 shares @ $0.49 = $4.90 cost
  Sell 10 shares @ $0.51 = $5.10 revenue
  Gross profit: $0.20 (4.1%)

Maker Rebates (estimated 1.5% per side):
  Buy side rebate: $4.90 × 1.5% = $0.07
  Sell side rebate: $5.10 × 1.5% = $0.08
  Total rebates: $0.15

Total Profit: $0.20 + $0.15 = $0.35 (7.1% ROI)
```

---

## Risk vs Arbitrage

| Factor | Market Making | Pure Arbitrage |
|--------|--------------|----------------|
| **Directional Risk** | Medium (inventory risk) | Low (mathematical edge) |
| **Timing Risk** | Low (passive) | High (need to snipe) |
| **Execution Risk** | Low (limit orders) | High (market orders) |
| **Fee Structure** | EARN rebates (+1-3%) | PAY fees (-1-3%) |
| **Expected Return** | 2-7% per round-trip | 2-5% per opportunity |
| **Frequency** | Continuous (24/7) | Episodic (when edge exists) |

**Trade-off**: Market making has inventory risk (you might get filled on one side and stuck with position), but earns rebates instead of paying fees.

---

## When to Use Market Making

### ✅ Good Scenarios
1. **Wide spreads (>4%)**: High profit potential
2. **High liquidity**: Orders fill quickly
3. **Balanced markets**: Neither side overwhelmingly favored
4. **5-10 minutes before expiry**: Sweet spot for timing
5. **Low volatility**: Prices stable, less risk of gap moves

### ❌ Bad Scenarios
1. **Narrow spreads (<2%)**: Not worth the risk
2. **One-sided markets**: Get filled on wrong side only
3. **Very early in window**: Too much uncertainty
4. **Very late in window**: Not enough time for both sides to fill
5. **High volatility**: Prices gap through your orders

---

## Configuration

### Enable Market Making

Edit `config/config.yaml`:
```yaml
market_making:
  enabled: true  # ← Set to true

  # Spread requirements
  min_spread_pct: 2.0  # Only make markets if spread > 2%
  target_spread_pct: 4.0  # Our target spread (4%)

  # Rebate estimation
  estimated_maker_rebate: 1.5  # Conservative estimate (%)

  # Position sizing
  order_size_usdc: 5.0  # Size per limit order
  max_position_usdc: 20.0  # Maximum inventory risk

  # Quote management
  quote_ttl_seconds: 180  # Cancel after 3 minutes
  update_frequency: 30  # Update every 30s
```

### Dual-Mode Operation

**You can run market making + pure arbitrage simultaneously!**

```yaml
pure_arbitrage:
  enabled: true  # Take arbitrage opportunities

market_making:
  enabled: true  # Provide liquidity
```

**Strategy**:
- **Arbitrage**: Aggressively take opportunities when mathematical edge exists
- **Market Making**: Passively earn rebates when no arbitrage edge

**Result**: Maximize opportunities - earn from both taking AND making liquidity

---

## Expected Performance

### Conservative Estimate

**Assumptions**:
- Spread: 4% target (2% per side)
- Maker rebate: 1.5% per side
- Orders fill: 50% of the time (one or both sides)
- Inventory risk: 10% (get stuck with position 10% of time)

**Calculation**:
```
Successful round-trips (both sides fill):
  Frequency: 3 per day
  Spread profit: 4% × $5 = $0.20
  Maker rebates: 3% × $5 = $0.15
  Total per round-trip: $0.35

Monthly (90 round-trips):
  Gross: 90 × $0.35 = $31.50
  Inventory losses (10%): -$3.15
  Net: $28.35 (28% monthly ROI on $100 capital)
```

### Aggressive Estimate

**Assumptions**:
- Wider spreads (6%+) on volatile markets
- Higher frequency (10 round-trips/day)

**Result**: 50-100% monthly ROI (but higher risk)

### Reality Check

**Actual performance depends on**:
1. **Market conditions**: Spread availability
2. **Competition**: Other market makers tightening spreads
3. **Polymarket fee changes**: Rebate rates can change
4. **Your inventory management**: Avoiding getting stuck

**Expected realistic range**: 10-30% monthly ROI

---

## Risk Management

### Inventory Risk

**Problem**: You get filled on BID (buy at $0.49) but no one takes your ASK (sell at $0.51)

**You're now stuck with**:
- 10 shares of YES token
- $4.90 invested
- Market resolves: WIN ($10) or LOSE ($0)

**Mitigation**:
1. **Position limits**: `max_position_usdc: 20` caps exposure
2. **Cancel stale quotes**: `quote_ttl_seconds: 180` prevents runaway inventory
3. **Monitor market direction**: Cancel if price moving against you
4. **Pair with arbitrage**: If stuck, use arbitrage logic to exit

### Market Risk

**Problem**: Market gaps through your quotes (e.g., sudden news)

**Example**:
- Your ASK: $0.51
- News breaks, price gaps to $0.70
- You sold at $0.51, missed $0.19 profit

**Mitigation**:
1. **Wide spreads**: Don't quote too tight
2. **TTL**: Short quote lifetime limits exposure
3. **Monitor news**: Pause during volatile events

### Fee Risk

**Problem**: Maker rebates lower than expected or turn into fees

**Polymarket structure**:
- Extreme odds (5% or 95%): ~0.5% rebate
- Mid odds (50%): ~3.15% rebate
- **Dynamic**: Changes based on probability

**Mitigation**:
1. **Conservative estimates**: Use 1.5% average
2. **Monitor actual rebates**: Track via trade history
3. **Adjust if needed**: Disable if rebates disappear

---

## Monitoring & Adjustments

### Dashboard Metrics

When market making is active, dashboard shows:
```
[MARKET MAKING]
  Active Quotes: 2 (BTC, ETH)
  Completed Round-Trips: 15
  Total Rebates Earned: $4.50
  ROI: 18.0%
```

### Log Messages

```
[MARKET MAKING] BTC YES: Mid=$0.500, Spread=8.0%
  Our Bid: $0.480, Our Ask: $0.520
  Gross Spread: 8.3% + Rebate: 1.5% = 9.8%

[MM] Placing BID: BTC @ $0.480 for 10.42 shares
[MM] Placing ASK: BTC @ $0.520 for 9.62 shares
[MM] Successfully placed quotes for BTC

[MM] ✓ Round-trip completed: BTC
  Spread: $0.40 (8.3%)
  Rebate: $0.15
  Total: $0.55 (11.5%)
```

### When to Adjust

**If round-trip frequency < 1 per day**:
- **Widen minimum spread**: Change `min_spread_pct: 1.0` (more aggressive)
- **Increase order size**: Bigger orders = more likely to fill
- **Expand time window**: Trade earlier/later in 15-min cycle

**If inventory builds up (stuck with positions)**:
- **Tighten spreads**: Get filled on both sides faster
- **Reduce order size**: Less capital at risk
- **Pause market making**: Wait for better conditions

**If rebates < 1.0%**:
- **Increase spread target**: `target_spread_pct: 6.0`
- **Focus on mid-odds markets**: Higher rebates near 50%

---

## Advanced Strategies

### 1. Dynamic Spread Pricing

Instead of fixed 4% spread, adjust based on:
- **Volatility**: Wider spreads when volatile
- **Time remaining**: Tighter spreads near expiry
- **Orderbook depth**: Wider if thin liquidity

**Implementation** (requires code changes):
```python
if volatility > 0.05:
    target_spread = 6.0  # Wider
elif time_remaining < 300:
    target_spread = 3.0  # Tighter
else:
    target_spread = 4.0  # Normal
```

### 2. Layered Quoting

Place multiple limit orders at different price levels:
```
Your Bids:           Your Asks:
$0.47 (5 shares)     $0.53 (5 shares)
$0.48 (10 shares)    $0.52 (10 shares)
$0.49 (20 shares)    $0.51 (20 shares)
```

**Benefit**: Capture more flow, better avg price

**Risk**: Larger inventory, more capital required

### 3. Arbitrage + Market Making Combo

**Dual strategy**:
1. **Arbitrage mode**: Snipe obvious mispricings
2. **Market making mode**: Provide liquidity rest of time

**Optimal balance**:
- Arbitrage: 70% of capital (active, high return)
- Market making: 30% of capital (passive, steady income)

**Result**: Maximize overall utilization

---

## Troubleshooting

### "No market making opportunities found"

**Reasons**:
1. **Spreads too narrow**: Increase `min_spread_pct` to see opportunities (riskier)
2. **Wrong time window**: Only trades 5-10 min before expiry
3. **Low volatility**: Markets too efficient, no wide spreads
4. **Competition**: Other bots have tightened spreads

**Fix**: Monitor logs for "Spread=X%" - if consistently <2%, market too tight

### "Orders not filling"

**Reasons**:
1. **Quotes too wide**: Your bid/ask not competitive
2. **Low liquidity**: Not enough counterparty flow
3. **One-sided market**: Everyone wants same side

**Fix**:
- **Tighten spreads**: `target_spread_pct: 2.0` (more aggressive)
- **Increase size**: Bigger orders more visible
- **Cancel and replace**: Update prices every 30s

### "Stuck with inventory"

**If you get filled on one side only**:

**Option 1: Wait for other side to fill**
- Let ASK order sit, hope it fills
- Risk: Market resolves before fill

**Option 2: Cancel and take loss**
- Cancel ASK, accept inventory
- Use position as arbitrage trade

**Option 3: Hedge with opposite side**
- Buy NO token to neutralize
- Guaranteed $1 payout (minus fees)

**Example**:
```
Stuck with: 10 YES @ $0.49 = $4.90
Hedge: Buy 10 NO @ $0.51 = $5.10
Total cost: $10.00
Payout: $10.00 (always)
Loss: $0.00 (break-even, fees paid)
```

---

## Comparison: Market Making vs Other Modes

| Mode | ROI | Risk | Skill Required | Time Commitment |
|------|-----|------|----------------|----------------|
| **Pure Arbitrage** | 2-5% | Low | Low | High (snipe timing) |
| **ML Hybrid** | 15-35%* | High | High | Medium (training) |
| **Market Making** | 10-30% | Medium | Low | Low (passive) |
| **Dual (Arb+MM)** | 15-40% | Medium | Medium | Medium |

*Unproven claims, likely lower

**Best for**:
- **Pure Arbitrage**: Conservative traders, provable edge
- **Market Making**: Passive income seekers, don't want to time trades
- **Dual Mode**: Maximize opportunities, balanced risk/return

---

## Summary

**Market Making Mode is**:
- ✅ Passive income (orders sit in book)
- ✅ Earns rebates (0.5-3.15% per trade)
- ✅ Profits from spreads (4-8% typical)
- ✅ Lower stress (no sniping required)
- ⚠️ Inventory risk (can get stuck with positions)
- ⚠️ Requires spreads >2% to be profitable

**Best Use Case**:
- Run alongside pure arbitrage (dual-mode)
- Arbitrage takes opportunities aggressively
- Market making earns passive income rest of time
- Combined ROI: 15-40% monthly (if both work)

**Recommendation**: Enable both pure_arbitrage and market_making for maximum profit potential.

---

## Next Steps

1. **Read this guide fully** - Understand risks and rewards
2. **Enable market making**: Edit `config/config.yaml`
3. **Test in learning mode**: $10 virtual, run for 24 hours
4. **Monitor results**: Check completed round-trips, rebates earned
5. **Optimize settings**: Adjust spreads based on fill rates
6. **Scale gradually**: Start $5 per order → $10 → $20 as confidence grows

**Good luck earning those maker rebates! 💰**
