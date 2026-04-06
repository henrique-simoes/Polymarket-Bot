# Pure Arbitrage Bot - Quick Start Guide

## What is Pure Arbitrage Mode?

Pure Arbitrage Mode removes ALL machine learning components and uses only proven mathematical arbitrage strategies that extracted **$40M+ from Polymarket** markets.

**Key Differences from Standard Mode:**
- ❌ No ML predictions
- ❌ No feature extraction (86 features → 0)
- ❌ No training or episode collection
- ✅ Only mathematical arbitrage edges
- ✅ Proven strategies (binary complement, spot price, lotto)
- ✅ Lower overhead, faster execution

---

## Arbitrage Strategies Included

### 1. Binary Complement Arbitrage ($39.5M+ extracted)
**Logic**: If YES + NO < $1.00, buy both for guaranteed profit

**Example**:
```
YES price: $0.48
NO price:  $0.48
Total:     $0.96

Buy both:  Cost $0.96
Payout:    Always $1.00 (one side wins)
Profit:    $0.04 (4.2% return)
```

**Why it works**: Market inefficiency - prices don't sum to $1.00

### 2. Spot Price Arbitrage
**Logic**: If BTC spot is clearly above/below strike, market should reflect this

**Example**:
```
BTC spot:   $100,000
Strike:     $99,000 (already $1K above)
YES price:  $0.60 (only 60% probability?)

Opportunity: Buy YES at $0.60 (underpriced)
Expected:    Should be 0.85+ given current position
```

**Why it works**: Market lags behind spot price movements

### 3. Lotto Strategy (Favorable Asymmetry)
**Logic**: Buy low-probability bets (<15 cents) with directional evidence

**Example**:
```
Price: $0.10 (10% implied probability)
If WIN:  $0.90 profit (9x return)
If LOSE: $0.10 loss (1x)

Asymmetry: 9:1 upside vs downside
Break-even: Only need 10.2% win rate (including fees)
```

**Why it works**: Market underprices tail events, favorable risk/reward

---

## How to Enable

### Step 1: Edit Config
Open `config/config.yaml` and find the `pure_arbitrage` section (around line 56):

```yaml
# Pure Arbitrage Mode (NEW - Conservative, Proven Strategy)
pure_arbitrage:
  enabled: true  # ← CHANGE THIS TO true
```

### Step 2: Adjust Strategy Settings (Optional)

**Recommended settings for conservative start**:
```yaml
pure_arbitrage:
  enabled: true

  # Strategy 1: Binary complement
  complement_arbitrage: true
  complement_threshold: 0.98  # Only flag if YES+NO < 0.98 (2%+ edge)

  # Strategy 2: Spot price arbitrage
  spot_arbitrage: true
  spot_buffer_pct: 0.5
  min_edge_pct: 5.0  # Require 5%+ edge (conservative)

  # Strategy 3: Lotto strategy
  lotto_strategy: true
  lotto_max_price: 0.15  # Only prices < $0.15
  lotto_min_edge_pct: 10.0  # Require 10%+ estimated edge

  # Fee awareness
  max_fee_pct: 3.15  # Polymarket dynamic fees (peak at 50%)

  # Timing
  snipe_window: 300  # Last 5 minutes only
```

**Aggressive settings** (if you want more opportunities):
```yaml
  complement_threshold: 0.99  # Accept smaller edges (1%+)
  min_edge_pct: 3.0  # Lower edge requirement
  lotto_max_price: 0.20  # Allow prices up to 20 cents
  snipe_window: 600  # Trade in last 10 minutes
```

### Step 3: Run in Learning Mode First

**IMPORTANT**: Test with virtual money before risking real capital!

```bash
python -m src.bot
# Select: C (Learning Mode)
# Choose: 1 (Low Probability / Lotto) or 3 (Trust Algorithm)
# Budget: $10 virtual
```

**Expected Behavior**:
- Dashboard will show "PURE ARBITRAGE MODE ENABLED" at startup
- No ML training messages
- Arbitrage strategies logged clearly
- Orders only placed when mathematical edge exists

### Step 4: Monitor for 24 Hours

Collect at least **20 virtual trades** to validate:
1. Arbitrage opportunities are being found
2. Orders are executing successfully
3. Fees are calculated correctly
4. Win rate is tracking properly

Check logs for:
```
[PURE ARBITRAGE MODE] ML features disabled
[COMPLEMENT ARB] YES=$0.48 + NO=$0.48 = $0.96
  Edge: 4.17% - Fees: 6.30% = Net: -2.13%  ← Fee too high, skipped

[LOTTO] BTC: UP at $0.12 (<$0.15)
  Edge: 12.5% - Net: 9.35%  ← Good opportunity

[BEST OPPORTUNITY] Strategy: lotto, Edge: 9.35%
```

### Step 5: Switch to Live Trading

**Only proceed if**:
- ✓ 20+ virtual trades collected
- ✓ Opportunities are being found regularly (at least 1-2 per hour)
- ✓ No errors or crashes
- ✓ Win rate > 45% (accounting for variance)

**To go live**:
1. Restart bot
2. Select: B (Standard ML) - but with pure_arbitrage.enabled=true, ML is disabled anyway
3. Set real budget: Start with $0.50-$1.00 per round
4. Monitor closely for first 10 trades

---

## Expected Performance

### Conservative Estimate (If Arbitrage Still Exists)

**Assumptions**:
- Fees: 1.5-3.15% per trade
- Edge: 2-5% after fees (conservative)
- Win rate: 50-60% (better than random due to arbitrage)
- Trades: 100 per month

**Calculation**:
```
Scenario 1: Complement Arbitrage (2% net edge)
100 trades × $1 each = $100 cost
Average edge: 2% × $100 = $2 profit per trade
Monthly profit: 100 × $0.02 = $2.00 (2% ROI)

Scenario 2: Lotto Strategy (55% win rate at $0.10 price)
100 trades × $1 each = $100 cost
Wins: 55 × $9 profit = $495
Losses: 45 × -$1 = -$45
Net: $495 - $45 - $100 = $350 (350% ROI if ML finds edge)
```

**Reality Check**: Lotto strategy still requires ML-level prediction accuracy. Pure complement arbitrage is safer but lower return.

### Realistic Estimate

Given 3.15% fees block most arbitrage:
- **Expected ROI**: 0-5% monthly
- **Win rate**: 50-55%
- **Strategy**: Mostly lotto at low-fee probabilities

**If no opportunities found**: Fees may have eliminated all arbitrage. Pivot to market making (earn rebates instead).

---

## Troubleshooting

### "No arbitrage opportunities found"

**Possible reasons**:
1. **Fees too high**: 3.15% dynamic fees eliminate <3.15% edges
   - **Fix**: Lower `min_edge_pct` to 2.0-3.0 (riskier but more opportunities)

2. **Markets efficient**: $40M extraction may have dried up inefficiencies
   - **Check**: Look at orderbook manually - do YES+NO sum to $1.00?

3. **Snipe window too narrow**: Only trading last 5 minutes
   - **Fix**: Increase `snipe_window` to 600 (10 minutes)

4. **Conservative settings**: Thresholds too strict
   - **Fix**: Use aggressive settings (see Step 2)

### "Orders not filling"

**Reasons**:
1. **Liquidity too low**: Not enough counterparty orders
   - **Fix**: Check `min_market_depth` in config (default 1000 shares)

2. **Price moved**: Arbitrage disappeared between detection and order
   - **Fix**: Faster execution (hard to fix without code changes)

3. **Minimum order size**: Market requires $5+ but you're betting $1
   - **Fix**: Increase `initial_bet_usdc` to 2.0-5.0

### "Win rate < 45%"

**If this happens after 50+ trades**:
1. **Arbitrage doesn't exist**: Fees eliminated edge
2. **Bot logic error**: Check logs for strategy decisions
3. **Market resolution wrong**: Verify Chainlink oracle results match

**Action**: Switch to market making or abandon strategy

---

## Next Steps

### If Profitable (ROI > 5%)
1. Scale up slowly: $1 → $2 → $5 → $10 per trade
2. Track Sharpe ratio (return / volatility)
3. Monitor for fee changes (Polymarket may adjust)

### If Marginally Profitable (ROI 0-5%)
1. Optimize settings (lower thresholds, wider window)
2. Focus on specific strategy (disable others)
3. Consider opportunity cost (is 2% worth the effort?)

### If Unprofitable (ROI < 0%)
1. **Stop trading immediately**
2. Analyze logs: Which strategy losing money?
3. Pivot to market making (earn 0.5-3.15% maker rebates)

---

## Comparison: Pure Arbitrage vs ML Hybrid

| Feature | Pure Arbitrage | ML Hybrid (Standard) |
|---------|---------------|---------------------|
| **ML Training** | None | Required (200+ samples) |
| **Complexity** | Low | High (86 features) |
| **Overhead** | Minimal | Significant |
| **Proven Track Record** | $40M+ extracted | Unproven |
| **Overfitting Risk** | Zero | High (0.58 samples/feature) |
| **Expected ROI** | 0-5% (conservative) | Unknown (claims 15-35%) |
| **Risk Level** | Low | Medium-High |
| **Setup Time** | Immediate | 1-2 weeks |

**Recommendation**: Start with Pure Arbitrage to validate edge still exists, then consider hybrid if needed.

---

## Advanced: Combining with Market Making

**Opportunity**: Polymarket offers **0.5-3.15% maker rebates**

**Strategy**:
1. Pure arbitrage for taking opportunities
2. Market making for earning rebates on liquidity provision

**Expected Return**:
- Arbitrage: 2-5% per winning trade
- Maker rebates: 0.5-2% per filled limit order
- Combined: 3-7% blended return

**Implementation**: Requires modifications to use limit orders instead of market orders (not currently supported).

---

## Summary

**Pure Arbitrage Mode is**:
- ✅ Proven ($40M+ extracted)
- ✅ Simple (no ML complexity)
- ✅ Conservative (mathematical edges only)
- ⚠️ May be blocked by fees (3.15% > most edges)
- ⚠️ Requires validation (test first!)

**Best for**:
- Testing if arbitrage still exists post-fees
- Conservative traders avoiding ML risk
- Bootstrapping before committing to ML training

**Not ideal for**:
- Maximizing returns (ML hybrid potentially higher if it works)
- High-frequency trading (execution speed matters)
- Competing with sophisticated bots (they're faster)

---

**Good luck! Start small, validate first, scale carefully.**
