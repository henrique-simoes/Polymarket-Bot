# ✅ FINAL INTEGRATION - Real 15-Minute Markets

## 🎯 Original Goal Restored!

Your bot now trades on **real Polymarket 15-minute crypto price prediction markets** with full ML integration!

**Live Markets**: https://polymarket.com/crypto/15M

---

## What's Integrated

### ✅ Original Architecture (100% Preserved)
- **15-minute candle monitoring** (14:58 seconds)
- **Last-second betting** (14:59 - just before resolution)
- **Continuous ML learning** (every 5 observations)
- **Multi-timeframe analysis** (1s, 1m, 15m, 1h, 4h, 1d, 1w)
- **Technical indicators** (RSI, MACD, Bollinger Bands, etc.)
- **Profit protection** (save 100% immediately)
- **Money management** (increase on wins, reset on losses)
- **Risk management** (circuit breakers, loss limits)
- **Parallel coin trading** (BTC, ETH, SOL)

### ✅ Now Connected to REAL Markets
- Real Polymarket 15M markets via SDK
- Real Chainlink oracle price resolution
- Real order placement on CLOB
- Real profit/loss tracking
- No simulation - everything is live!

---

## How It Works

### 1. Market Structure
```
┌─────────────────────────────────────────────────────┐
│ 15-Minute Market Cycle                              │
├─────────────────────────────────────────────────────┤
│ 00:00  Market starts (capture start price)         │
│ 00:01-14:58  Monitor & learn from price movements  │
│ 14:59  Place bet based on ML prediction            │
│ 15:00  Market resolves via Chainlink oracle        │
│        - UP if final_price >= start_price           │
│        - DOWN if final_price < start_price          │
└─────────────────────────────────────────────────────┘
```

### 2. Your Bot's Process
```
For each 15-minute period:

Phase 1: MONITORING (00:00 - 14:58)
├─ Fetch real crypto prices every second
├─ Feed to multi-timeframe analyzer (1s→1w)
├─ Extract 38+ technical features
├─ Continuous ML learning (every 5 observations)
└─ Build prediction confidence

Phase 2: BETTING (14:59)
├─ Get final ML prediction (prob_up)
├─ Decide: UP if prob_up > 0.5, else DOWN
├─ Calculate bet size (with profit reinvestment)
└─ Place REAL order on Polymarket 15M market

Phase 3: RESOLUTION (15:00)
├─ Wait for Chainlink oracle resolution
├─ Compare actual vs predicted outcome
└─ Calculate profit/loss

Phase 4: MONEY MANAGEMENT
├─ If WIN: Save profit, increase bet by X%
├─ If LOSS: Reset to initial bet
└─ Update ML models with outcome
```

---

## 📁 New Files Created

### `src/core/market_15m.py`
**Purpose**: Bridge between your bot and Polymarket's 15M markets

**Key Features**:
- Discover active 15M markets for BTC/ETH/SOL
- Get token IDs (YES/NO) for each market
- Fetch real crypto prices (for monitoring)
- Place predictions (UP/DOWN bets)
- Check market resolution
- Handle 15-minute windows

**Main Methods**:
```python
market_15m.get_current_15m_markets(['BTC', 'ETH', 'SOL'])
market_15m.get_current_price('BTC')  # Market price (probability)
market_15m.get_real_crypto_price('BTC')  # Actual BTC price
market_15m.place_prediction('BTC', 'UP', 1.0)  # Place bet
market_15m.check_resolution('BTC', start, end)  # Verify outcome
```

---

## 🚀 Setup Instructions

### Step 1: Install Dependencies
```bash
venv\Scripts\activate.bat
pip install -r requirements.txt
```

**New dependency**: `py-clob-client` (official Polymarket SDK)

### Step 2: Configure .env
```bash
# Required
WALLET_PRIVATE_KEY=0x...  # Your MetaMask private key
POLYGON_RPC_URL=https://polygon-rpc.com

# Optional (for better price feeds)
BINANCE_WS_URL=wss://stream.binance.com:9443/ws
```

### Step 3: Approve Tokens (ONE TIME)

**For self-managed wallets (MetaMask) only:**
```bash
python -c "from src.core.wallet import WalletManager; WalletManager().approve_polymarket_trading()"
```

**What this does**:
- Approves USDC for Polymarket Exchange
- Approves CTF (Conditional Tokens) for Polymarket Exchange
- **Cost**: ~$0.10 worth of POL (Polygon native token, one-time gas fee)

**Note**: If you use email/Google signup on Polymarket, gas is covered by their proxy wallet

### Step 4: Configure Trading
Edit `config/config.yaml`:
```yaml
trading:
  initial_bet_usdc: 1.0  # Start small!
  profit_increase_pct: 10
  coins:
    - BTC
    - ETH
    - SOL
```

### Step 5: Run the Bot!
```bash
python -m src
```

---

## 💰 Cost Breakdown

### One-Time Costs (Self-Managed Wallets Only):
- Token approvals: ~$0.10 POL ✅ (only if using MetaMask/self-managed wallet)
- **Email/Google signups**: $0 (Polymarket covers gas via proxy wallet)

### Per-Trade Costs:
- **Gas fees**: $0 (CLOB trading is off-chain, no gas required)
- **Only cost**: What you bet (in USDC)

### Polymarket Trading Fees:
- 15-minute markets have **variable taker fees** up to 3%
- Fee depends on market probability (highest at 50/50)
- Example: $1 bet at 50% odds ≈ $0.03 fee
- Most other markets: No trading fees

---

## 🎮 What to Expect

### First Run:
```
==========================================
INITIALIZING ADVANCED POLYMARKET BOT
==========================================

Initializing wallet...
  Wallet: 0x123...
  USDC Balance: 10.50 USDC
  POL Balance: 0.0500 POL (only needed for initial approvals)

Initializing Polymarket...
  Polymarket client authenticated
  API Key: abc12345...

Discovering 15M markets for BTC, ETH, SOL...
  ✓ Found BTC 15M market: market_xyz
  ✓ Found ETH 15M market: market_abc
  ✓ Found SOL 15M market: market_def

Initializing Machine Learning...
  Continuous Learning Engine initialized
  Buffer size: 5000
  Retrain frequency: every 5 observations

...

✓ BOT INITIALIZED SUCCESSFULLY
==========================================
```

### During Trading:
```
NEW 15-MINUTE ROUND STARTING
==========================================
Market Window: 09:00:00 to 09:15:00
Time Remaining: 14.8 minutes

PHASE 1: MONITORING PERIOD (14:58)
──────────────────────────────────────────

  [BTC] Monitoring started
    Start Price: $45,234.56

  [BTC] 1m0s - $45,245.12 | UP | ML: 52.3% UP
  [BTC] 2m0s - $45,256.78 | UP | ML: 54.1% UP
  [BTC] Model updated | Samples: 124 | Recent accuracy: 58.3%
  ...
  [BTC] 14m58s - $45,289.34 | UP | ML: 61.2% UP

  [BTC] FINAL PREDICTION at 14:59:
    Start: $45,234.56 → Now: $45,289.34
    Change: +0.12%
    ML Probability UP: 61.2%
    Volatility: 12.45 | Range: $67.89 | Ticks: 898

PHASE 2: PLACING BETS AT 14:59
──────────────────────────────────────────

  [BTC] ML PREDICTION: UP (61.2% UP)
  Bet Size: 1.50 USDC

  Creating market BUY order: 1.50 USDC for token_xyz
  ✓ Market buy order placed: order_123

PHASE 3: WAITING FOR RESOLUTION...
Waiting 61 seconds until market resolves...

PHASE 4: PROCESSING OUTCOMES
──────────────────────────────────────────

BTC Resolution:
  Start Price: $45,234.56
  Final Price: $45,301.23
  Actual Outcome: UP

[BTC] WIN!
  Start: $45,234.56 → Final: $45,301.23
  Predicted: UP | Actual: UP
  Profit: +0.42 USDC
  💎 Total Saved: 0.42 USDC
  📈 Bet 1.50 → 1.54 USDC
  🔥 Win Streak: 1

ROUND COMPLETE
==========================================
Record: 1W / 0L (100.0%)
💰 Total Earned: +0.42 USDC
💎 Saved Profits: 0.42 USDC
🎲 Next Bet: 1.54 USDC
📈 ROI: +28.0%
==========================================
```

---

## 🔧 Key Components

### Original Components (Unchanged):
✅ `src/ml/features.py` - FeatureExtractor (38+ features)
✅ `src/ml/models.py` - EnsembleModel (RF + GB)
✅ `src/ml/learning.py` - ContinuousLearningEngine
✅ `src/analysis/timeframes.py` - MultiTimeframeAnalyzer (1s-1w)
✅ `src/analysis/arbitrage.py` - PriceArbitrageDetector
✅ `src/trading/strategy.py` - TradingStrategy (money management)
✅ `src/trading/risk.py` - RiskManager (circuit breakers)
✅ `src/core/monitoring.py` - RealTimeMonitor

### Updated Components:
🔄 `src/core/polymarket.py` - Now uses official SDK
🔄 `src/core/wallet.py` - Added CTF token approval
🔄 `src/bot.py` - Wired to real 15M markets

### New Components:
✨ `src/core/market_15m.py` - 15M market integration helper

---

## ⚠️ Important Notes

### 1. Market Availability
- 15M markets for BTC, ETH, SOL are usually active
- Check https://polymarket.com/crypto/15M to verify
- Bot will warn if markets not found

### 2. Timing
- Markets resolve **exactly** every 15 minutes
- Bot bets at 14:59 (1 second before resolution)
- Resolution via Chainlink oracle (decentralized)

### 3. Fees
- Variable taker fees (up to 3%)
- Higher fees at 50/50 odds
- Factor into profit calculations

### 4. Minimum Bets
- Start with 1-2 USDC to test
- Ensure you have enough USDC for multiple rounds
- For self-managed wallets: Keep ~$0.10 POL for initial token approvals (one-time)

---

## 📊 Success Metrics

Your bot tracks:
- **Win rate**: % of correct predictions
- **ROI**: Return on initial investment
- **Saved profits**: Protected money (never at risk)
- **Win streaks**: Consecutive wins
- **Per-coin performance**: BTC vs ETH vs SOL

All saved to: `reports/bot_report_YYYYMMDD_HHMMSS.json`

---

## 🎯 Next Steps

1. **Test with small amounts** (1-2 USDC)
2. **Run for multiple rounds** to see ML learning in action
3. **Monitor accuracy** - should improve over time
4. **Adjust parameters** in config.yaml as needed
5. **Scale up** when confident

---

## 🆘 Troubleshooting

### "No 15M market found for BTC"
- Check https://polymarket.com/crypto/15M
- Markets may be temporarily paused
- Try again in 15 minutes

### "Order placement failed"
- Check USDC balance
- Verify tokens are approved
- Check market is still active

### "Authentication failed"
- Verify WALLET_PRIVATE_KEY in .env
- Ensure wallet has some USDC

### Bot makes wrong predictions
- ML needs more data (keep running)
- Continuous learning improves over time
- 15M markets are inherently unpredictable

---

## 🎉 You're All Set!

Your bot now:
✅ Trades on REAL Polymarket 15-minute markets
✅ Uses all your ML models and strategies
✅ Monitors prices continuously
✅ Learns from every observation
✅ Protects profits immediately
✅ Manages risk automatically

**Original design fully preserved + SDK integration complete!**

Start with small bets and watch it learn! 🚀
