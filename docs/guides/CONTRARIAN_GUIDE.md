# Contrarian Fade Strategy - Quick Start

## 🎯 The Strategy in 30 Seconds

**Bet AGAINST the crowd when they're TOO certain**

```
Market shows: YES = 90¢ (everyone thinks it's going UP)
You buy:      NO = 10¢  (betting it goes DOWN)

If you WIN:  $1.00 - $0.10 = $0.90 profit (900% return!)
If you LOSE: -$0.10 loss

Need to be right: Only 15% of the time to profit ✓
```

## 🚀 How to Run

### Quick Start (Simplest)

```bash
# 1. Enable contrarian mode
# Edit config/config.yaml line 106:
contrarian:
  enabled: true  # ← Change to true

# 2. Run the standalone contrarian bot
python -m src.contrarian_bot

# 3. Set your bet amount (e.g., $1)
Enter bet amount: 1.00

# 4. Bot runs automatically
# Watches for extreme prices (>85¢)
# Places trades when opportunities found
```

### Advanced (Customize Settings)

Edit `config/config.yaml`:

```yaml
contrarian:
  enabled: true

  # When to consider a price "extreme"
  extreme_threshold: 0.85  # 85¢ or higher

  # Maximum you'll pay for the fade
  max_entry_price: 0.15  # Won't buy if >15¢

  # Time window (last 1-3 minutes before expiry)
  min_time_remaining: 60   # At least 1 minute
  max_time_remaining: 180  # At most 3 minutes
```

**Conservative settings** (fewer trades, safer):
```yaml
  extreme_threshold: 0.90  # Only fade 90¢+ (very extreme)
  max_entry_price: 0.10    # Only pay up to 10¢
```

**Aggressive settings** (more trades, riskier):
```yaml
  extreme_threshold: 0.80  # Fade 80¢+ (moderately extreme)
  max_entry_price: 0.20    # Pay up to 20¢
```

## 📊 The Math

### Break-Even Analysis

| Entry Price | Break-Even Win Rate | Profit if Win | Loss if Lose |
|-------------|--------------------|--------------:|-------------:|
| **10¢** | **10%** | $0.90 (900%) | -$0.10 (100%) |
| **15¢** | **15%** | $0.85 (566%) | -$0.15 (100%) |
| **20¢** | **20%** | $0.80 (400%) | -$0.20 (100%) |

### Example: 100 Trades at 15¢ Entry

**Scenario A: 15% Win Rate (break-even)**
```
Wins:  15 × $0.85 = $12.75
Losses: 85 × -$0.15 = -$12.75
Net: $0 (break-even)
```

**Scenario B: 20% Win Rate (profitable)**
```
Wins:  20 × $0.85 = $17.00
Losses: 80 × -$0.15 = -$12.00
Net: $5.00 (33% ROI)
```

**Scenario C: 30% Win Rate (very profitable)**
```
Wins:  30 × $0.85 = $25.50
Losses: 70 × -$0.15 = -$10.50
Net: $15.00 (100% ROI)
```

## 🎮 What You'll See

### When Opportunity Found

```
🎯 CONTRARIAN OPPORTUNITY: BTC
┌────────────┬──────────────────────────────────┐
│ Metric     │ Value                            │
├────────────┼──────────────────────────────────┤
│ Strategy   │ FADE EXTREME PRICE               │
│ Direction  │ DOWN (buying NO token)           │
│ Fading     │ YES at 92¢                       │
│ Entry Price│ 8¢                               │
│ Max Profit │ 1050%                            │
│ Breakeven WR│ 8.7%                            │
│ Reason     │ YES overextended at 92¢          │
└────────────┴──────────────────────────────────┘

→ Placing contrarian trade: BTC DOWN at $0.08
✓ Order placed successfully!
  Order ID: 0x548309c38b66...
  Shares: 12.50
  Cost: $1.00
```

### When Monitoring (No Opportunity)

```
[INFO] Checking BTC... YES=0.73, NO=0.27 (not extreme)
[INFO] Checking ETH... YES=0.81, NO=0.19 (not extreme)
[INFO] Checking SOL... YES=0.66, NO=0.34 (not extreme)
```

## ⚠️ Risks & Warnings

### Risk 1: The Crowd Might Be Right

**Scenario**: BTC pumping hard, YES hits 95¢

You fade: Buy NO at 5¢
Market resolves: BTC actually went UP ✗
Your loss: -$1.00 (bought 20 shares @ 5¢)

**Mitigation**: Only trade last 1-3 minutes (less time for trend to extend)

### Risk 2: Fees Eat Into Edge

**Fee impact at extremes**:
```
Entry at 10¢:
  Pay 2% fee = $0.20 on $10 trade
  Effective entry: 12¢ instead of 10¢
  Break-even WR: 12% (vs 10% without fees)
```

**Mitigation**: Already accounted for in max_entry_price (15¢ leaves buffer)

### Risk 3: Not Enough Opportunities

**Reality**: Extreme prices (>85¢) don't happen every market

Expected frequency:
- Conservative (90¢+): 1-2 per day
- Moderate (85¢+): 3-5 per day
- Aggressive (80¢+): 5-10 per day

**Mitigation**: Be patient, only take true extremes

### Risk 4: Liquidity at Extremes

**Problem**: At 95¢ YES, the 5¢ NO might have huge spread

```
Orderbook:
  Best Bid (NO): 3¢
  Best Ask (NO): 7¢

You want 5¢ but market gives you 7¢
```

**Mitigation**: Use limit orders (not implemented yet) OR accept slippage

## 🧪 Testing Recommendations

### Phase 1: Observation (No Money)

```bash
# Just watch for opportunities, don't place trades
# Comment out the place_contrarian_trade() call
# Run for 24 hours, count opportunities
```

**Success criteria**: 3+ opportunities per day

### Phase 2: Paper Trading (Virtual Money)

```bash
# Modify bot to log trades instead of placing them
# Track simulated results over 50 trades
```

**Success criteria**: >20% win rate

### Phase 3: Small Capital Test ($10)

```bash
# Set bet_amount = 0.10 (10 cents per trade)
# Run for 1 week
# Total risk: $10
```

**Success criteria**: Positive P&L after 100 trades

### Phase 4: Scale Up

If profitable, increase to $1-5 per trade

## 📈 Expected Performance

### Conservative Estimate

**Assumptions**:
- 3 trades per day
- 18% win rate (slightly above break-even)
- Average entry: 15¢

**Monthly results**:
```
Trades: 90
Wins: 16 (18%)
Losses: 74

Profit: 16 × $0.85 = $13.60
Losses: 74 × -$0.15 = -$11.10
Net: $2.50 (16% ROI)
```

### Realistic Estimate

**Assumptions**:
- 5 trades per day
- 25% win rate (solid performance)
- Average entry: 12¢

**Monthly results**:
```
Trades: 150
Wins: 37 (25%)
Losses: 113

Profit: 37 × $0.88 = $32.56
Losses: 113 × -$0.12 = -$13.56
Net: $19.00 (126% ROI)
```

### Optimistic Estimate

**Assumptions**:
- 8 trades per day
- 35% win rate (excellent performance)
- Average entry: 10¢

**Monthly results**:
```
Trades: 240
Wins: 84 (35%)
Losses: 156

Profit: 84 × $0.90 = $75.60
Losses: 156 × -$0.10 = -$15.60
Net: $60.00 (400% ROI)
```

## 💡 Tips for Success

### Tip 1: Be Patient

Don't chase marginal extremes. Wait for TRUE extremes (90¢+).

### Tip 2: Size Appropriately

Start small (10¢-50¢ per trade). Scale only after 100+ trades prove it works.

### Tip 3: Track Your Win Rate

```bash
# After each week, calculate:
Win Rate = Wins / Total Trades

If < 15%: Strategy not working, stop
If 15-20%: Barely profitable, consider stopping
If 20-30%: Good! Keep going
If > 30%: Excellent! Scale up carefully
```

### Tip 4: Understand WHY You Won/Lost

After each trade, note:
- Did price reverse quickly? (Good - strategy working)
- Did price grind higher slowly? (Bad - trend continuing)
- Was there news? (Bad - fundamental move, not reversal)

### Tip 5: Combine with Other Strategies

Contrarian works best alongside other modes:
- Arbitrage: Takes certain opportunities
- Contrarian: Takes asymmetric bets
- Result: Diversified profit sources

## 🆚 Comparison to Other Strategies

| Strategy | Win Rate Needed | Frequency | Stress Level |
|----------|----------------|-----------|--------------|
| **Contrarian** | **15%** | Low (3-5/day) | Low (set & forget) |
| Arbitrage | 53% | Medium (varies) | High (timing crucial) |
| ML Hybrid | 55%+ | Medium | High (complex) |
| Market Making | N/A | High | Low (passive) |

**Contrarian is best for**: Patient traders who want favorable asymmetry

## 🚨 When to Stop

Stop immediately if:
- ✗ Win rate < 10% after 50 trades
- ✗ 10+ losing streak
- ✗ You're emotionally tilted
- ✗ Market structure changes (fees increase, liquidity vanishes)

## ✅ Summary

**Contrarian Fade = Simple + Powerful**

- ✅ Only need 15% win rate (very forgiving)
- ✅ Huge upside (566%+) vs small downside (100%)
- ✅ No ML complexity
- ✅ No timing stress
- ✅ Clean, simple code
- ⚠️ Low frequency (3-5 trades/day)
- ⚠️ Requires patience

**Bottom line**: If you can identify reversals 20% of the time, you'll make money.

---

**Ready to run?**

```bash
python -m src.contrarian_bot
```

Good luck fading the extremes! 🎯
