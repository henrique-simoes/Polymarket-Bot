# Polymarket Crypto Trading Bot - Complete Technical Documentation

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [Core Objectives](#core-objectives)
3. [System Architecture](#system-architecture)
4. [Critical Design Decisions](#critical-design-decisions)
5. [How Everything Works](#how-everything-works)
6. [Money Management System](#money-management-system)
7. [Machine Learning & Prediction](#machine-learning--prediction)
8. [Polymarket Integration](#polymarket-integration)
9. [Next Steps & Improvements](#next-steps--improvements)
10. [Technical Requirements](#technical-requirements)

---

## 📖 Project Overview

### What This Bot Does
An **autonomous cryptocurrency trading bot** that predicts 15-minute price movements (UP/DOWN) for Bitcoin (BTC), Ethereum (ETH), and Solana (SOL) on **Polymarket**, a decentralized prediction market platform.

### Why It Was Built This Way
After discovering that **betting at the start of a 15-minute period** (naive approach) wastes valuable real-time data, we rebuilt the system to:
- **Monitor continuously** during the entire 15-minute candle
- **Learn from every price tick** (not just final outcomes)
- **Place bets at the last second** (14:59) with maximum information
- **Protect profits immediately** while compounding wins intelligently

---

## 🎯 Core Objectives

### Primary Goals
1. **Maximize prediction accuracy** by using multi-timeframe analysis (7 timeframes: 1s, 1m, 15m, 1h, 4h, 1d, 1w)
2. **Learn continuously** from every price movement, not just trade outcomes
3. **Trade all 3 coins simultaneously** (BTC, ETH, SOL) for diversification
4. **Protect profits** - lock away winnings immediately, never risk saved money
5. **Adapt in real-time** - if market moves against prediction mid-candle, learn and adjust

### Secondary Goals
1. Detect **arbitrage opportunities** between Polymarket oracle and major exchanges (Binance, Coinbase)
2. Use **WebSocket feeds** for 1-second price updates (not REST API polling)
3. **Auto-compound** wins by adding 10% of profit to next bet (user-configurable)
4. **Reset to safety** - return to default bet size on ANY single loss
5. Generate **detailed reports** showing per-coin performance and longest streaks

---

## 🏗️ System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     POLYMARKET TRADING BOT                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ WalletManager  │  │ Polymarket      │  │ Real-Time       │ │
│  │                │  │ Mechanics       │  │ Monitor         │ │
│  │ - USDT Balance │  │                 │  │                 │ │
│  │ - Transactions │  │ - YES/NO Shares │  │ - Price Ticks   │ │
│  │ - Polygon Net  │  │ - Resolution    │  │ - Continuous    │ │
│  └────────────────┘  └─────────────────┘  │   Learning      │ │
│                                            └─────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │         Multi-Timeframe Analyzers (3 coins)               │ │
│  │                                                            │ │
│  │  BTC: [1s, 1m, 15m, 1h, 4h, 1d, 1w] → 21 features        │ │
│  │  ETH: [1s, 1m, 15m, 1h, 4h, 1d, 1w] → 21 features        │ │
│  │  SOL: [1s, 1m, 15m, 1h, 4h, 1d, 1w] → 21 features        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │     Continuous Learning Engine (Online ML)                │ │
│  │                                                            │ │
│  │  - Random Forest (50 trees, depth 10)                     │ │
│  │  - Gradient Boosting (50 estimators, depth 5)             │ │
│  │  - Retrains every 5 observations                          │ │
│  │  - Buffer: 5000 recent observations                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Arbitrage Detector                           │ │
│  │                                                            │ │
│  │  - Binance WebSocket (real-time)                          │ │
│  │  - Polymarket Oracle prices                               │ │
│  │  - Detects >0.1% price differences                        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. WebSocket Feeds (Binance/Coinbase)
   ↓ (1-second ticks)
2. Multi-Timeframe Analyzers
   ↓ (aggregate into 7 timeframes)
3. Feature Extraction (23 features per coin)
   ↓
4. Continuous Learning Engine
   ↓ (updates every 5 observations)
5. Real-Time Monitor
   ↓ (tracks for 14:58)
6. Final Prediction at 14:59
   ↓
7. Bet Placement (last second)
   ↓
8. Market Resolution at 15:00
   ↓
9. Outcome Learning & Money Management
```

---

## 🔑 Critical Design Decisions

### Decision 1: Bet Timing - Last Second (14:59) vs Start (0:00)

**❌ Original Approach (Rejected):**
```
0:00 → Analyze → Predict → Bet → Wait 15 minutes → Outcome
Problem: 898 seconds of price data WASTED
```

**✅ Final Approach (Implemented):**
```
0:00 → Start monitoring
0:01-14:58 → Learn from every price tick (898 observations)
14:59 → Make final prediction with ALL data → Bet
15:00 → Outcome
```

**Why This Matters:**
- If price crashes at minute 5, old approach is already locked into wrong bet
- New approach sees the crash, learns from it, adjusts prediction by 14:59
- **Result:** Far more accurate predictions using complete candle data

### Decision 2: Continuous Learning vs Batch Learning

**❌ Batch Learning (Most Bots):**
```
Trade 1 → Wait for outcome → Store result
Trade 2 → Wait for outcome → Store result
...
Trade 20 → Finally retrain model
```

**✅ Continuous Learning (Our Bot):**
```
Second 1 → Price tick → Learn direction → Update model (if 5 ticks passed)
Second 2 → Price tick → Learn direction → Update model (if 5 ticks passed)
...
Second 898 → Price tick → Learn → Final prediction
```

**Why This Matters:**
- Don't waste money waiting for 20 trades to accumulate
- Model adapts immediately to market regime changes
- Learn from EVERY price movement, not just trade outcomes

### Decision 3: Multi-Coin Parallel Trading

**Why Trade All 3 Coins Simultaneously:**
1. **Diversification** - If BTC loses but ETH/SOL win, still profitable
2. **3x Learning Speed** - Get 3x more training data per round
3. **Efficiency** - Not waiting for one coin to finish before trading next
4. **Better Statistics** - Can identify which coins strategy works best on

**Balance Requirement:**
- Need `initial_bet × 3` minimum (e.g., $30 for $10 bets)

### Decision 4: Money Management - Immediate Profit Lock

**The Problem We Solved:**
Traditional compounding: Win 10 trades → big bet → ONE loss wipes out all gains

**Our Solution:**
```python
Win:  profit → 100% saved (locked) + add 10% of profit to next bet
Loss: reset to default bet (saved profits untouched)
```

**Example:**
```
Win $10 → Save $10, next bet = $11 (original $10 + 10% of $10)
Win $11 → Save $11, next bet = $12.10
...
Win $23 → Save $23, total saved = $159
LOSE $23 → Saved profits still $159! Next bet back to $10
```

---

## 🔧 How Everything Works

### 1. Multi-Timeframe Analysis

**Purpose:** Understand market context at all scales

**Implementation:**
```python
For each coin (BTC/ETH/SOL):
  - 1-second candles: Short-term momentum (last hour)
  - 1-minute candles: Intraday trend (last 24 hours)
  - 15-minute candles: Current session (last 7 days)
  - 1-hour candles: Daily patterns (last 30 days)
  - 4-hour candles: Weekly context (last 60 days)
  - 1-day candles: Monthly trend (last year)
  - 1-week candles: Long-term direction (2 years)
```

**Features Extracted (per timeframe):**
1. **Direction**: Short MA > Long MA? (Binary: 1 or 0)
2. **Strength**: Distance between MAs (% difference)
3. **Momentum**: Rate of price change over period

**Total:** 7 timeframes × 3 features = **21 timeframe features**

**Plus 2 current candle features:**
- Volatility (std dev / mean of last 60 seconds)
- Momentum (current price vs 60 seconds ago)

**Grand Total:** **23 features** fed into ML model

### 2. Continuous Learning Engine

**Architecture:**
- **Ensemble Model**: Random Forest + Gradient Boosting
- **Training Data**: Last 5000 observations (rolling window)
- **Update Frequency**: Every 5 new observations
- **Thread-Safe**: Uses mutex locks for parallel coin processing

**Learning Process:**

```python
# Every second during 15-min candle:
current_price = get_live_price()
price_60s_ago = price_history[-60]

# Determine short-term direction
if current_price > price_60s_ago:
    label = 1  # UP
else:
    label = 0  # DOWN

# Extract all 23 features at this moment
features = extract_features(coin)

# Add to learning buffer
observation_buffer.append({
    'coin': coin,
    'features': features,
    'direction': label
})

# Retrain if enough new data
if len(new_observations) >= 5:
    X = recent_features[-100:]  # Last 100 observations
    y = recent_labels[-100:]
    
    scaler.fit_transform(X)
    random_forest.fit(X, y)
    gradient_boosting.fit(X, y)
```

**What It Learns:**
- "When 1d trend is UP + 1h trend is DOWN + high volatility → next minute usually UP"
- "When all timeframes aligned DOWN → strong DOWN continuation"
- "When price just reversed (1m trend different from 15m) → reversal often continues"

### 3. Real-Time Monitoring (14:58 Period)

**Flow:**
```python
def monitor_candle_period(coin, start_price):
    for second in range(0, 898):  # 14 min 58 sec
        # Get current price (from WebSocket)
        current_price = fetch_live_price(coin)
        
        # Add to multi-timeframe analyzer
        mtf_analyzer[coin].add_tick(timestamp, current_price)
        
        # Extract features
        features = extract_features(coin)
        
        # Update monitor (triggers learning)
        monitor.update_price(coin, current_price, features)
        
        # Every 60 seconds, log status
        if second % 60 == 0:
            prob_up = predict(coin, features)
            print(f"{second//60}m: Price ${current_price} | ML: {prob_up*100:.1f}% UP")
        
        sleep(1)
    
    # At 14:59, get final prediction
    return monitor.get_final_prediction(coin)
```

**Output Example:**
```
[BTC] 0m: Price $45,123 | ML: 52.3% UP
[BTC] 1m: Price $45,135 | ML: 54.1% UP
[BTC] 2m: Price $45,089 | ML: 48.7% UP  ← Saw price drop, adjusted!
...
[BTC] 14m: Price $45,201 | ML: 68.9% UP
[BTC] FINAL at 14:59: UP prediction with 68.9% confidence
```

### 4. Bet Placement (Last Second)

**Polymarket Share Mechanics:**
```python
# If model predicts 68.9% chance of UP:
YES_shares = $0.689 each
NO_shares = $0.311 each
(YES + NO always = $1.00)

# To bet $10 on UP:
shares_to_buy = $10 / $0.689 = 14.51 shares

# If UP wins:
payout = 14.51 × $1.00 = $14.51
profit = $14.51 - $10.00 = $4.51

# If DOWN wins:
payout = $0.00
profit = -$10.00
```

**Bet Placement Code:**
```python
def place_bet_at_last_second(coin, prediction):
    prob_up = prediction['prob_up']
    
    if prob_up > 0.5:
        outcome = 'UP'
        share_price = prob_up
    else:
        outcome = 'DOWN'
        share_price = 1 - prob_up
    
    shares = wallet.buy_shares(coin, outcome, current_bet, share_price)
    
    return {
        'outcome': outcome,
        'shares': shares,
        'share_price': share_price,
        'cost': current_bet
    }
```

### 5. Market Resolution & Learning

**Polymarket Resolution Logic:**
```python
# At 15:00, market resolves based on Chainlink oracle:
if final_price >= start_price:
    winning_outcome = 'UP'
    YES_shares_pay = $1.00 each
    NO_shares_pay = $0.00 each
else:
    winning_outcome = 'DOWN'
    YES_shares_pay = $0.00 each
    NO_shares_pay = $1.00 each
```

**Outcome Processing:**
```python
# Calculate profit
won = (predicted_outcome == actual_outcome)
if won:
    payout = shares × $1.00
    profit = payout - cost
else:
    profit = -cost

# Update learning buffer with final outcome
observation_buffer.append({
    'features': features_at_14_59,
    'label': 1 if actual_outcome == 'UP' else 0,
    'won': won
})

# Money management (detailed in next section)
if won:
    save_profit(profit)
    increase_bet()
else:
    reset_to_default_bet()
```

---

## 💰 Money Management System

### Core Principles

1. **Profits are sacred** - Saved immediately, never risked again
2. **Compound intelligently** - Add small % of profit to next bet
3. **Protect capital** - Reset to default on ANY loss
4. **User configurable** - Both default bet and increase % adjustable

### Configuration

```python
initial_bet_usdt = 10         # Default bet size (always return here on loss)
profit_increase_pct = 10      # % of PROFIT to add to next bet
```

### Bet Sizing Logic

```python
class BetManager:
    def __init__(self, initial_bet, increase_pct):
        self.default_bet = initial_bet
        self.current_bet = initial_bet
        self.increase_pct = increase_pct
        self.saved_profits = 0
        self.consecutive_wins = 0
    
    def process_win(self, profit):
        # Lock profit away
        self.saved_profits += profit
        
        # Calculate increase for next bet
        bet_increase = profit * (self.increase_pct / 100)
        
        # Add only the increase to current bet
        self.current_bet += bet_increase
        
        # Update streak
        self.consecutive_wins += 1
        
        print(f"💎 Saved: ${profit:.2f}")
        print(f"📈 Next bet: ${self.current_bet:.2f}")
    
    def process_loss(self, amount_lost):
        # Saved profits NEVER touched
        # Just reset bet to default
        self.current_bet = self.default_bet
        self.consecutive_wins = 0
        
        print(f"🔄 Reset to default: ${self.default_bet}")
```

### Example Scenarios

**Scenario 1: 10-Win Streak Then Loss**

```
Initial: current_bet = $10, saved = $0

Win 1:  Bet $10 → Profit $6.50 → Saved $6.50 → Next $10.65
Win 2:  Bet $10.65 → Profit $6.92 → Saved $13.42 → Next $11.34
Win 3:  Bet $11.34 → Profit $7.37 → Saved $20.79 → Next $12.08
Win 4:  Bet $12.08 → Profit $7.85 → Saved $28.64 → Next $12.87
Win 5:  Bet $12.87 → Profit $8.36 → Saved $37.00 → Next $13.70
Win 6:  Bet $13.70 → Profit $8.91 → Saved $45.91 → Next $14.59
Win 7:  Bet $14.59 → Profit $9.48 → Saved $55.39 → Next $15.54
Win 8:  Bet $15.54 → Profit $10.10 → Saved $65.49 → Next $16.55
Win 9:  Bet $16.55 → Profit $10.76 → Saved $76.25 → Next $17.63
Win 10: Bet $17.63 → Profit $11.46 → Saved $87.71 → Next $18.77

LOSS:   Bet $18.77 → Lost $18.77
        Saved still $87.71 ← PROTECTED!
        Net total = $87.71 - $18.77 = $68.94 profit
        Next bet = $10 (back to default)
```

**Key Insight:** Even after losing $18.77, you're still up $68.94 overall!

**Scenario 2: Alternating Wins/Losses**

```
Win:  Bet $10 → +$6.50 → Saved $6.50 → Next $10.65
Loss: Bet $10.65 → -$10.65 → Saved $6.50 (unchanged) → Next $10
Win:  Bet $10 → +$6.50 → Saved $13.00 → Next $10.65
Loss: Bet $10.65 → -$10.65 → Saved $13.00 (unchanged) → Next $10

Net: +$6.50 - $10.65 + $6.50 - $10.65 = -$8.30
But saved profits = $13.00
True total = $13.00 - $8.30 = $4.70 profit
```

### Balance Tracking

```python
# Three separate metrics tracked:

1. current_bet
   - Amount being bet right now
   - Resets to default on loss
   - Grows on wins

2. saved_profits
   - All winnings locked away
   - NEVER decreases
   - Only increases on wins

3. total_earned
   - Running P&L including active bets
   - Can be negative if recent losses
   - Formula: saved_profits - recent_losses
```

---

## 🤖 Machine Learning & Prediction

### Model Architecture

**Ensemble Approach:**
```python
models = {
    'rf': RandomForestClassifier(
        n_estimators=50,      # 50 decision trees
        max_depth=10,         # Prevent overfitting
        random_state=42       # Reproducible
    ),
    'gb': GradientBoostingClassifier(
        n_estimators=50,      # 50 boosting stages
        max_depth=5,          # Shallower trees
        learning_rate=0.1,    # Conservative learning
        random_state=42
    )
}
```

**Why Ensemble:**
- Random Forest: Captures non-linear patterns, robust to noise
- Gradient Boosting: Sequential learning, corrects previous errors
- Average predictions: More stable than single model

### Feature Engineering

**Input Features (23 total):**

```python
# Timeframe features (21):
for tf in ['1s', '1m', '15m', '1h', '4h', '1d', '1w']:
    features.append(trend_direction[tf])  # Binary: 1=UP, 0=DOWN
    features.append(trend_strength[tf])   # Float: 0.0001 to 0.05
    features.append(momentum[tf])         # Float: -0.1 to +0.1

# Current candle features (2):
features.append(volatility_last_60s)     # Float: 0.0 to 0.02
features.append(momentum_last_60s)       # Float: -0.01 to +0.01
```

**Feature Scaling:**
```python
# StandardScaler: (x - mean) / std_dev
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Example:
# Raw momentum: 0.0234
# Scaled: (0.0234 - 0.0015) / 0.008 = 2.74
```

### Training Process

**Initial Training:**
```python
# On bot startup, train with historical data
for coin in ['BTC', 'ETH', 'SOL']:
    # Generate 100 candles of historical data
    historical_data = fetch_historical(coin, periods=100)
    
    # Extract features and labels
    X, y = [], []
    for i in range(20, len(historical_data)-1):
        features = extract_features(historical_data[:i+1])
        label = 1 if historical_data[i+1].close > historical_data[i].close else 0
        X.append(features)
        y.append(label)
    
    # Train both models
    X_scaled = scaler.fit_transform(X)
    models['rf'].fit(X_scaled, y)
    models['gb'].fit(X_scaled, y)
    
    print(f"{coin} model trained with {len(X)} samples")
```

**Continuous Updates:**
```python
# During live trading, update every 5 observations
observation_buffer = deque(maxlen=5000)

def add_observation(features, label):
    observation_buffer.append({'features': features, 'label': label})
    
    if len(observation_buffer) % 5 == 0:  # Every 5 observations
        # Get recent data
        recent = list(observation_buffer)[-100:]
        X = [obs['features'] for obs in recent]
        y = [obs['label'] for obs in recent]
        
        # Retrain
        X_scaled = scaler.fit_transform(X)
        models['rf'].fit(X_scaled, y)
        models['gb'].fit(X_scaled, y)
```

### Prediction Process

```python
def predict(coin, features):
    # Scale features
    X = scaler.transform(features.reshape(1, -1))
    
    # Get probabilities from both models
    rf_proba = models['rf'].predict_proba(X)[0]
    # rf_proba = [0.32, 0.68]  # [prob_DOWN, prob_UP]
    
    gb_proba = models['gb'].predict_proba(X)[0]
    # gb_proba = [0.28, 0.72]  # [prob_DOWN, prob_UP]
    
    # Average the UP probabilities
    avg_prob_up = (rf_proba[1] + gb_proba[1]) / 2
    # avg_prob_up = (0.68 + 0.72) / 2 = 0.70
    
    return avg_prob_up  # 70% chance of UP
```

### Handling Edge Cases

```python
# Not enough data yet
if len(observation_buffer) < 20:
    return 0.5  # 50/50 guess

# Model not trained yet
if coin not in models:
    initialize_model(coin)
    return 0.5

# Extreme probabilities (>95% or <5%)
# Add confidence dampening to prevent overconfidence
if prob > 0.95:
    prob = 0.95
elif prob < 0.05:
    prob = 0.05
```

---

## 🔗 Polymarket Integration

### How Polymarket Works

**Binary Markets:**
- Each market has **YES** and **NO** outcomes
- YES + NO share prices always sum to **$1.00**
- Winning shares pay **$1.00**, losing shares pay **$0.00**

**Example:**
```
Market: "Will BTC be UP in next 15 minutes?"
Current odds: 65% YES, 35% NO

YES shares = $0.65 each
NO shares = $0.35 each

If you buy 10 YES shares:
- Cost = 10 × $0.65 = $6.50
- If BTC goes UP: Payout = 10 × $1.00 = $10.00 → Profit = $3.50
- If BTC goes DOWN: Payout = $0.00 → Loss = -$6.50
```

### Market Resolution

**15-Minute Markets:**
- Open at: :00, :15, :30, :45 of each hour
- Close at: :15, :30, :45, :00 of next period
- Resolution source: **Chainlink price oracles**

**Resolution Logic:**
```python
start_price = oracle.get_price(start_timestamp)
end_price = oracle.get_price(end_timestamp)

if end_price >= start_price:
    winning_outcome = 'UP'
else:
    winning_outcome = 'DOWN'
```

**Important:** Even $0.01 difference determines outcome!

### Trading Mechanics

**Placing Bets:**
```python
# 1. Approve USDT spending
wallet.approve_polymarket(amount_usdt)

# 2. Buy shares
outcome = 'UP'  # or 'DOWN'
shares = polymarket.buy_shares(
    market_id='BTC_15m_20250129_1430',
    outcome=outcome,
    amount_usdt=10.0
)

# 3. Wait for resolution (15 minutes)

# 4. If won, shares automatically pay $1 each
# If lost, shares become worthless
```

**Slippage & Fees:**
```python
# Polymarket has spread (bid-ask)
spread = 0.02 to 0.05  # 2-5 cents typical

# Example:
market_price = 0.65
bid = 0.63  # You sell here
ask = 0.67  # You buy here

# If buying YES at ask:
effective_cost = 0.67 (worse than market 0.65)

# Fee: ~2% on trades (as of 2025)
```

### Wallet Integration

**Requirements:**
- **Network**: Polygon (not Ethereum mainnet)
- **Currency**: USDT (6 decimals, not 18)
- **Gas**: MATIC tokens for transaction fees

**Setup:**
```python
from web3 import Web3
from eth_account import Account

# Connect to Polygon
w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))

# Load wallet
private_key = "your_private_key"
account = Account.from_key(private_key)

# USDT contract on Polygon
usdt_address = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
usdt_contract = w3.eth.contract(address=usdt_address, abi=usdt_abi)

# Check balance
balance = usdt_contract.functions.balanceOf(account.address).call()
balance_usdt = balance / 10**6  # USDT has 6 decimals
```

### API Integration Points

**Current (Simulated):**
```python
# These are placeholders - need real integration:

1. fetch_current_price(coin)
   → Replace with: Binance WebSocket or Polymarket API

2. wallet.buy_shares(...)
   → Replace with: Actual Polymarket smart contract call

3. get_market_resolution(...)
   → Replace with: Chainlink oracle query or Polymarket API
```

**Real WebSocket (Binance):**
```python
import websockets
import asyncio

async def binance_websocket(symbol):
    uri = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@trade"
    
    async with websockets.connect(uri) as ws:
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            
            price = float(data['p'])
            timestamp = data['T']
            
            # Feed to multi-timeframe analyzer
            mtf_analyzer.add_tick(timestamp, price)
```

---

## 🚀 Next Steps & Improvements

### Immediate Priorities (For Claude Code)

#### 1. **Real Exchange Integration**
```python
# Replace simulated prices with real WebSocket feeds

TODO:
- [ ] Implement Binance WebSocket for BTC/ETH/SOL
- [ ] Add Coinbase WebSocket as backup
- [ ] Handle reconnections and error states
- [ ] Store tick data efficiently (use ClickHouse or TimescaleDB?)
```

#### 2. **Actual Polymarket API**
```python
# Current bot uses simulated betting

TODO:
- [ ] Research Polymarket SDK/API documentation
- [ ] Implement real share buying/selling
- [ ] Add transaction confirmation tracking
- [ ] Handle failed transactions (retry logic)
- [ ] Monitor gas prices (optimize transaction timing)
```

#### 3. **Enhanced Learning**
```python
# Current: Simple RF + GB ensemble

IMPROVEMENTS:
- [ ] Add LSTM/GRU for time-series patterns
- [ ] Implement attention mechanism (which timeframe is most important?)
- [ ] Meta-learning: Learn which features work best for each coin
- [ ] Confidence-weighted predictions (bet more when confident)
```

#### 4. **Risk Management Enhancements**
```python
# Current: Simple bet sizing with reset on loss

IMPROVEMENTS:
- [ ] Kelly Criterion for optimal bet sizing
- [ ] Maximum drawdown limits (pause if losing 20% of capital)
- [ ] Per-coin bet allocation (if BTC performs poorly, reduce BTC bets)
- [ ] Time-of-day filters (avoid low liquidity periods)
- [ ] Volatility-adjusted position sizing
```

#### 5. **Backtesting Framework**
```python
# Need to validate strategy before going live

TODO:
- [ ] Download historical 1-second price data
- [ ] Simulate exact 15-minute market cycles
- [ ] Calculate realistic fees and slippage
- [ ] Generate performance reports (Sharpe ratio, max drawdown, etc.)
- [ ] Compare vs buy-and-hold benchmark
```

#### 6. **Production Infrastructure**
```python
# Bot needs to run 24/7 reliably

TODO:
- [ ] Docker containerization
- [ ] Automatic restart on crash
- [ ] Health monitoring (Prometheus + Grafana)
- [ ] Alert system (Telegram/Discord notifications)
- [ ] Database for trade history (PostgreSQL)
- [ ] Automated daily reports
```

---

### Advanced Features (Future Roadmap)

#### 1. **Market Microstructure Analysis**
```python
# Exploit Polymarket-specific patterns

IDEAS:
- Order book imbalance detection
- Large bet detection (whale watching)
- Time-to-resolution effects (prices change as resolution approaches)
- Cross-market arbitrage (BTC influences ETH prices)
```

#### 2. **Sentiment Analysis Integration**
```python
# Incorporate external signals

DATA SOURCES:
- Twitter sentiment for crypto mentions
- Reddit r/cryptocurrency discussion volume
- Google Trends for search interest
- News sentiment from crypto news APIs
- On-chain metrics (whale movements, exchange flows)
```

#### 3. **Multi-Strategy Portfolio**
```python
# Run multiple strategies simultaneously

STRATEGIES:
1. Trend-following (current approach)
2. Mean-reversion (bet against extremes)
3. Arbitrage-only (pure price difference exploitation)
4. Volatility-based (bet on high volatility periods)

# Allocate capital based on recent performance
```

#### 4. **Automated Parameter Optimization**
```python
# Let the bot tune itself

OPTIMIZE:
- profit_increase_pct (currently 10%)
- retrain_frequency (currently every 5 observations)
- timeframe weights (which timeframes are most predictive?)
- model hyperparameters (n_estimators, max_depth, etc.)

# Use Bayesian optimization or genetic algorithms
```

---

## 📋 Technical Requirements

### Python Dependencies

```bash
# Core libraries
pip install numpy pandas scikit-learn

# Blockchain interaction
pip install web3 eth-account

# Technical analysis
pip install ta-lib  # Requires C library installation

# Real-time data
pip install websockets requests

# Async operations
pip install asyncio aiohttp

# Database (optional)
pip install psycopg2-binary sqlalchemy

# Monitoring (optional)
pip install prometheus-client
```

### System Requirements

**Minimum:**
- CPU: 2 cores
- RAM: 4 GB
- Storage: 10 GB (for price history)
- Network: Stable internet with <100ms latency to exchanges

**Recommended:**
- CPU: 4+ cores (for parallel processing)
- RAM: 8 GB
- Storage: 50 GB SSD (fast I/O for tick data)
- Network: Low-latency connection (<50ms to Binance/Coinbase)

### External Services Needed

1. **Polygon RPC Node**
   - Public: `https://polygon-rpc.com` (free but rate-limited)
   - Private: Alchemy, Infura (paid but faster)

2. **Price Data Sources**
   - Binance WebSocket (free)
   - Coinbase WebSocket (free)
   - CoinGecko API (backup, free tier available)

3. **Polymarket Access**
   - Polymarket CLOB API (research needed)
   - Or Polymarket smart contract direct interaction

---

## 🎓 Learning Resources

### For Understanding Polymarket

1. **Official Documentation**
   - https://docs.polymarket.com
   - Smart contract addresses
   - API documentation

2. **Key Concepts**
   - Binary options vs traditional trading
   - AMM (Automated Market Maker) mechanics
   - CLOB (Central Limit Order Book) system
   - Chainlink oracle resolution process

### For Improving ML Models

1. **Time Series Prediction**
   - LSTM/GRU tutorials
   - Attention mechanisms for financial data
   - Online learning best practices

2. **Feature Engineering**
   - Technical indicators beyond SMA/RSI
   - Volume profile analysis
   - Order flow imbalance

3. **Risk Management**
   - Kelly Criterion calculator
   - Position sizing strategies
   - Drawdown management

---

## 🐛 Known Issues & Limitations

### Current Limitations

1. **Simulated Data**
   - Not using real exchange prices yet
   - Market resolution is random (not actual Polymarket)
   - No real transaction costs included

2. **Model Simplicity**
   - RF + GB may not capture complex time dependencies
   - No recurrent neural network (LSTM/GRU)
   - Feature engineering is basic

3. **No Backtesting**
   - Strategy not validated on historical data
   - Unknown real-world performance
   - Risk metrics not calculated

4. **Single Wallet**
   - No hot/cold wallet separation
   - Private key stored in code (security risk)
   - No multi-sig protection

### Edge Cases to Handle

```python
# 1. Network disconnection during bet placement
# Solution: Transaction confirmation tracking + retry logic

# 2. Insufficient USDT balance mid-round
# Solution: Pre-check balance before each round

# 3. Polymarket market doesn't resolve
# Solution: Timeout logic, manual intervention alerts

# 4. Price oracle failure (Chainlink down)
# Solution: Fallback to secondary oracle or skip round

# 5. Extreme volatility (flash crash)
# Solution: Volatility filters, max bet size limits

# 6. Model predicts 50.0% exactly
# Solution: Skip bet (no edge) or use tie-breaker logic
```

---

## 📊 Performance Metrics to Track

### Essential KPIs

```python
metrics = {
    # Profitability
    'total_pnl': 0.0,              # Total profit/loss in USDT
    'roi_percent': 0.0,            # Return on initial capital
    'win_rate': 0.0,               # Wins / Total trades
    
    # Risk metrics
    'max_drawdown': 0.0,           # Largest peak-to-trough loss
    'sharpe_ratio': 0.0,           # Risk-adjusted returns
    'win_streak_max': 0,           # Longest winning streak
    'loss_streak_max': 0,          # Longest losing streak
    
    # Per-coin performance
    'btc_win_rate': 0.0,
    'eth_win_rate': 0.0,
    'sol_win_rate': 0.0,
    
    # Model performance
    'prediction_accuracy': 0.0,    # % of correct predictions
    'avg_confidence': 0.0,         # Average prediction confidence
    'calibration_error': 0.0,      # How well probabilities match outcomes
    
    # Operational
    'trades_per_day': 0,
    'avg_trade_duration': 0,       # Should be 15 minutes
    'failed_transactions': 0,
    'api_errors': 0
}
```

### Logging & Reporting

```python
# Trade log format
{
    'timestamp': '2025-01-29T14:45:00Z',
    'round': 42,
    'coin': 'BTC',
    'start_price': 45123.45,
    'final_price': 45201.30,
    'predicted': 'UP',
    'actual': 'UP',
    'probability': 0.689,
    'bet_size': 10.65,
    'shares': 14.51,
    'share_price': 0.734,
    'pnl': 4.49,
    'cumulative_pnl': 87.21,
    'saved_profits': 91.70,
    'timeframe_features': {...},
    'model_version': 'v1.2.3'
}
```

---

## 🔐 Security Considerations

### Critical Security Issues

1. **Private Key Storage**
```python
# ❌ BAD: Hardcoded in script
PRIVATE_KEY = "0x1234..."

# ✅ GOOD: Environment variable
import os
PRIVATE_KEY = os.getenv('WALLET_PRIVATE_KEY')

# ✅ BETTER: Encrypted keystore
from eth_account import Account
account = Account.decrypt(keystore_json, password)
```

2. **API Key Protection**
```python
# Never commit to Git
# Use .env files (add to .gitignore)
# Rotate keys regularly
```

3. **Transaction Signing**
```python
# Always verify transaction details before signing
# Set gas limits (prevent infinite spending)
# Use nonce management (prevent replay attacks)
```

4. **Capital Limits**
```python
# Don't put entire bankroll in hot wallet
# Set maximum daily loss limits
# Implement circuit breakers
```

---

## 🧪 Testing Strategy

### Unit Tests Needed

```python
# test_multiTimeframeAnalyzer.py
def test_add_tick():
    analyzer = MultiTimeframeAnalyzer()
    analyzer.add_tick(timestamp=1000, price=45000)
    assert len(analyzer.timeframes['1s']['data']) == 1

def test_trend_calculation():
    # Add 100 ticks with uptrend
    # Verify trend_direction == 1 (UP)
    pass

# test_learningEngine.py
def test_observation_buffer():
    # Verify FIFO behavior (max 5000)
    pass

def test_model_update():
    # Add observations, verify model retrains
    pass

# test_moneyManagement.py
def test_profit_compounding():
    # Win streak should increase bet correctly
    pass

def test_loss_reset():
    # Any loss should reset to default
    pass
```

### Integration Tests

```python
# test_full_round.py
def test_complete_15min_cycle():
    # Simulate entire round
    # Verify all phases execute correctly
    pass

def test_parallel_coin_trading():
    # Verify BTC, ETH, SOL all process correctly
    pass

# test_websocket_resilience.py
def test_reconnection_on_disconnect():
    # Simulate network drop
    # Verify reconnection logic
    pass
```

### Backtesting

```python
# backtest.py
def run_backtest(start_date, end_date):
    # Load historical tick data
    # Simulate exact 15-min cycles
    # Calculate all fees and slippage
    # Generate performance report
    
    return {
        'total_trades': 1000,
        'win_rate': 0.58,
        'total_pnl': 234.56,
        'max_drawdown': -45.23,
        'sharpe_ratio': 1.45
    }
```

---

## 📝 Code Organization

### Recommended Project Structure

```
polymarket-bot/
│
├── src/
│   ├── core/
│   │   ├── wallet.py              # WalletManager
│   │   ├── polymarket.py          # PolymarketMechanics
│   │   └── monitoring.py          # RealTimeMonitor
│   │
│   ├── ml/
│   │   ├── features.py            # Feature extraction
│   │   ├── models.py              # ML models
│   │   └── learning.py            # ContinuousLearningEngine
│   │
│   ├── analysis/
│   │   ├── timeframes.py          # MultiTimeframeAnalyzer
│   │   └── arbitrage.py           # PriceArbitrageDetector
│   │
│   ├── trading/
│   │   ├── strategy.py            # Trading logic
│   │   └── risk.py                # Risk management
│   │
│   └── bot.py                     # Main bot class
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── backtest/
│
├── data/
│   ├── historical/                # Price history
│   └── models/                    # Saved ML models
│
├── config/
│   ├── config.yaml                # Bot configuration
│   └── secrets.env                # API keys (not in Git!)
│
├── logs/
│   └── trades/                    # Trade history
│
├── scripts/
│   ├── download_data.py           # Fetch historical data
│   ├── train_model.py             # Pre-train models
│   └── analyze_performance.py     # Generate reports
│
├── requirements.txt
├── .gitignore
├── .env.example
├── README.md
└── docker-compose.yml
```

---

## 🎯 Success Criteria

### Minimum Viable Performance

To consider the bot "production-ready":

```python
minimum_targets = {
    'win_rate': 0.55,              # >55% (better than random)
    'sharpe_ratio': 1.0,           # >1.0 (decent risk-adjusted returns)
    'max_drawdown': -0.20,         # <20% of capital
    'avg_daily_return': 0.02,      # >2% per day
    'uptime': 0.99,                # >99% (minimal downtime)
}
```

### Red Flags to Watch

```python
stop_trading_if = {
    'consecutive_losses': 5,        # 5 losses in a row → pause
    'daily_loss': -0.10,           # -10% in one day → pause
    'model_accuracy': 0.45,        # <45% accuracy → retrain
    'api_error_rate': 0.05,        # >5% errors → fix infrastructure
}
```

---

## 🔄 Operational Workflow

### Daily Routine

```bash
# Morning (before markets open)
1. Check system health
2. Review overnight trades
3. Verify wallet balance
4. Check for any alerts

# During trading hours
1. Monitor live performance dashboard
2. Watch for anomalies (unusual losses)
3. Check model performance metrics
4. Verify transactions confirming properly

# Evening (after markets close)
1. Generate daily report
2. Backup trade logs
3. Review model updates
4. Plan any parameter adjustments
```

### Weekly Maintenance

```bash
1. Backtest latest strategy on past week's data
2. Compare actual vs expected performance
3. Retrain models with full week's data
4. Optimize parameters if needed
5. Update documentation with lessons learned
```

### Monthly Review

```bash
1. Calculate monthly ROI
2. Compare vs benchmarks (BTC buy-and-hold)
3. Analyze per-coin performance
4. Adjust coin allocations if needed
5. Archive old logs
6. Security audit (rotate keys if needed)
```

---

## 📞 Support & Troubleshooting

### Common Issues

**Issue 1: Bot stops placing bets**
```
Symptoms: Monitoring works, but no bets placed
Possible causes:
  - Insufficient USDT balance
  - Wallet connection lost
  - Polymarket API down
  
Debug:
  1. Check wallet.get_usdt_balance()
  2. Verify wallet.address is correct
  3. Test manual transaction
```

**Issue 2: Model accuracy drops suddenly**
```
Symptoms: Win rate falls below 45%
Possible causes:
  - Market regime change (volatility spike)
  - Overfitting to recent data
  - Feature distribution shift
  
Solutions:
  1. Retrain with more historical data
  2. Increase observation buffer size
  3. Add volatility filters
```

**Issue 3: Trades not resolving**
```
Symptoms: Bet placed but no outcome after 15 minutes
Possible causes:
  - Polymarket oracle delayed
  - Wrong market ID
  - Transaction reverted
  
Debug:
  1. Check transaction hash on Polygonscan
  2. Verify market resolution timestamp
  3. Contact Polymarket support
```

---

## 🚦 Getting Started Checklist

### Phase 1: Setup (Day 1)
- [ ] Install all Python dependencies
- [ ] Set up Polygon wallet with test USDT
- [ ] Configure environment variables
- [ ] Run bot in simulation mode
- [ ] Verify logging works

### Phase 2: Integration (Days 2-3)
- [ ] Connect Binance WebSocket
- [ ] Test real price feeds
- [ ] Implement Polymarket API (research required)
- [ ] Test small real transactions on testnet
- [ ] Verify money management logic

### Phase 3: Validation (Days 4-7)
- [ ] Backtest on 1 month of data
- [ ] Paper trade for 1 week
- [ ] Compare paper vs backtest results
- [ ] Fix any discovered issues
- [ ] Write unit tests for critical functions

### Phase 4: Live Trading (Day 8+)
- [ ] Start with minimum bet size ($1)
- [ ] Monitor continuously for first 24 hours
- [ ] Gradually increase bet size if successful
- [ ] Set up automated alerts
- [ ] Document all issues and resolutions

---

## 📚 Key Takeaways for Claude Code

### Core Philosophy
1. **Last-second betting beats early betting** - 898 seconds of learning makes huge difference
2. **Continuous learning beats batch learning** - Update models immediately, don't wait
3. **Protect profits first** - Lock winnings away, never risk saved money
4. **Multi-timeframe context matters** - Don't just look at 15-min candles

### Critical Implementation Details
1. **Bet timing**: Must bet at 14:59, not 0:00
2. **Learning frequency**: Update model every 5 observations, not every 20 trades
3. **Money reset**: ANY loss resets to default, not 2 consecutive losses
4. **Profit locking**: 100% of profit saved, only 10% increase goes to betting

### What Makes This Bot Different
- Most bots: Predict → Bet → Wait → Learn from outcome
- This bot: Monitor → Learn continuously → Predict at last second → Bet

### Questions to Research Further
1. How exactly does Polymarket's CLOB work? (order book vs AMM)
2. What are typical spreads for 15-min markets?
3. Can bets be canceled/modified after placement?
4. What's the maximum bet size before slippage becomes significant?
5. Are there API rate limits to watch for?

---

## 🎓 Final Notes

This bot represents a sophisticated approach to algorithmic trading on prediction markets. The key innovations are:

1. **Temporal advantage**: Using the full 15 minutes of data before betting
2. **Continuous adaptation**: Learning from every price tick, not just outcomes
3. **Capital preservation**: Aggressive profit-taking with conservative loss management
4. **Multi-timeframe synthesis**: Understanding context from 1-second to 1-week scales

The next developer working on this (whether human or Claude Code) should focus on:
- Real exchange integration (replace simulations)
- Proper backtesting framework
- Production infrastructure (Docker, monitoring, alerts)
- Security hardening (key management, transaction validation)

Good luck, and may your win rate be ever in your favor! 🚀📈

---

**Document Version**: 1.0
**Last Updated**: January 29, 2025
**Author**: Created collaboratively by Claude (Anthropic) and User
**Purpose**: Complete technical handoff to Claude Code CLI for continued development