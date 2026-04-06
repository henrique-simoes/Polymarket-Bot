# Trading Polymarket 15-Minute Binary Options: An Empirical Analysis

## What We Actually Found After 30 Days of Data and 2,863 Markets

**Date**: February 7, 2026
**Data**: 2,863 resolved BTC 15-minute binary option markets on Polymarket, 43,201 Binance 1-minute candles, 4,281 CLOB price snapshots
**Period**: January 8 - February 7, 2026

---

## Executive Summary

We built a sophisticated ML-driven trading bot for Polymarket's 15-minute binary options and then spent a month collecting hard data to figure out if any of our strategies actually work. The answer surprised us: the strategy we thought was best (buying cheap tokens for lotto-style payoffs) has a **negative edge** on real Polymarket data, while a simpler approach we treated as a fallback (directional arbitrage against Black-Scholes fair value) shows **+$977/month gross profit** from $1 bets in our backtested data -- though real-world execution costs, fees, and competition would significantly reduce this number.

This article presents every strategy we tested, with real numbers, real failures, and the uncomfortable truths about what separates theoretical edge from actual profit.

---

## Table of Contents

1. [The Setup: What Are 15-Minute Binary Options?](#1-the-setup)
2. [Strategy 1: The Lotto (Buy Cheap Tokens) -- FAILED](#2-the-lotto)
3. [Strategy 2: High-Probability Tokens -- MARGINAL](#3-high-probability)
4. [Strategy 3: Pure Hedged Arbitrage -- FAILED](#4-hedged-arbitrage)
5. [Strategy 4: Directional Arbitrage -- THE WINNER](#5-directional-arbitrage)
6. [Strategy 5: Time-Decay Sniping -- RISKY](#6-time-decay)
7. [Strategy 6: Low-Vol Lotto -- CONDITIONAL](#7-low-vol-lotto)
8. [The BS Model: How Accurate Is Our Edge Detector?](#8-bs-model-accuracy)
9. [The Oracle Problem: Polymarket vs Binance](#9-oracle-problem)
10. [Market Efficiency: The Hard Truth](#10-market-efficiency)
11. [Five Critical Bugs That Would Have Lost Money](#11-five-bugs)
12. [The Data Pipeline Problem Nobody Talks About](#12-data-pipeline)
13. [What Actually Works: The Profitable Path](#13-the-profitable-path)
14. [Lessons Learned](#14-lessons)

---

## 1. The Setup: What Are 15-Minute Binary Options? {#1-the-setup}

Every 15 minutes, Polymarket opens a new market: "Will BTC be above $X at [time]?" Two tokens trade:

- **UP token**: Pays $1 if BTC closes above the strike, $0 otherwise
- **DOWN token**: Pays $1 if BTC closes below the strike, $0 otherwise

The strike price is set at the opening BTC price. If BTC opens at $97,000, you're betting whether it will be above or below $97,000 exactly 15 minutes later.

Tokens trade between $0.01 and $0.99. A token at $0.20 implies a 20% probability. A token at $0.85 implies 85%.

**The minimum order is $1 USDC.** This is important -- it means you can't size down to manage risk on expensive tokens. A $1 bet on an 85-cent token risks $1 to make $0.18.

**Fees**: Polymarket charges dynamic taker fees that peak at ~3.15% at 50% probability and taper toward 0% at extreme prices. These fees reduce every edge calculation in this article. We report gross P&L throughout; net P&L after fees will be lower.

**Settlement**: Markets resolve via Polymarket's oracle (UMA-based), not Binance. This distinction matters more than you'd think.

### The Asymmetry That Attracted Us

Buying a token at $0.10 gives you a 9:1 payoff ratio. A $1 bet buys 10 shares; if you win, those shares pay $10 total ($9 profit). You only need to win ~10% of the time to break even. Meanwhile, buying at $0.85 gives you a 1:5.67 ratio -- you need ~85% accuracy just to break even.

This asymmetry seemed like a goldmine for ML: if a model can identify even slightly mispriced cheap tokens, the payoff structure does the rest.

We were wrong. Here's why.

---

## 2. Strategy 1: The Lotto (Buy Cheap Tokens) -- FAILED {#2-the-lotto}

### The Theory

Buy tokens priced at 20 cents or less. You're buying "unlikely" outcomes at a discount. If your ML model can identify reversals -- moments when the market says 15% probability but the real probability is 20% -- you profit from the massive payoff asymmetry.

The math looks beautiful on paper:
- Buy at $0.10 average price
- Need only 10% win rate to break even
- Each win pays $9 profit per $1 bet
- Even a 2% edge (12% WR vs 10% BE) generates +$0.20/trade average (0.12 x $9 - 0.88 x $1)

### The Reality (from 2,863 actual Polymarket markets)

| Threshold | Opportunities | Win Rate | Avg Price | Break-Even | Edge | P&L per Trade |
|-----------|-------------|----------|-----------|------------|------|---------------|
| 5 cents or less | 376 | 0.8% | 2.6 cents | 2.6% | **-1.8%** | **-$0.69** |
| 10 cents or less | 671 | 3.9% | 4.7 cents | 4.7% | **-0.8%** | **-$0.17** |
| 15 cents or less | 945 | 6.0% | 6.9 cents | 6.9% | **-0.9%** | **-$0.13** |
| 20 cents or less | 1,221 | 8.8% | 9.3 cents | 9.3% | **-0.4%** | **-$0.05** |
| 25 cents or less | 1,535 | 12.1% | 12.0 cents | 12.0% | +0.1% | +$0.01 |

**Every single threshold below 25 cents has a negative edge.** The market isn't mispricing cheap tokens -- it's pricing them accurately or even generously. (Note: the 5-cent bucket has only 376 observations with a 0.8% win rate, meaning roughly 3 wins total. Small absolute counts like this make the exact win rate unreliable -- but the direction of the result is consistent across all thresholds.)

### Why the Lotto Fails

When we compared Polymarket's actual prices to Black-Scholes theoretical values, we found something striking:

**Polymarket prices cheap tokens LOWER than Black-Scholes estimates.**

- At 0-10 cent prices: Polymarket mean divergence is -1.7 cents (Poly cheaper than BS)
- At 10-20 cent prices: -2.5 cents divergence
- At 20-30 cent prices: -2.5 cents divergence

This is the opposite of what a lotto strategy needs. The market makers on Polymarket aren't naive. They're pricing cheap tokens *below* fair value, which means buyers of cheap tokens are paying fair price or more for their lottery tickets.

### The BS Illusion

Our initial analysis used Binance data and Black-Scholes to *estimate* token prices. That analysis showed strong positive edges:

| Threshold | BS-Estimated Edge | Actual Polymarket Edge |
|-----------|------------------|----------------------|
| 5 cents or less | **+5.1%** | **-1.8%** |
| 10 cents or less | **+3.7%** | **-0.8%** |
| 20 cents or less | **+0.8%** | **-0.4%** |

The difference is enormous. BS-estimated prices suggest "buy cheap tokens" is a +$7,170/month strategy. Polymarket reality says it's a -$261/month loser (945 opportunities x -$0.13/trade at the 15-cent threshold, extrapolated). **Never backtest with model prices when you can use actual market prices.**

---

## 3. Strategy 2: High-Probability Tokens -- MARGINAL {#3-high-probability}

### The Theory

Buy tokens above 80 cents. You win most of the time. The math is harsh (need 85%+ accuracy) but if the market systematically underprices likely outcomes, there's profit to be had.

### The Reality

| Threshold | Opportunities | Win Rate | Avg Price | Break-Even | Edge | P&L per Trade |
|-----------|-------------|----------|-----------|------------|------|---------------|
| 75 cents or more | 1,535 | 87.9% | 88.0 cents | 88.0% | -0.1% | -$0.00 |
| 80 cents or more | 1,221 | 91.2% | 90.7 cents | 90.7% | **+0.4%** | **+$0.005** |
| 85 cents or more | 945 | 94.0% | 93.1 cents | 93.1% | **+0.9%** | **+$0.01** |
| 90 cents or more | 671 | 96.1% | 95.3 cents | 95.3% | **+0.8%** | **+$0.01** |
| 93 cents or more | 511 | 97.5% | 96.5 cents | 96.5% | **+0.9%** | **+$0.01** |

Edge is positive above 80 cents, but **the profit per trade is one cent.** From our data:

- At 85+ cents: ~945 opportunities x $0.01/trade = **~$9/month gross**
- At 93+ cents: ~511 opportunities x $0.01/trade = **~$5/month gross**

And these are before fees. Polymarket's taker fee on a 90-cent token is lower than on a 50-cent token, but it is still nonzero -- and could easily exceed the $0.01/trade edge.

The strategy technically "works" but produces single-digit monthly returns. A single bad day wipes out the month. The asymmetry works against you: each loss at 85 cents costs $1, each win pays only about $0.18 (1/0.85 - 1). You need to win roughly 85% of the time just to break even, and the edge above that is measured in fractions of a cent per trade.

### Why It's Marginal

High-probability tokens are efficiently priced. The market already knows BTC at $97,200 with $97,000 strike and 2 minutes left is very likely UP. The edge comes from occasional mispricings in the 0.5-1% range, which after Polymarket's spread and timing risk, barely covers transaction costs.

---

## 4. Strategy 3: Pure Hedged Arbitrage -- FAILED {#4-hedged-arbitrage}

### The Theory

If UP + DOWN tokens sum to less than $1, you can buy both and guarantee a risk-free profit regardless of outcome. This is textbook arbitrage.

### The Reality

From 4,281 paired price snapshots across our 30-day dataset:

- **UP + DOWN < $1 (arb opportunity)**: 212 instances
- **Average gap**: $0.008 (less than 1 cent)
- **Total P&L from buying both sides**: **-$7**

Yes, negative. The hedged arb *lost money*. Why?

1. **Spreads eat the gap**: The 0.8-cent average gap is smaller than bid-ask spreads
2. **Timing risk**: UP and DOWN prices are never exactly simultaneous
3. **Minimum order size**: $1 minimum means you need $2 per hedged position, making the 0.8% return negligible

The distribution of UP + DOWN sums:
- 93.2% of snapshots: sum between 0.98 and 1.02 (efficiently priced)
- 4.9% of snapshots: sum < 0.98 (theoretical arb, eaten by spreads)
- 1.9% of snapshots: sum > 1.02 (overpriced, can't short on Polymarket)

**Pure hedged arbitrage does not work on Polymarket 15-minute markets.** The market is too efficient and the minimum order too large. (A methodological note: our paired snapshots used a 2-minute tolerance window for matching UP and DOWN prices. Simultaneous execution is even harder in practice, meaning real hedged arb performance would likely be worse than what we measured.)

---

## 5. Strategy 4: Directional Arbitrage -- THE WINNER {#5-directional-arbitrage}

### The Theory

Use Black-Scholes to calculate the "fair" probability of UP vs DOWN, then bet against Polymarket whenever there's a meaningful price divergence. If BS says UP should be 60% but Polymarket prices it at 50%, buy UP.

This isn't risk-free -- BS could be wrong. But if BS is systematically more accurate than the market price, the edge compounds over thousands of trades.

### The Reality

**This is the only strategy with a meaningful, statistically significant positive edge.**

| Divergence Size | Bets | Wins | Win Rate | Monthly P&L | Per Trade |
|----------------|------|------|----------|-------------|-----------|
| 2-5 cents | 989 | 533 | 53.9% | -$97 | -$0.10 |
| **5-10 cents** | **1,067** | **604** | **56.6%** | **+$258** | **+$0.24** |
| **10-15 cents** | **677** | **399** | **58.9%** | **+$238** | **+$0.35** |
| **15-20 cents** | **359** | **226** | **63.0%** | **+$157** | **+$0.44** |
| **20+ cents** | **421** | **263** | **62.5%** | **+$324** | **+$0.77** |
| **TOTAL (5+ cents)** | **2,524** | **1,492** | **59.1%** | **+$977** | **+$0.39** |

Filtering to divergences of 5 cents or more:
- **2,524 opportunities per month** (about 84/day -- but not all are tradeable; see caveats below)
- **59.1% win rate** (vs break-even rates of 35-47% depending on entry price -- the further from 50 cents, the lower the break-even)
- **+$977 monthly gross profit** from $1 bets (before fees and slippage)

**Important caveats on these numbers**:
- **Fees not included**: Polymarket taker fees (up to 3.15% near 50-cent tokens) would reduce the edge by 1-3 cents per trade, cutting into the 5-10 cent divergence bucket significantly.
- **Look-ahead bias**: Each "opportunity" is a price snapshot. In live trading, you see the price, submit an order, and it fills (or doesn't) at a potentially different price. Slippage and execution latency erode edge.
- **Tradability assumption**: We count every snapshot where divergence exceeds 5 cents as a trade. In practice, orderbook depth is $50-500, and you may not get filled at the snapshot price. The actual number of executable trades per day is likely lower than 84.
- **Sample period**: 30 days of BTC data. This period may not be representative of all market conditions.

### Why Directional Arbitrage Works

Three key reasons:

**1. BS is genuinely predictive.** When BS says 60-75% confident, it's right 62-65% of the time. When it says 75-85% confident, it's right 76-80% of the time. The model isn't perfect, but it's consistently better than the market at estimating probabilities.

**2. Polymarket has structural biases.** Token prices systematically diverge from fair value:
- Below 50 cents: Polymarket prices cheaper than BS (by 1-2.5 cents)
- Above 50 cents: Polymarket prices more expensive than BS (by 1-3 cents)

This creates persistent directional mispricings that BS exploits.

**3. The 15-minute timeframe helps.** BS works best at short timeframes where the key inputs (current price, strike, time, volatility) are all directly observable. There's no earnings report coming, no regulatory announcement -- just random walk mathematics.

**A warning about edge decay**: If you're reading this article, so are other people. Directional arbitrage edges exist because not enough capital is correcting the mispricings. Every new bot running this strategy compresses the spreads and reduces the divergence size. The 5+ cent divergences we observed may shrink to 2-3 cents within months if enough participants adopt similar strategies. This is the fundamental tension: publishing profitable strategies accelerates their decay.

### Why 2-5 Cent Divergences Lose Money

Small divergences are noise, not signal. When BS and Polymarket disagree by only 2-3 cents, the disagreement is within the bid-ask spread and often reflects legitimate information the market has that BS doesn't (orderbook depth, recent momentum, cross-market flows). The 5-cent minimum threshold acts as a noise filter. Additionally, Polymarket's taker fees (up to 3.15%) can exceed the entire 2-5 cent divergence, making these trades negative EV even if the directional call is correct.

---

## 6. Strategy 5: Time-Decay Sniping -- RISKY {#6-time-decay}

### The Theory

In the last few minutes before expiry, time-decay accelerates exponentially. A token at 80 cents with 3 minutes left has much higher probability than 80% because there isn't enough time for a reversal. The BS model captures this "time premium" decay, identifying tokens priced below their mathematical certainty.

### The Reality: It Depends Entirely on Volatility

Time-Decay Sniping (Mode D) targets tokens in the 75-85 cent range. From our 30-day data, the break-even win rate for an 80-cent average entry is 80%.

**The problem: weekend volatility.**

During weekdays (BTC annualized vol ~0.78), the strategy works -- price moves are large enough relative to strike that 75-cent tokens genuinely represent 85%+ probabilities.

During weekends (BTC annualized vol ~0.41), BTC barely moves. Price hovers near strike. A token at 80 cents can easily flip when BTC moves $50 in the last minute. The BS model, using hardcoded volatility of 0.80, thinks the token should be at 95 cents. But with actual vol at 0.41, the real probability is closer to 75%.

**We fixed this** with a vol-scaled distance guard:

```
min_distance = 0.005 * (assumed_vol / realized_vol)
```

When vol is low, the guard requires price to be further from strike before allowing entry. This rejected 100% of weekend trades in our testing -- which is exactly right.

**Monthly P&L projection (with vol guard)**:
- Weekday rounds only (~2,000/month): 75-85% WR gives -$100 to +$200
- The variance is extremely high because each loss costs 4-5x each win (buy at 80c, lose $1 vs win ~$0.25)
- These projections are rough estimates based on limited Mode D data; we did not have enough high-confidence time-decay snapshots in our dataset to produce reliable bucket-level statistics

**Verdict**: Time-Decay is viable but requires vol-awareness and is not the primary profit driver. It supplements directional arbitrage, not replaces it.

---

## 7. Strategy 6: Low-Vol Lotto -- CONDITIONAL {#7-low-vol-lotto}

### The Theory

When volatility is low, price hovers near strike. Tokens priced at 20-25 cents have better odds than their price implies because the random walk covers less distance in low vol, making reversals back across strike more likely.

### The Reality

This strategy only activates when vol_ratio (assumed / realized) exceeds 1.5x. In our 30-day dataset, this condition existed for roughly 30% of the time (weekends and some quiet weekday evenings).

From BS-estimated data (not Polymarket prices, since Polymarket didn't have enough cheap-token snapshots during low-vol specifically):

- The theoretical edge exists: tokens at 20 cents win 13.8% of the time when BS says they should win 13%
- But the edge is tiny (0.8%) and might disappear on actual Polymarket prices

**Verdict**: An interesting concept for overnight/weekend operation but not validated as profitable from hard data. Treat as experimental.

---

## 8. The BS Model: How Accurate Is Our Edge Detector? {#8-bs-model-accuracy}

We tested Black-Scholes predictions against actual Gamma API (on-chain oracle) outcomes across all 2,863 markets:

| BS Confidence | Samples | Actual Accuracy | Edge vs Naive |
|--------------|---------|----------------|---------------|
| 50-60% | 12,847 | 54.2% | -0.8% |
| 60-75% | 9,231 | 65.3% | **+2.8%** |
| 75-80% | 3,456 | 77.8% | +0.3% |
| 80-85% | 2,891 | 82.1% | -0.4% |
| 85-90% | 2,344 | 87.9% | +0.4% |
| 90-95% | 2,109 | 91.4% | -1.1% |
| 95%+ | 8,760 | 96.8% | -0.7% |

**Key insight**: BS is most valuable in the **60-75% confidence range**, where it outperforms naive probability by 2.8%. This is exactly the range where directional arbitrage operates (5-15 cent divergences when fair value is 55-70%).

At extreme confidences (95%+), BS is well-calibrated but offers no tradable edge -- the market prices these efficiently.

Note that the "Edge vs Naive" column compares actual accuracy against the bucket midpoint (e.g., 67.5% for the 60-75% bucket). A positive edge means BS is slightly underconfident (actual accuracy exceeds the confidence level), while a negative edge means BS is overconfident. The large sample sizes (2,000-12,000 per bucket) make these estimates reasonably stable, though they are computed from the same 30-day window used throughout this analysis.

**Bug we found**: Our bot was using hardcoded volatility (BTC=0.80) in the BS calculation instead of realized volatility. During weekends when BTC vol dropped to 0.41, the model was 2x overconfident. We fixed this (see Section 11).

---

## 9. The Oracle Problem: Polymarket vs Binance {#9-oracle-problem}

One of our most surprising findings: **Polymarket's oracle disagrees with Binance's close price 8% of the time.**

Of 2,863 markets:
- **2,633 (92%)**: Binance close and Polymarket oracle agree
- **230 (8%)**: They disagree

This isn't a data error. Polymarket uses UMA's oracle to determine the "official" BTC price at each 15-minute mark. The UMA oracle can use different price feeds, and its timestamp resolution may differ from Binance's exact candle close.

**Why this matters**: Any backtesting strategy that uses Binance data to determine outcomes will be wrong 8% of the time. For a strategy with 57% win rate, an 8% error rate in your labels significantly distorts your accuracy measurements. Most of these disagreements occur when BTC closes very near the strike price (within a few dollars), where a tiny difference in price feed timing determines the outcome. This means the oracle divergence disproportionately affects strategies that trade near-strike scenarios.

Our approach: We used Gamma API outcomes (the actual on-chain resolution) as ground truth for all win/loss calculations. We used Binance data only for estimating BS fair values (which is appropriate -- BS needs the current spot price, not the settlement oracle).

### Verification

We independently verified the Gamma API outcomes using the CTF smart contract (`payoutNumerators` function) for all 296 of our actual bot trades. Result: **296/296 matched (100%)**. The Gamma API is trustworthy as a data source.

---

## 10. Market Efficiency: The Hard Truth {#10-market-efficiency}

The central question for any trading bot: is the market efficient enough to prevent systematic profit?

### What We Found

Polymarket 15-minute binary options are **partially efficient**:

**Efficiently priced (no edge)**:
- Cheap tokens (under 25 cents): Market makers price these at or below fair value
- Expensive tokens (over 85 cents): Efficiently priced to within 1% of fair value
- Hedged positions (UP + DOWN): Sum is consistently within 2% of $1.00

**Inefficiently priced (exploitable gross edge)**:
- Directional mispricings of 5+ cents vs BS fair value: 56-63% win rate depending on divergence size
- Most persistent in the 40-70 cent range (where directional uncertainty is highest)
- Average inefficiency: ~10 cents when it exists
- Whether this edge survives fees, slippage, and competition is the key open question

### Why Partial Efficiency?

Polymarket's 15-minute markets are structurally different from traditional exchanges:

1. **No continuous market making**: Tokens trade on an orderbook with discrete limit orders, not an AMM
2. **Short lifespan**: Each market exists for only 15 minutes, limiting arbitrage convergence time
3. **Information asymmetry**: Market makers use simpler models; sophisticated BS with realized vol can detect mispricings
4. **Low liquidity**: Typical orderbook depth is $50-500, meaning large orders move prices significantly
5. **Oracle divergence**: The 8% Binance-oracle gap creates genuine uncertainty that the market must price

The directional arbitrage edge likely exists because most market participants use heuristics or simpler models, while the BS fair value calculation with realized volatility captures the mathematical relationship between spot, strike, time, and volatility more precisely.

---

## 11. Five Critical Bugs That Would Have Lost Money {#11-five-bugs}

Before we could capitalize on the directional arbitrage edge, we found five bugs in our bot that would have prevented it from working:

### Bug 1: Mode A Equals Mode B

Our "Arbitrage Only" mode (Mode A) was supposed to use pure mathematical arbitrage. But the flag it set (`arb_only_mode`) was never read anywhere in the codebase. Mode A and Mode B were functionally identical -- both used ML predictions blended with arbitrage.

**Fix**: Mode A now sets `pure_arbitrage_mode = True`, routing to the dedicated pure-arbitrage code path that bypasses ML entirely.

### Bug 2: Hardcoded Volatility in BS Model

The Black-Scholes fair value calculation used hardcoded volatility (BTC=0.80, ETH=0.90, SOL=1.10) instead of realized volatility computed from recent 1-minute candles.

During a weekend with BTC vol at 0.41, the model thought a token at 75 cents was 23% underpriced (should be 98 cents). In reality, with proper vol, it should have been ~82 cents -- only a 7% edge.

**Fix**: `calculate_fair_value()` now uses `realized_volatility` (computed from 30 x 1-min Binance candles each round) with hardcoded values as fallback.

### Bug 3: 60/40 Scoring Scale Mismatch

The combined score formula was:
```
combined_score = 0.6 * arb_edge + 0.4 * ml_confidence
```

But `arb_edge` ranged from 0.05-0.15 while `ml_confidence` ranged from 0.0-1.0. A typical calculation:
```
0.6 * 0.10 + 0.4 * 0.75 = 0.06 + 0.30 = 0.36
```

ML dominated at ~83% effective weight instead of the intended 40%.

**Fix**: Normalized arb_edge to 0-1 scale: `arb_edge = min(raw_edge / 0.20, 1.0)`. A 10% edge now scores 0.50, properly balancing with ML at 0.75.

### Bug 4: SNIPE Trigger Misaligned with Dynamic Window

The bot entered SNIPE state at 420 seconds (7 minutes) before expiry, but the dynamic entry window allowed trading up to 720 seconds (12 minutes) before expiry for large edges. Trades placed during MONITOR state (7-12 minutes) bypassed the ML scoring pipeline in `smart_coin_selection()`.

**Fix**: SNIPE trigger moved to 720 seconds. Order placement guarded with `round_state == "SNIPE"` check -- MONITOR state only collects data and updates dashboard.

### Bug 5: Training/Prediction Feature Mismatch

During data collection (`_collect_data()`), features were extracted without arbitrage data -- 4 arbitrage features were always zero. But during prediction (`smart_coin_selection()`), the same features were extracted WITH arbitrage data. The ML model trained on zeros but predicted on real values.

**Fix**: `_collect_data()` now computes arbitrage data via `check_arbitrage()` and passes it to `extract_features()`.

### The Meta-Lesson

These bugs existed for weeks without being noticed because:
1. The bot appeared to work (placed orders, won some, lost some)
2. Log output showed "correct" behavior at a surface level
3. Only by comparing against hard empirical data did the code-vs-theory gaps become visible

**Any trading bot that hasn't been audited against empirical data is flying blind.**

---

## 12. The Data Pipeline Problem Nobody Talks About {#12-data-pipeline}

After fixing the bugs, we discovered another problem: **the bot wasn't storing enough data to evaluate its own performance.**

### What Was Being Stored

| Data | Stored? | Where |
|------|---------|-------|
| Trade outcome (won/lost) | Yes | trade_history.json |
| Token price at entry | Yes | trade_history.json |
| P&L per trade | Yes | trade_history.json |
| ML features (86 values) | Yes | replay_buffer.json |
| Rejected opportunities | Yes | phantom_trades.json |

### What Was NOT Being Stored

| Data | Stored? | Why It Matters |
|------|---------|---------------|
| BS fair value at entry | **No** | Can't verify if arbitrage detection was correct |
| Divergence percentage | **No** | Can't slice win rate by edge size |
| Realized volatility | **No** | Can't evaluate vol guard effectiveness |
| Spot price at entry | **No** | Can't reconstruct the trade's context |
| Time remaining at entry | **No** | Can't analyze timing optimization |
| Entry mode (arb/TD/lotto) | **No** | Can't compare strategy performance |

Without this data, you can compute aggregate win rate and P&L but cannot answer:
- "Do bigger divergences actually win more often?"
- "Is the vol guard saving us money?"
- "Does the dynamic entry window improve results?"

### The Fix

We added an `arb_metadata` dict to every order at placement time:

```json
{
  "arb_metadata": {
    "fair_value": 0.627,
    "poly_price": 0.520,
    "divergence_pct": 10.7,
    "edge_at_entry": 0.107,
    "time_remaining": 285,
    "spot_price": 97200.50,
    "vol_assumed": 0.80,
    "vol_realized": 0.78,
    "dynamic_window_used": 300,
    "mode": "pure_arb",
    "risk_profile": "any"
  }
}
```

This metadata flows through placement, settlement, and into `trade_history.json`. Every future trade can be fully reconstructed and analyzed.

### The Lesson

Build your data pipeline before your trading strategy. If you can't analyze your bot's decisions after the fact, you can't improve it. Log everything that went into the decision, not just the outcome.

---

## 13. What Actually Works: The Profitable Path {#13-the-profitable-path}

Based on 2,863 markets and 4,281 price snapshots, here is the one strategy that showed a positive gross edge in our backtested data:

### Directional Arbitrage (Mode A)

**How it works**:
1. Every few seconds, compute BS fair value using current spot, strike, realized vol, and time remaining
2. Compare to Polymarket's actual token price
3. If divergence exceeds 5 cents, bet on the BS side
4. Use realized vol (not hardcoded) for accurate BS calculation
5. Apply vol-scaled distance guard to reject near-strike trades in low vol

**Backtested performance (from 30-day data, gross of fees)**:
- Up to 84 opportunities/day across BTC (fewer will be executable due to liquidity constraints)
- 59.1% win rate (for divergences exceeding 5 cents)
- +$0.39 gross profit per $1 trade (before fees and slippage)
- +$977/month gross from BTC snapshots alone
- Starting capital needed: $20-50 (covers worst-case losing streaks with buffer)
- **Realistic expectation after fees/slippage**: Significantly lower. Budget 30-50% reduction from gross figures until validated with live trading data.

**Statistical confidence**: With 2,524 observations and a 59.1% win rate (vs 50% null), the z-score is approximately 9.1, which is nominally significant at p < 0.001. However, these observations are not independent -- multiple snapshots come from the same 15-minute market, and adjacent markets share similar volatility regimes. The effective sample size is smaller than 2,524. The edge is likely real, but the precision of the 59.1% estimate is lower than the raw p-value suggests.

**Risks**:
- **Execution risk**: Prices move between calculation and order fill. Our analysis assumes fills at the snapshot price, which overstates real performance.
- **Taker fees**: Polymarket charges up to 3.15% on taker orders. For trades near 50 cents (where most 5-10 cent divergences occur), this fee directly reduces the edge.
- **Oracle divergence**: 8% of outcomes differ from Binance (our BS uses Binance, oracle uses UMA)
- **Regime change**: Market may become more efficient as more bots compete. The edge we measure is from a specific 30-day window.
- **Vol misestimation**: Even realized vol can lag sudden regime changes
- **Crowding**: As more participants adopt BS-based arbitrage, divergences will compress and the strategy's profitability will decline

### How to Validate Before Scaling

1. Start Mode E (virtual/learning) first to collect data without risk
2. After 200+ virtual trades, switch to Mode A with $20 budget, $1 per trade
3. Run live for 5-7 days (~300+ trades for statistical significance)
4. Check `data/trade_history.json` -- every trade now has `arb_metadata`
5. Compare live win rate against backtested 59.1%. If live is 55%+ after fees, the edge is confirmed in current market conditions
6. Scale up gradually, monitoring for edge decay as market conditions change

### What About ML?

ML (Mode B) blends directional arbitrage with learned patterns. From our data, the ML component adds marginal value when properly weighted (60% arb, 40% ML after normalization fix). But the arbitrage signal alone is sufficient for profitability. ML becomes valuable when:

1. The replay buffer has 500+ properly-labeled samples
2. Features include arbitrage data (Bug 5 fix)
3. The model has seen enough regime changes (low vol, high vol, trending, ranging)

Start with pure arbitrage (Mode A), collect ML training data passively, then switch to Mode B after the model is trained.

---

## 14. Lessons Learned {#14-lessons}

### On Trading Bots

**1. Theoretical edge does not equal practical edge.**
Our BS model showed +$7,170/month from cheap tokens. Actual Polymarket data showed -$261/month. The model was right about the math; the market was just more efficient than we assumed.

**2. Market microstructure dominates strategy.**
Spreads, minimum order sizes, oracle differences, and execution timing matter more than the elegance of your model. A simple strategy that accounts for these realities beats a sophisticated strategy that doesn't.

**3. Every bug is invisible until you have ground truth data.**
Five critical bugs survived weeks of operation because the bot "worked" at a surface level. Only by comparing against 2,863 empirically-resolved markets did the code-vs-theory gaps become visible.

### On Data

**4. Backtest with real market data, not model outputs.**
Our BS backtest said lotto was the best strategy (+$7,170/month). Polymarket data said it was the worst (-$261/month). The market data was right.

**5. Store everything at decision time, not just outcomes.**
Knowing you won 57% of trades is useful. Knowing you won 63% of trades when divergence exceeded 15 cents but only 54% when it was 2-5 cents is actionable.

**6. Your oracle is not your data source.**
Polymarket settles on UMA oracle. BTC price comes from Binance. They disagree 8% of the time. Build your system around the settlement mechanism, not your data feed.

**7. Gross edge is not net edge.**
Our best strategy shows +$977/month gross. After Polymarket's taker fees (up to 3.15%), execution slippage, and the occasional failed fill, the real number is substantially lower. Always model fees before celebrating a backtest.

### On This Specific Market

**8. Polymarket 15-min markets are partially efficient.**
Cheap tokens: efficiently priced (no edge). Expensive tokens: efficiently priced (tiny edge). Directional mispricings of 5+ cents: show a gross edge in backtesting, but whether it persists net of costs and competition remains to be proven in live trading.

**9. The edge is in information processing, not prediction.**
We don't predict where BTC will go. We identify when Polymarket's price meaningfully diverges from a well-calibrated mathematical model. This is information arbitrage, not prediction.

**10. Volatility awareness is non-negotiable.**
A strategy that works at 0.78 vol (weekdays) can lose money at 0.41 vol (weekends). The vol-scaled distance guard is not an optimization -- it's a survival mechanism.

**11. Start simple, add complexity only when data justifies it.**
Pure directional arbitrage (Mode A) requires no ML, no complex features, no neural networks. It requires one thing: an accurate BS fair value calculation with realized volatility. Everything else is optimization.

---

## Appendix A: Data Sources and Methodology

### Data Collection

- **Polymarket markets**: Gamma API (`gamma-api.polymarket.com/markets?tag_id=102467&closed=true`), 2,864 markets fetched (2,863 with complete data after filtering)
- **Token prices**: CLOB API (`clob.polymarket.com/prices-history`), ~7-10 minute resolution per market
- **BTC candles**: Binance API via CCXT, 43,201 1-minute candles
- **Settlement outcomes**: Gamma API `outcomePrices` field (verified against CTF contract for 296 trades)

### Statistical Notes

- Win rates computed as simple proportions (wins/total)
- Break-even calculated as average entry price (for binary options, BE = avg token price)
- Edge = win rate - break-even
- P&L = (wins x win_payout) - (losses x $1), where win_payout = (1/avg_price - 1). For a $1 bet at price p, you buy 1/p shares; if you win, shares pay $1 each, so profit = 1/p - 1. If you lose, you lose the $1.
- All P&L figures assume $1 flat bet sizing, gross of Polymarket fees
- "30-day" figures represent actual 30-day window (Jan 8 - Feb 7, 2026)

### Replication

All data is saved to `data/polymarket_validation_30d.json` (6.9MB) and `data/polymarket_validation_cache.json` (20.7MB). Analysis scripts are in `scripts/validate_from_polymarket.py` and `scripts/analyze_arbitrage.py`.

---

## Appendix B: Monthly P&L Projections at $1 Bets

### Directional Arbitrage (Mode A, 5+ cent divergence)

**Why a simple average doesn't work here**: The +$977 figure from Section 5 is the sum of per-bucket P&L, where each bucket has a different average entry price and thus a different payout per win. You cannot reproduce this number from a single "average" win rate and a single "average" entry price, because higher-divergence trades have lower entry prices (bigger payoffs) AND higher win rates.

To illustrate: if you naively assume all 2,524 trades enter at 50 cents (where win payout = $1.00 profit and loss = $1.00), a 59.1% win rate gives:

```
1,491 wins x $1.00 - 1,033 losses x $1.00 = +$458
```

That's positive but still far from +$977. The gap comes from the fact that higher-divergence trades enter at 35-43 cents, not 50. The per-bucket breakdown below shows the real math.

**Detailed per-bucket economics (the actual math behind +$977)**:

| Divergence | Trades | Win Rate | Avg Entry | Win Pays | Per Trade | Monthly |
|-----------|--------|----------|-----------|----------|-----------|---------|
| 5-10c | 1,067 | 56.6% | ~47c | $1.13 | +$0.24 | +$258 |
| 10-15c | 677 | 58.9% | ~43c | $1.33 | +$0.35 | +$238 |
| 15-20c | 359 | 63.0% | ~40c | $1.50 | +$0.44 | +$157 |
| 20c+ | 421 | 62.5% | ~35c | $1.86 | +$0.77 | +$324 |
| **Total** | **2,524** | | | | **+$0.39 avg** | **+$977** |

The +$977 is the sum of the per-bucket monthly figures: $258 + $238 + $157 + $324 = $977. This is a gross figure before Polymarket taker fees, which would reduce it by an estimated $50-150/month depending on the fee schedule at each price point.

---

*This analysis is based on 30 days of historical data and past performance does not guarantee future results. All P&L figures are gross of Polymarket taker fees (up to 3.15%) and do not account for execution slippage or failed fills. Market conditions, liquidity, and competition from other bots may change the profitability landscape. The 8% oracle divergence rate introduces irreducible uncertainty. The strategies described here will become less profitable as more participants adopt them.*
