  Mode D: Every Qualification Step (in order)
                                                                                                                                                                                                          
  Phase 1: State Machine — Getting to SNIPE                 

  Step 1 — INIT (first 60s of each 15-min window)
  - Fetches active 15-min markets for BTC, ETH, SOL
  - Scrapes official strike prices from Polymarket webpage
  - Resets round_budget_spent = 0, round_coins_bet = set(), current_round_bets = []
  - Updates cross-market correlations and historical DB
  - Runs process_coin_sniping() once per coin for initial dashboard data

  Step 2 — MONITOR (60s to 480s elapsed, i.e. remaining > 420s)
  - Calls process_coin_sniping() each tick — updates dashboard prices/edges
  - Collects ML observations via _collect_data() (feeds VWAP calculator too)
  - No trades placed — just watching

  Step 3 — SNIPE trigger (bot.py:2811)
  - When remaining <= 420 (7 minutes left), transitions to SNIPE state
  - Now smart_coin_selection(remaining) is called every tick

  ---
  Phase 2: smart_coin_selection() — The Gauntlet

  Every tick during SNIPE, each coin must pass these checks in order:

  Step 4 — Budget check (bot.py:1937-1941)
  remaining_budget = user_max_bet - round_budget_spent
  if remaining_budget < $0.10 → SKIP entire round

  Step 5 — Already bet check (bot.py:1951-1952)
  if coin in round_coins_bet → SKIP this coin

  Step 6 — Data collection (bot.py:1958)
  - Calls _collect_data() — fetches Binance spot price, updates multi-timeframe analyzer, extracts ML features, adds observation to episode buffer, feeds VWAP calculator

  Step 7 — Strike price sync (bot.py:1963-1966)
  - Re-fetches official strike from webpage (continuous sync)

  Step 8 — Arbitrage detector (bot.py:1972)
  - Calls check_arbitrage(coin, polymarket_price, strike, remaining)
  - Inside check_arbitrage() (arbitrage.py:170-245):
    - Gets current Binance spot price
    - Calculates BS fair value: d2 = (ln(S/K) - 0.5σ²t) / (σ√t) → fair_prob = N(d2)
    - Computes diff = fair_prob - polymarket_price
    - Checks dynamic entry window (edge-based timing from config tiers)
    - Sets direction = UP if diff > 5%, DOWN if diff < -5%, None otherwise
    - Returns dict with opportunity, direction, fair_value, diff

  Step 9 — Direction determination (bot.py:1990-2002)
  - If arbitrage detector returned direction = None (outside its window or edge < 5%):
    - Mode D override: Derives direction from spot vs strike
    - spot > strike → direction = UP
    - spot <= strike → direction = DOWN
  - This is critical — Mode D doesn't need the arb detector to have a signal

  Step 10 — Fetch token prices (bot.py:2009-2031)
  - Calls get_both_prices(coin) for YES and NO Polymarket prices
  - Selects the correct token based on direction:
    - UP → YES token price and token_id
    - DOWN → NO token price and token_id

  Step 11 — Minimum order check (bot.py:2033-2039)
  min_cost = $1.00 (Polymarket floor)
  if $1.00 > effective_budget → SKIP this coin

  ---
  Phase 3: Time-Decay Scoring (the core logic)

  Step 12 — is_time_decay_opportunity() (bot.py:1731-1807)

  Four sub-checks in order:

  12a — Time window (bot.py:1752-1757)
  optimal_window = get_dynamic_entry_window()  → 420s default, or ML-learned after 20+ trades
  if time_remaining > optimal_window → REJECT ("Outside optimal window")

  12b — Price range (bot.py:1761-1767)
  if token_price < 0.75 → REJECT ("Price too low, need ≥75¢")
  if token_price > 0.85 → REJECT ("Price too high, need ≤85¢")

  12c — Black-Scholes edge ≥ 15% (bot.py:1771-1792)
  - Calls calculate_fair_value(coin, strike, time_remaining) → gets fair_prob_yes
  - If direction UP: edge = fair_prob_yes - polymarket_price
  - If direction DOWN: edge = (1 - fair_prob_yes) - polymarket_price
  if edge < 0.15 → REJECT ("Edge too small, need ≥15%")

  12d — Price movement from strike (bot.py:1794-1798)
  price_move_pct = |spot - strike| / strike
  if price_move_pct < 0.005 → REJECT ("Price too close to strike, need >0.5%")

  If ANY sub-check fails → records rejection to PhantomTracker for ML learning, skips to next coin.

  Step 13 — Feature extraction for calibration (bot.py:2090-2130)
  - Calculates price_distance_pct (spot vs strike)
  - Fetches orderbook → computes orderbook_imbalance (top 5 bid vol vs ask vol)
  - Calculates vol_realized from recent 1-minute close prices (annualized log returns)
  - Gets VWAP features: vwap_deviation_pct, price_above_vwap, vwap_trend

  Step 14 — ML Calibration (optional) (bot.py:2132-2159)
  - Only if TimeDecayCalibrator is trained (has enough historical data)
  - Adjusts raw BS edge using learned patterns:
  calibrated_edge = calibrator.calibrate_edge(bs_prob, market_price, time_remaining,
                                               price_distance, vol_realized, vol_assumed,
                                               ob_imbalance, vwap_deviation, vwap_trend)
  - If calibrated edge > 0, replaces td_edge with calibrated value

  Step 15 — ML confidence (bot.py:2161-2177)
  - Extracts full 86-feature vector
  - Calls learning_engine.predict(coin, features) → returns prob_up (float)
  - ml_confidence = prob_up if UP, 1.0 - prob_up if DOWN
  - Defaults to 0.5 if model not yet trained

  Step 16 — Combined score (bot.py:2178-2179)
  combined_score = 0.8 × td_edge + 0.2 × ml_confidence

  ---
  Phase 4: Risk Validation

  Step 17 — validate_trade() (bot.py:1809-1840)

  Three sub-checks:

  17a — Price range (again)
  if price < 0.75 → REJECT
  if price > 0.85 → REJECT
  (Redundant with Step 12b but acts as a safety net)

  17b — Budget check
  if $1.00 > user_max_bet → REJECT
  if $1.00 > balance → REJECT

  ---
  Phase 5: Selection & Execution

  Step 18 — Late-game fallback (bot.py:2291-2451)
  - Only checked if zero opportunities passed all steps above
  - Requires: remaining <= 200s AND time_decay_sniper_mode = True
  - Scans all coins for YES or NO token priced 75-85¢
  - No BS edge required — pure momentum play
  - Score = 1.0 - price (potential upside to 99¢)
  - Marked is_fallback = True for ML tracking

  Step 19 — Rank opportunities (bot.py:2460)
  Sort by combined_score descending (highest first)

  Step 20 — Budget allocation (bot.py:2472-2479)
  For each opportunity (best first):
    if min_cost ($1.00) <= budget_left → SELECT it
    break  (only 1 coin per round)

  Step 21 — Bet sizing (bot.py:2497-2498)
  progressive_bet = strategy.get_current_bet()  (initial * 1.10^consecutive_wins, capped at 5x)
  bet_amt = min(progressive_bet, effective_budget, balance * 0.95)
  if bet_amt < $1.00 → SKIP

  Step 22 — Order placement (bot.py:2518-2543)
  - Learning mode (E): learning_simulator.simulate_order() — virtual, no real money
  - Live mode (D): market_15m.place_prediction(coin, direction, bet_amt) — real CLOB order

  Step 23 — Post-order tracking (bot.py:2545-2567)
  - Saves start_price and td_metadata on the order object
  - Updates round_budget_spent, adds coin to round_coins_bet
  - Real mode: tracks via order_tracker and optionally position_tracker
  - Adds to current_round_bets for settlement

  ---
  Summary: The 12 Gates

  A coin must pass all of these to get a trade in Mode D:
  ┌─────┬────────────────────────────────┬─────────────────────────────────┐
  │  #  │              Gate              │            Threshold            │
  ├─────┼────────────────────────────────┼─────────────────────────────────┤
  │ 1   │ Round budget remaining         │ ≥ $0.10                         │
  ├─────┼────────────────────────────────┼─────────────────────────────────┤
  │ 2   │ Not already bet this round     │ coin not in round_coins_bet     │
  ├─────┼────────────────────────────────┼─────────────────────────────────┤
  │ 3   │ Can fetch Polymarket prices    │ get_both_prices() succeeds      │
  ├─────┼────────────────────────────────┼─────────────────────────────────┤
  │ 4   │ Min order vs budget            │ $1.00 ≤ effective budget        │
  ├─────┼────────────────────────────────┼─────────────────────────────────┤
  │ 5   │ Direction determinable         │ spot vs strike comparison       │
  ├─────┼────────────────────────────────┼─────────────────────────────────┤
  │ 6   │ Time remaining ≤ entry window  │ ≤ 420s (or ML-learned)          │
  ├─────┼────────────────────────────────┼─────────────────────────────────┤
  │ 7   │ Token price in range           │ 75¢ ≤ price ≤ 85¢               │
  ├─────┼────────────────────────────────┼─────────────────────────────────┤
  │ 8   │ BS edge ≥ 15%                  │ fair_prob - market_price ≥ 0.15 │
  ├─────┼────────────────────────────────┼─────────────────────────────────┤
  │ 9   │ Spot moved from strike         │ > 0.5% distance                 │
  ├─────┼────────────────────────────────┼─────────────────────────────────┤
  │ 10  │ validate_trade() price check   │ 75¢ ≤ price ≤ 85¢ (safety net)  │
  ├─────┼────────────────────────────────┼─────────────────────────────────┤
  │ 11  │ validate_trade() balance check │ balance ≥ $1.00                 │
  ├─────┼────────────────────────────────┼─────────────────────────────────┤
  │ 12  │ Final bet ≥ min order          │ bet_amt ≥ $1.00                 │
  └─────┴────────────────────────────────┴─────────────────────────────────┘
  If all 12 pass → order placed. If none pass for any coin → fallback checks (gate 6 relaxed to ≤200s, gates 8-9 dropped, pure momentum).