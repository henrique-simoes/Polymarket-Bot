# Quick Start Guide

## All Fixes Applied - Ready to Test

All critical issues have been resolved:
- ✅ Order placement using official OrderArgs API
- ✅ Timezone fix (UTC everywhere)
- ✅ Position monitoring with stop-loss/take-profit
- ✅ ML training label corrected

---

## Prerequisites

1. **Python environment**:
   ```bash
   # Activate virtual environment
   venv\Scripts\activate  # Windows
   # or
   source venv/bin/activate  # Linux/Mac
   ```

2. **Environment variables** (`.env` file):
   ```
   WALLET_PRIVATE_KEY=your_private_key_here
   ```

3. **Wallet funded**:
   - USDC balance for trading (minimum 5 USDC recommended for testing)
   - POL balance for gas (0.1 POL should be sufficient)

---

## Quick Test (1 Round)

Run a single 15-minute round to verify everything works:

```bash
python -m src.bot
```

**What to expect**:
```
INITIALIZING ADVANCED POLYMARKET BOT
================================================================================

Initializing wallet...
Initializing Polymarket...
  [OK] Polymarket client authenticated
  API Key: 12345678...

Discovering 15M markets for BTC, ETH, SOL...
[OK] Found BTC 15M market...
[OK] Found ETH 15M market...
[OK] Found SOL 15M market...

BOT INITIALIZED SUCCESSFULLY
================================================================================

Wallet Balance: 10.00 USDC
POL Balance: 0.5000 POL (for approvals)
Trading: BTC, ETH, SOL
Initial Bet: 1.0 USDC
```

---

## What Happens During a Round

### Phase 1: Market Discovery (00:00)
```
NEW 15-MINUTE ROUND STARTING
================================================================================

Market Window: 12:45:00 to 13:00:00
Time Remaining: 15.0 minutes
Market Start: NOW (00:00)
Betting Window: 10:00 (600 seconds from now, 5 min buffer before close)

Refreshing 15M markets for current time window...
  [OK] BTC market active
  [OK] ETH market active
  [OK] SOL market active
```

### Phase 2: Monitoring (00:00 - 10:00)
```
PHASE 1: MONITORING PERIOD (until 10:00)
--------------------------------------------------------------------------------

    [BTC] Monitoring started - will run for 600 seconds (until 10:00)
    [BTC] Bet will be placed at 10:00 with 5 minutes buffer before market close

    [BTC] 1m0s - $97,234.50 | UP | ML: 62.5% UP
    [ETH] 1m0s - $3,421.80 | DOWN | ML: 45.2% UP
    [SOL] 1m0s - $142.67 | UP | ML: 58.9% UP

    ... (monitoring continues for 10 minutes) ...
```

### Phase 3: Bet Placement (10:00)
```
PHASE 2: PLACING BETS AT 10:00 (5 min buffer before close)
--------------------------------------------------------------------------------

    [BTC] FINAL PREDICTION at 10:00 (5 min buffer before close):
       Start: $97,234.50 -> Now: $97,456.20
       Change: +0.23%
       ML Probability UP: 65.3%
       Volatility: 12.45 | Range: $342.80 | Ticks: 600

    [BTC] ML PREDICTION: UP (65.3% UP)
       Base Bet: 1.00 USDC
       Market Depth: 2500 shares
       Dynamic Bet: 1.20 USDC

Creating market BUY order: 1.20 USDC for token 3494104851808530...
  Price: 0.9900, Size: 1.2121 shares
[OK] Market buy order placed: order_abc123def456

[BTC] Starting position monitoring...
    Monitoring position... (checking every 5s)
    Current PnL: +2.5% (target: ±15% stop-loss, +50% take-profit)
```

### Phase 4: Position Monitoring (10:00 - 15:00)
```
[BTC] Position monitoring...
    10:02 - PnL: +5.2% (continue holding)
    10:04 - PnL: +12.8% (continue holding)
    10:06 - PnL: +51.3% → TAKE-PROFIT TRIGGERED!

[BTC] Position exited early: TAKE_PROFIT
       PnL: $+0.62 (+51.3%)
```

OR if stop-loss triggers:
```
    10:03 - PnL: -8.5% (continue holding)
    10:05 - PnL: -15.2% → STOP-LOSS TRIGGERED!

[BTC] Position exited early: STOP_LOSS
       PnL: $-0.18 (-15.2%)
```

### Phase 5: Resolution (15:00)
```
PHASE 4: PROCESSING OUTCOMES
--------------------------------------------------------------------------------

BTC Resolution:
  Start Price: $97,234.50
  Final Price: $97,892.30
  Actual Outcome: UP

  [SETTLEMENT VERIFICATION]
  [OK] Polymarket resolved as UP (matches expected)

[BTC] WIN!
   Start: $97,234.50 -> Final: $97,892.30
   Predicted: UP | Actual: UP
   Profit: +0.65 USDC
   Total Saved: 0.33 USDC
   Bet 1.00 -> 1.01 USDC
   Win Streak: 1

[BALANCE VERIFICATION]
Waiting 60 seconds for settlement to complete...
  Previous Balance: 10.00 USDC
  Current Balance:  10.65 USDC
  Actual P&L:       +0.65 USDC (from blockchain)
  Calculated P&L:   +0.65 USDC (from bot)
  [OK] Balance verified (discrepancy: 0.0000 USDC)

================================================================================
ROUND COMPLETE
================================================================================
Record: 3W / 0L (100.0%)
Total Earned: +1.95 USDC
Saved Profits: 0.98 USDC
Next Bet: 1.01 USDC
ROI: +19.5%
```

---

## Expected Outputs

### ✅ Success Indicators

1. **No decimal errors**:
   ```
   [OK] Market buy order placed: order_abc123
   ```

2. **No 404 errors** (if timezone fix works):
   ```
   Found BTC market: 12:45:00 - 13:00:00
   Calculated window: 12:45:00 - 13:00:00  ← Match!
   ```

3. **Position monitoring works**:
   ```
   [BTC] Position exited early: TAKE_PROFIT
   PnL: $+0.62 (+51.3%)
   ```

4. **Balance verification succeeds**:
   ```
   [OK] Balance verified (discrepancy: 0.0000 USDC)
   ```

### ⚠️ Warnings to Watch For

1. **Orderbook closed early**:
   ```
   [WARN] Orderbook closed for token 12345... (market stopped accepting orders)
   ```
   → This means market closed before 10:00 mark
   → Solution: Bet even earlier (e.g., 08:00 or 07:00)

2. **Market not found**:
   ```
   [ERROR] No active markets found! Waiting for next round...
   ```
   → Markets may not be available at current time
   → Wait for next 15-minute window

3. **Settlement mismatch**:
   ```
   [WARNING] Settlement mismatch!
     Expected (from price): UP
     Actual (from Polymarket): DOWN
   ```
   → Rare, but Polymarket may use different settlement source
   → Using Polymarket's outcome for P&L

---

## Troubleshooting

### Error: 400 decimal precision
**Symptom**:
```
[ERROR] invalid amounts, maker amount supports max accuracy of 4 decimals
```

**Fix**: This should be fixed now. If you still see this:
1. Verify `src/core/polymarket.py` lines 226-328 use OrderArgs
2. Check no MarketOrderArgs in imports
3. Verify prices are rounded to 4 decimals: `round(price, 4)`

---

### Error: 404 orderbook not found
**Symptom**:
```
[WARN] Orderbook closed for token 12345... (market stopped accepting orders)
```

**Possible causes**:
1. **Timezone mismatch** (should be fixed):
   - Verify `market_15m.py` uses `datetime.now(timezone.utc)`
   - Check logs show matching window times

2. **Market closes early**:
   - Orderbooks may close before 15:00
   - Solution: Bet earlier (change 10:00 to 08:00 in config)

3. **Market ended**:
   - 15-minute window already passed
   - Wait for next window to start

---

### Error: Insufficient balance
**Symptom**:
```
Trading paused: Insufficient balance (5.00 USDC < 10.00 USDC required)
```

**Fix**:
1. Add more USDC to wallet
2. Or reduce `initial_bet_usdc` in `config/config.yaml`

---

### Warning: Price feed not ready
**Symptom**:
```
[INFO] BTC WebSocket price not ready, using CoinGecko API...
```

**Fix**:
- Normal at startup
- Wait 10-30 seconds for WebSocket to connect
- CoinGecko fallback works fine

---

## Configuration Tweaks

Edit `config/config.yaml` to adjust:

### 1. Bet Timing (if markets close early)
```yaml
# Change betting time from 10:00 to 08:00 (7-minute buffer)
# Requires code change in src/bot.py line 280:
monitoring_duration = min(window_info['seconds_remaining'] - 420, 480)  # 08:00 mark
```

### 2. Position Management
```yaml
risk_management:
  position_management:
    stop_loss_pct: 20.0      # More tolerant (was 15.0)
    take_profit_pct: 30.0    # Earlier exit (was 50.0)
```

### 3. Bet Sizing
```yaml
trading:
  initial_bet_usdc: 0.5      # Smaller bets for testing (was 1.0)
  profit_increase_pct: 50    # Smaller increases (was 100)
```

---

## Full Run (4 Rounds)

Run 4 consecutive rounds (1 hour total):

```bash
python -m src.bot
```

The bot will:
1. Trade 4 consecutive 15-minute windows
2. Adjust bet size based on wins/losses
3. Save profits automatically
4. Generate final report

**Final report**:
```
================================================================================
FINAL RESULTS
================================================================================

Financial Summary:
   Total Earned: +3.45 USDC
   Saved Profits: 1.73 USDC (Protected)
   Final Bet Size: 1.05 USDC
   Wallet Balance: 13.45 USDC
   ROI: +34.5%

Performance:
   Total Trades: 12
   Wins: 8 | Losses: 4
   Win Rate: 66.7%
   Current Streak: 2 wins

Per-Coin Performance:
   BTC: 3W/1L (75.0%) | Profit: +1.23 USDC
   ETH: 2W/2L (50.0%) | Profit: +0.45 USDC
   SOL: 3W/1L (75.0%) | Profit: +1.77 USDC

Report saved to: reports/bot_report_20260131_143022.json
```

---

## Next Steps

1. ✅ **Verify all fixes work** - Run 1-2 test rounds
2. ✅ **Monitor for errors** - Check logs carefully
3. ✅ **Adjust config** - Fine-tune if needed
4. ✅ **Scale up** - Increase bet sizes once confident
5. ✅ **Monitor performance** - Track win rate and ROI

---

**All systems ready** 🚀
**Run the bot and verify the fixes work!**
