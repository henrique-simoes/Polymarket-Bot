# Time-Decay Learning Mode - Complete Flow Simulation

## Simulation Setup

**Simulated Market Data:**
- BTC Strike: $71,368.76 (OFFCL)
- BTC Spot: $71,363.48 (below strike)
- YES price: $0.28 (28¢)
- NO price: $0.71 (71¢)
- Time remaining: 446s

**Bot Configuration:**
- Mode: Time-Decay Learning (Mode E)
- Virtual Balance: $10.00
- Risk Profile: time_decay
- Learning Mode: True

---

## PHASE 1: INIT State (Round Start)

### Step 1.1: Market Discovery
```
Code: src/bot.py:2498-2515
```

**Simulated Flow:**
```python
# Bot fetches active 15-minute markets
markets = market_15m.find_active_15m_markets()
# Returns: {'BTC': {...}, 'ETH': {...}, 'SOL': {...}}

active_coins = ['BTC', 'ETH', 'SOL']

# Fetch official strike prices
for c in active_coins:
    official_strike = market_15m.get_official_strike_price(c)
    # BTC: $71,368.76
    start_prices['BTC'] = 71368.76
    strike_types['BTC'] = "OFFCL"
```

**Log Output:**
```
[INFO] BTC: Official strike $71,368.76
[INFO] ETH: Official strike $2,108.66
[INFO] SOL: Official strike $90.80
[INFO] New round started - Budget: $10.00
```

### Step 1.2: Regime Detection
```
Code: src/bot.py:2528-2533
```

**Simulated Flow:**
```python
regime_detector.update_all_regimes(['BTC', 'ETH', 'SOL'])
# Returns regimes based on historical data analysis
# BTC: BULL (85% confidence) → risk_multiplier = 1.0
```

---

## PHASE 2: MONITOR State (Data Collection)

### Step 2.1: Continuous Data Collection
```
Code: src/bot.py:2564-2570
```

**Simulated Flow (every tick):**
```python
for coin in active_coins:
    process_coin_sniping(coin, remaining)  # 446s remaining

# Inside process_coin_sniping():
_collect_data(coin, start_prices[coin], remaining)

# Inside _collect_data():
price = fetch_current_price(coin)  # $71,363.48
mtf_analyzer[coin].add_tick(time.time(), price)
features = extract_features(coin, start_price, {}, time_remaining)
learning_engine.add_observation(coin, features, time.time())
```

**Log Output:**
```
[COLLECT] BTC: Added observation (features: 56 dimensions)
```

### Step 2.2: Episode Buffer Growing
```
Code: src/ml/learning.py:62-91
```

**Simulated State:**
```python
learning_engine.episode_buffer = {
    'BTC': [
        {'features': [0.52, -0.01, 0.85, ...], 'timestamp': 1738712400.0},
        {'features': [0.51, -0.02, 0.84, ...], 'timestamp': 1738712401.0},
        # ... more observations
    ],
    'ETH': [...],
    'SOL': [...]
}
```

---

## PHASE 3: SNIPE State (Order Evaluation)

**Trigger:** `remaining <= 500` → State changes to SNIPE

### Step 3.1: Smart Coin Selection Entry
```
Code: src/bot.py:1888-1904
```

**Simulated Flow:**
```python
smart_coin_selection(remaining=446)

remaining_budget = 10.00 - 0.00  # $10.00 available
effective_budgets = _get_effective_budgets(10.00)
# BTC: {'amount': 10.00, 'multiplier': 1.0, 'regime': 'BULL'}

opportunities = []
```

### Step 3.2: Arbitrage Check (for each coin)
```
Code: src/bot.py:1930-1944
```

**Simulated Flow for BTC:**
```python
cp = fetch_current_price('BTC')  # $71,363.48
pp = market_15m.get_current_price('BTC')  # 0.28 (YES price)

arb = arbitrage_detector.check_arbitrage(
    coin='BTC',
    polymarket_price=0.28,  # YES price
    strike_price=71368.76,
    time_remaining=446
)
```

**Inside check_arbitrage:**
```python
fair_prob = calculate_fair_value('BTC', 71368.76, 446)
# fair_prob = P(spot > strike) ≈ 0.483 (48.3%)

diff = 0.483 - 0.28  # = +0.203 (+20.3%)

# Check if in window (446 > 300 = snipe_window)
in_window = (446 <= 300)  # FALSE!

# Since outside window, direction stays None
direction = None  # ❌ PROBLEM (but we fixed it!)
```

**Return value:**
```python
arb = {
    'opportunity': False,  # Outside window
    'direction': None,     # Not set
    'fair_value': 0.483,
    'poly_price': 0.28,
    'diff': 20.3,          # Edge % still calculated
    'time_left': 446
}
```

### Step 3.3: Direction Override (Time-Decay Fix)
```
Code: src/bot.py:1949-1964
```

**Simulated Flow (WITH FIX):**
```python
# arb['direction'] is None
if not arb or arb.get('direction') is None:
    if self.time_decay_sniper_mode:  # TRUE
        strike = start_prices.get('BTC', cp)  # 71368.76
        if cp > strike:  # 71363.48 > 71368.76? NO
            arb['direction'] = 'UP'
        else:
            arb['direction'] = 'DOWN'  # ✅ Set to DOWN
            logger.info("BTC: [TD] Direction=DOWN (spot $71,363.48 < strike $71,368.76)")
```

**Log Output:**
```
[INFO] BTC: [TD] Direction=DOWN (spot $71,363.48 < strike $71,368.76)
```

### Step 3.4: Token Selection
```
Code: src/bot.py:1968-1981
```

**Simulated Flow:**
```python
both_prices = market_15m.get_both_prices('BTC')
# {'yes': 0.28, 'no': 0.71}

tokens = market_15m.get_token_ids_for_coin('BTC')
# {'yes': '0x123...', 'no': '0x456...'}

# Direction is DOWN, so select NO token
tid = tokens['no']      # '0x456...'
t_price = both_prices['no']  # 0.71 (71¢)
```

### Step 3.5: Time-Decay Opportunity Check
```
Code: src/bot.py:2008-2037
```

**Simulated Flow:**
```python
td_check = is_time_decay_opportunity(
    coin='BTC',
    polymarket_price=0.71,     # NO token price
    strike_price=71368.76,
    time_remaining=446,
    current_spot=71363.48,
    direction='DOWN'           # ✅ NEW: Direction passed
)
```

**Inside is_time_decay_opportunity:**
```python
# Step 1: Check optimal window
optimal_window = get_dynamic_entry_window()  # 300s default
if time_remaining > optimal_window:  # 446 > 300
    reasons.append("Outside optimal window (need ≤300s, have 446s)")
    return {'opportunity': False, 'edge': 0.0, 'reasoning': ...}
    # ❌ REJECTED - Outside window
```

**ISSUE FOUND:** The dynamic entry window (300s) is smaller than the SNIPE state trigger (500s), causing all opportunities to be rejected until time drops below 300s.

### Step 3.5b: If Window Check Passed (simulating with 250s remaining)

Let's simulate with `time_remaining = 250s`:

```python
# Step 1: Window check - PASS
optimal_window = 300
if time_remaining > optimal_window:  # 250 > 300? NO
    pass  # Continue

# Step 2: Price range check
if polymarket_price < 0.40:  # 0.71 < 0.40? NO
    pass  # Continue

if polymarket_price > 0.90:  # 0.71 > 0.90? NO
    pass  # Continue

# 71¢ is within 40-90¢ range ✅

# Step 3: Calculate Black-Scholes edge
fair_prob_yes = arbitrage_detector.calculate_fair_value('BTC', 71368.76, 250)
# With spot slightly below strike and 250s left, fair_prob_yes ≈ 0.48

# Step 4: Calculate edge for NO token (direction='DOWN')
if direction == 'UP':
    fair_prob = fair_prob_yes  # 0.48
else:
    fair_prob = 1.0 - fair_prob_yes  # 0.52 (52%)

edge = fair_prob - polymarket_price  # 0.52 - 0.71 = -0.19 (-19%)

# Step 5: Edge check
if edge < 0.15:  # -0.19 < 0.15? YES
    reasons.append("Edge too small (need ≥15%, have -19.0%) [NO token]")
    return {'opportunity': False, 'edge': -0.19, 'reasoning': ...}
    # ❌ REJECTED - Negative edge!
```

**CRITICAL FINDING:** The NO token at 71¢ has NEGATIVE edge (-19%). This is correct behavior - the market is overpricing NO.

### Step 3.5c: Simulating a VALID Opportunity

Let's simulate a scenario where there IS a valid opportunity:

**Scenario:** BTC spot moved significantly above strike
- Strike: $71,368.76
- Spot: $71,700.00 (+0.46% above strike)
- YES price: $0.75 (market slow to update)
- Time remaining: 200s

```python
# Direction = UP (spot > strike)
t_price = 0.75  # YES token

# Inside is_time_decay_opportunity:
fair_prob_yes = calculate_fair_value('BTC', 71368.76, 200)
# With spot 0.46% above strike and 200s left, fair_prob_yes ≈ 0.92 (92%)

# Edge calculation (direction='UP')
fair_prob = fair_prob_yes  # 0.92
edge = 0.92 - 0.75  # = 0.17 (+17%)

# Edge check
if edge < 0.15:  # 0.17 < 0.15? NO
    pass  # Continue

# Price move check
price_move_pct = abs(71700 - 71368.76) / 71368.76  # 0.46%
if price_move_pct < 0.005:  # 0.46% < 0.5%? YES
    reasons.append("Price too close to strike (need >0.5%, have 0.46%)")
    return {'opportunity': False, ...}
    # ❌ REJECTED - Price hasn't moved enough
```

**Scenario with all criteria met:**
- Spot: $71,800.00 (+0.60% above strike)
- YES price: $0.72
- Time remaining: 200s

```python
fair_prob_yes ≈ 0.95 (95%)
edge = 0.95 - 0.72 = 0.23 (+23%)  # ✅ > 15%
price_move_pct = 0.60%  # ✅ > 0.5%
price = 0.72  # ✅ Within 40-90¢

return {'opportunity': True, 'edge': 0.23, 'reasoning': "✓ Time: 200s | Price: 72¢ | Edge: 23.0% | Move: 0.60% from strike"}
```

---

## PHASE 4: Order Placement (Learning Mode)

### Step 4.1: Opportunity Added to List
```
Code: src/bot.py:2195-2230
```

**Simulated Flow:**
```python
opp_dict = {
    'coin': 'BTC',
    'direction': 'UP',
    'price': 0.72,
    'min_shares': 5.0,
    'min_cost': 3.60,  # 5 shares × $0.72
    'arb_edge': 0.23,
    'ml_confidence': 0.5,  # Default neutral
    'combined_score': 0.23 * 0.8 + 0.5 * 0.2,  # = 0.284
    'token_id': '0x123...',
    'td_metadata': {...}
}
opportunities.append(opp_dict)
```

### Step 4.2: Opportunity Sorting
```
Code: src/bot.py:2245-2257
```

```python
# Sort by combined_score descending
opportunities.sort(key=lambda x: x['combined_score'], reverse=True)
# BTC with score 0.284 is selected
```

### Step 4.3: Order Placement (Learning Mode)
```
Code: src/bot.py:2311-2328
```

**Simulated Flow:**
```python
if self.learning_mode and self.learning_simulator:
    cp = fetch_current_price('BTC')  # $71,800.00
    market = market_15m.market_cache.get('BTC', {})
    condition_id = market.get('conditionId')  # '0xabc...'

    order = learning_simulator.simulate_order(
        coin='BTC',
        direction='UP',
        amount=3.60,
        token_id='0x123...',
        start_price=71368.76,
        current_price=71800.00,
        confidence=0.284,
        condition_id='0xabc...'
    )
```

### Step 4.4: Inside Learning Simulator
```
Code: src/core/learning_simulator.py:47-100
```

**Simulated Flow:**
```python
# Check balance
if not can_afford(3.60):  # 10.00 >= 3.60? YES
    return None

# Deduct from virtual balance
virtual_balance = 10.00 - 3.60  # = $6.40

# Create simulated order
position_counter = 1
order_id = "LEARNING_1_20260205120000"

estimated_price = random.uniform(0.45, 0.55)  # e.g., 0.50
estimated_shares = 3.60 / 0.50  # = 7.2 shares

position = {
    'order_id': 'LEARNING_1_20260205120000',
    'coin': 'BTC',
    'prediction': 'UP',
    'amount': 3.60,
    'cost': 3.60,
    'token_id': '0x123...',
    'condition_id': '0xabc...',
    'start_price': 71368.76,
    'current_price': 71800.00,
    'confidence': 0.284,
    'price': 0.50,
    'shares': 7.2,
    'timestamp': '2026-02-05T12:00:00',
    'status': 'simulated_open'
}

virtual_positions['LEARNING_1_20260205120000'] = position
return position
```

**Log Output:**
```
[INFO] [LEARNING] SIMULATING order: BTC UP $3.60
[INFO]   Confidence: Arb=23.0% ML=50.0% Combined=0.284
[INFO] ✓ Order placed! Spent: $3.60/$10.00
```

### Step 4.5: Order Tracking
```
Code: src/bot.py:2381-2385
```

```python
# Order added to round tracking
current_round_bets.append(order)
balance -= 3.60  # Virtual deduction already done

round_budget_spent = 3.60
round_coins_bet.add('BTC')
```

---

## PHASE 5: Dashboard Display

### Step 5.1: Active Orders Panel
```
Code: src/bot.py:539-574
```

**Simulated Display:**
```python
# Learning mode: Show virtual positions
active_orders = list(learning_simulator.virtual_positions.values())
# [{'coin': 'BTC', 'prediction': 'UP', 'amount': 3.60, ...}]

# Format display
# "BTC UP $3.60 (5s ago) [VIRTUAL]"
```

**Dashboard Output:**
```
┌─ Active Orders ──────────────────────────┐
│ BTC UP $3.60 (5s ago) [VIRTUAL]          │
└──────────────────────────────────────────┘
```

### Step 5.2: Learning Mode Stats Panel
```
Code: src/bot.py:580-618
```

**Simulated Display:**
```
┌─ Learning Mode Stats ────────────────────┐
│ VIRTUAL:   $6.40                         │
│ P&L:       $0.00 (+0.0%)                 │
│ Trades:    0 (0W/0L)                     │
│ Win Rate:  0.0%                          │
│ Progress:  [░░░░░░░░░░] 0% | 0/200       │
│                                          │
│ Real Bal:  $10.50 (untouched)           │
└──────────────────────────────────────────┘
```

---

## PHASE 6: SETTLE State (Settlement)

**Trigger:** `remaining < 10` → State changes to SETTLE

### Step 6.1: Settlement Thread Started
```
Code: src/bot.py:2584-2593
```

**Simulated Flow:**
```python
# Always start settlement thread (even with 0 bets - our fix!)
Thread(target=background_settlement, args=(
    current_round_bets,  # [order]
    start_prices,        # {'BTC': 71368.76, ...}
    seconds_remaining    # ~5s
)).start()
```

### Step 6.2: Wait for Market Resolution
```
Code: src/bot.py:1186-1202
```

**Simulated Flow:**
```python
# Wait for market close + resolution delay
time_until_close = 5  # seconds
resolution_delay = 90
total_wait = 5 + 90  # = 95 seconds

time.sleep(95)  # Wait for Chainlink oracle
```

### Step 6.3: Determine Outcome
```
Code: src/bot.py:1204-1226
```

**Simulated Flow (BTC bet):**
```python
for bet in placed_bets:
    coin = bet['coin']  # 'BTC'
    final_p = fetch_current_price('BTC')  # $71,750.00 (final)

    # Get official resolution
    condition_id = bet.get('condition_id')  # '0xabc...'
    actual = wait_for_market_resolution(condition_id, 'BTC', max_wait=120)
    # Returns: 'UP' (price finished above strike)
```

### Step 6.4: Learning Mode Settlement
```
Code: src/bot.py:1227-1340
```

**Simulated Flow:**
```python
if self.learning_mode and self.learning_simulator:
    order_id = bet.get('order_id')  # 'LEARNING_1_20260205120000'

    trade_record = learning_simulator.settle_position(
        order_id=order_id,
        final_price=71750.00,
        start_price=71368.76
    )
```

### Step 6.5: Inside settle_position
```
Code: src/core/learning_simulator.py:102-160
```

**Simulated Flow:**
```python
position = virtual_positions.get('LEARNING_1_20260205120000')
# {'coin': 'BTC', 'prediction': 'UP', 'shares': 7.2, ...}

# Determine outcome
# Final price $71,750 > Strike $71,368 → Market resolved UP
actual_outcome = 'UP'  # from oracle

# Check if prediction was correct
won = (position['prediction'] == actual_outcome)  # 'UP' == 'UP' → True

# Calculate P&L
if won:
    # Shares are worth $1 each
    payout = position['shares'] * 1.0  # 7.2 × $1 = $7.20
    profit = payout - position['cost']  # $7.20 - $3.60 = $3.60
else:
    profit = -position['cost']  # -$3.60

# Update virtual balance
virtual_balance += payout  # $6.40 + $7.20 = $13.60

# Update stats
total_trades += 1  # = 1
wins += 1  # = 1

# Create trade record
trade_record = {
    'order_id': 'LEARNING_1_20260205120000',
    'coin': 'BTC',
    'direction': 'UP',
    'amount': 3.60,
    'price': 0.50,
    'shares': 7.2,
    'won': True,
    'profit': 3.60,
    'actual_outcome': 'UP',
    'pnl': 3.60,
    'timestamp': '2026-02-05T12:00:00',
    'settled_at': '2026-02-05T12:15:00'
}

# Remove from active positions
del virtual_positions['LEARNING_1_20260205120000']

return trade_record
```

### Step 6.6: Save Trade to Persistence
```
Code: src/bot.py:1240-1280
```

**Simulated Flow:**
```python
# Save to learning trades file
learning_persistence.save_trade(trade_record)
# Appends to data/learning_trades.json
```

**File: data/learning_trades.json:**
```json
[
  {
    "order_id": "LEARNING_1_20260205120000",
    "coin": "BTC",
    "direction": "UP",
    "amount": 3.60,
    "price": 0.50,
    "shares": 7.2,
    "won": true,
    "profit": 3.60,
    "actual_outcome": "UP",
    "pnl": 3.60,
    "timestamp": "2026-02-05T12:00:00",
    "settled_at": "2026-02-05T12:15:00"
  }
]
```

### Step 6.7: ML Training (finalize_round)
```
Code: src/bot.py:1320-1330
```

**Simulated Flow:**
```python
if actual:
    learning_engine.finalize_round(coin, actual)
    # actual = 'UP'
```

### Step 6.8: Inside finalize_round
```
Code: src/ml/learning.py:93-119
```

**Simulated Flow:**
```python
# Label all observations from this round
label = 1 if won_outcome == "UP" else 0  # 1

new_samples = 0
for obs in episode_buffer['BTC']:
    replay_buffer.append((obs['features'], label))
    new_samples += 1

# e.g., 450 observations × 1 label = 450 new samples

# Clear episode buffer for BTC
episode_buffer['BTC'] = []

# Save labeled data
save_episode_buffers()
save_replay_buffer()

# Train model
train_model('BTC')
```

**Log Output:**
```
[FINALIZE] finalize_round() called for BTC, outcome: UP
[FINALIZE] Labeled 450 observations for BTC (outcome: UP)
[FINALIZE] Saved 450 samples to replay buffer
[TRAINING] Training model for BTC with 450 samples...
```

---

## PHASE 7: Passive Learning (No Bets Coins)

### Step 7.1: Identify Passive Coins
```
Code: src/bot.py:1511-1550
```

**Simulated Flow:**
```python
coins_with_bets = {'BTC'}  # Only BTC had a bet
passive_learning_coins = ['ETH', 'SOL']  # These had no bets

for coin in passive_learning_coins:
    final_price = fetch_current_price(coin)
    start_price = start_prices.get(coin)

    actual = market_15m.check_resolution(coin, start_price, final_price)
    # ETH: start=$2,108.66, final=$2,115.00 → 'UP'
    # SOL: start=$90.80, final=$90.50 → 'DOWN'

    # Label ML observations even without bet
    learning_engine.finalize_round(coin, actual)
```

**Log Output:**
```
[PASSIVE] ✓ ML trained on ETH outcome: UP (no bet placed)
[PASSIVE] ✓ ML trained on SOL outcome: DOWN (no bet placed)
```

### Step 7.2: Phantom Tracking Finalization
```
Code: src/bot.py:1552-1565
```

**Simulated Flow:**
```python
all_outcomes = {
    'BTC': 'UP',
    'ETH': 'UP',
    'SOL': 'DOWN'
}

phantom_tracker.finalize_round(all_outcomes)
```

**Inside phantom_tracker.finalize_round:**
```python
# For each rejection recorded during SNIPE phase
for coin, rejection_data in current_round_rejections.items():
    actual_outcome = all_outcomes.get(coin)

    would_have_won = (rejection_data['direction'] == actual_outcome)

    phantom_trade = {
        **rejection_data,
        'actual_outcome': actual_outcome,
        'would_have_won': would_have_won
    }
    phantom_trades.append(phantom_trade)

# Save to disk
save_data()
```

**File: data/phantom_trades.json:**
```json
[
  {
    "coin": "BTC",
    "price": 0.71,
    "direction": "DOWN",
    "edge": -0.19,
    "rejection_reason": "Edge too small (need ≥15%, have -19.0%) [NO token]",
    "actual_outcome": "UP",
    "would_have_won": false
  }
]
```

---

## ISSUES FOUND IN SIMULATION

### Issue 1: Window Mismatch (CRITICAL)
**Location:** `is_time_decay_opportunity()` line 1690

**Problem:** SNIPE state starts at 500s, but `optimal_window` defaults to 300s
- Bot enters SNIPE at 500s
- `is_time_decay_opportunity` rejects because 500s > 300s
- No opportunities evaluated until time drops below 300s

**Fix Needed:** Either:
1. Increase `get_dynamic_entry_window()` default to 500s
2. Or sync SNIPE trigger with optimal_window

### Issue 2: Edge Display Confusion (UI)
**Location:** Dashboard edge display

**Problem:** Dashboard shows edge for YES token, but time-decay may select NO token
- User sees "+20.6% edge" for BTC
- This is edge for YES at 28¢
- But time-decay selects NO at 71¢ which has -19% edge

**Fix Needed:** Display edge for the TOKEN being evaluated, not always YES

### Issue 3: All Fixed Issues Working
- ✅ Direction determined from spot vs strike when arb window exceeded
- ✅ Edge calculated correctly for NO tokens (1 - fair_prob_YES)
- ✅ Direction passed to `is_time_decay_opportunity()`
- ✅ Phantom tracking records rejections
- ✅ Passive learning runs even with 0 bets
- ✅ Settlement thread always runs

---

## RECOMMENDED FIXES

### Fix Window Mismatch
```python
# In get_dynamic_entry_window(), change default:
def get_dynamic_entry_window(self):
    # ... existing ML logic ...
    # Default should match SNIPE trigger (500s) not 300s
    return self.config.get('time_decay', {}).get('default_window', 500)
```

### Fix Edge Display
```python
# In update_dashboard(), calculate edge for correct token:
if self.time_decay_sniper_mode:
    # Show edge for token we'd actually buy (based on direction)
    strike = self.start_prices.get(coin, 0)
    spot = self.fetch_current_price(coin)
    if spot > strike:
        edge = arb.get('diff', 0)  # YES edge
    else:
        edge = -arb.get('diff', 0)  # Invert for NO edge
```
