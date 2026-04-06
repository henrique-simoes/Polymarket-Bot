#!/usr/bin/env python3
"""
Empirical validation: 30 days of BTC 15-min binary options.

For each 15-min window:
  - Strike = open price
  - Track price path minute-by-minute
  - Estimate token prices via BS (realized vol)
  - Identify when a token first drops to ≤20¢ (reversal opportunity)
  - Check if that cheap token actually won

Saves all data to data/validation_30d.json for further analysis.
"""

import ccxt
import json
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta, timezone
import time as time_module


def fetch_1m_candles(symbol='BTC/USDT', days=30):
    """Fetch N days of 1-minute candles from Binance."""
    exchange = ccxt.binance()
    all_candles = []
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    end = int(datetime.now(timezone.utc).timestamp() * 1000)

    print(f"Fetching {days} days of 1m {symbol} candles...")

    while since < end:
        try:
            candles = exchange.fetch_ohlcv(symbol, '1m', since=since, limit=1000)
            if not candles:
                break
            all_candles.extend(candles)
            since = candles[-1][0] + 60000
            if len(all_candles) % 10000 < 1000:
                print(f"  ...{len(all_candles):,} candles")
            if len(candles) < 1000:
                break
            time_module.sleep(0.3)
        except Exception as e:
            print(f"  Error: {e}, retrying in 2s...")
            time_module.sleep(2)

    print(f"  Done: {len(all_candles):,} candles")
    return all_candles


def realized_vol(closes):
    """Annualized vol from 1-min closes."""
    if len(closes) < 3:
        return 0.80
    rets = np.diff(np.log(np.array(closes, dtype=float)))
    s = np.std(rets)
    if s == 0:
        return 0.80
    return float(s * np.sqrt(365.25 * 24 * 60))


def bs_prob_up(spot, strike, vol, secs_left):
    """BS probability spot > strike at expiry."""
    if secs_left <= 0:
        return 1.0 if spot > strike else (0.0 if spot < strike else 0.5)
    T = secs_left / (365.25 * 24 * 3600)
    sig = vol * np.sqrt(T)
    if sig < 1e-12:
        return 1.0 if spot > strike else 0.0
    d = (np.log(spot / strike) + 0.5 * vol ** 2 * T) / sig
    return float(norm.cdf(d))


def main():
    candles = fetch_1m_candles('BTC/USDT', days=30)
    if len(candles) < 1000:
        print("Not enough candle data"); return

    # Sort and deduplicate
    candles.sort(key=lambda c: c[0])
    seen = set()
    unique = []
    for c in candles:
        if c[0] not in seen:
            seen.add(c[0])
            unique.append(c)
    candles = unique

    all_closes = [c[4] for c in candles]
    all_ts = [c[0] // 1000 for c in candles]

    # Group into 15-min windows (aligned :00/:15/:30/:45)
    windows = {}
    for c in candles:
        ts = c[0] // 1000
        ws = ts - (ts % 900)
        windows.setdefault(ws, []).append(c)

    complete = {k: sorted(v, key=lambda x: x[0])
                for k, v in windows.items() if len(v) >= 14}
    print(f"Complete 15-min windows: {len(complete):,}")

    # ── Analyze every window ──
    all_windows_data = []  # Save for JSON
    reversal_picks = []     # Tokens that hit ≤ threshold

    for ws in sorted(complete.keys()):
        clist = complete[ws]
        strike = clist[0][1]    # Open of first candle
        final = clist[-1][4]    # Close of last candle

        if strike == 0:
            continue

        outcome = 'UP' if final > strike else ('DOWN' if final < strike else 'PUSH')
        if outcome == 'PUSH':
            continue

        # Trailing 30-candle realized vol
        idx = next((i for i, t in enumerate(all_ts) if t >= ws), 0)
        vol = realized_vol(all_closes[max(0, idx - 30):idx])

        # Minute-by-minute token prices
        minute_data = []
        first_cheap = {}  # {threshold: {minute, direction, price}} — first time token ≤ threshold

        for m, candle in enumerate(clist):
            spot = candle[4]  # Close
            secs_left = max((len(clist) - m - 1) * 60, 1)
            p_up = bs_prob_up(spot, strike, vol, secs_left)
            up_price = round(p_up, 4)
            down_price = round(1.0 - p_up, 4)
            cheap_side = 'UP' if up_price <= down_price else 'DOWN'
            cheap_price = min(up_price, down_price)

            minute_data.append({
                'minute': m,
                'secs_left': secs_left,
                'spot': spot,
                'up_price': up_price,
                'down_price': down_price,
                'cheap_side': cheap_side,
                'cheap_price': round(cheap_price, 4),
                'distance_pct': round((spot - strike) / strike * 100, 4),
            })

            # Track first time a token hits various thresholds
            for thresh in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
                if thresh not in first_cheap:
                    if up_price <= thresh:
                        first_cheap[thresh] = {'minute': m, 'direction': 'UP', 'price': up_price}
                    elif down_price <= thresh:
                        first_cheap[thresh] = {'minute': m, 'direction': 'DOWN', 'price': down_price}

        window_record = {
            'window_start': ws,
            'time_utc': datetime.fromtimestamp(ws, tz=timezone.utc).isoformat(),
            'strike': strike,
            'final': final,
            'outcome': outcome,
            'vol': round(vol, 4),
            'minutes': minute_data,
            'first_cheap': {},
        }

        # Record reversal picks
        for thresh, info in first_cheap.items():
            won = (info['direction'] == outcome)
            window_record['first_cheap'][str(thresh)] = {
                'minute': info['minute'],
                'direction': info['direction'],
                'token_price': info['price'],
                'won': won,
            }
            reversal_picks.append({
                'threshold': thresh,
                'window_start': ws,
                'minute_entered': info['minute'],
                'secs_left_at_entry': max((len(clist) - info['minute'] - 1) * 60, 1),
                'direction': info['direction'],
                'token_price': info['price'],
                'strike': strike,
                'final': final,
                'vol': vol,
                'won': won,
            })

        all_windows_data.append(window_record)

    # ── Save all data ──
    save_path = 'data/validation_30d.json'
    with open(save_path, 'w') as f:
        json.dump({
            'generated': datetime.now(timezone.utc).isoformat(),
            'symbol': 'BTC/USDT',
            'days': 30,
            'total_windows': len(all_windows_data),
            'windows': all_windows_data,
            'reversal_picks': reversal_picks,
        }, f, indent=2)
    print(f"\nSaved {len(all_windows_data)} windows to {save_path}")

    # ── REVERSAL ANALYSIS ──
    print(f"\n{'=' * 95}")
    print(f"  REVERSAL STRATEGY: Buy the first token to drop to ≤ X¢  (BTC, 30 days, $1 bets)")
    print(f"{'=' * 95}")
    print(f"  {'Threshold':>10}  {'Opps':>6}  {'Wins':>5}  {'Win Rate':>9}  {'Avg Price':>10}  "
          f"{'BE':>6}  {'Edge':>7}  {'Win$':>7}  {'P&L':>10}  {'MaxLoss':>8}  {'Capital':>8}")
    print(f"  {'─' * 93}")

    for thresh in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
        picks = [p for p in reversal_picks if p['threshold'] == thresh]
        if not picks:
            print(f"  {'≤' + str(int(thresh*100)) + '¢':>10}  {'0':>6}  —")
            continue

        wins = sum(1 for p in picks if p['won'])
        total = len(picks)
        wr = wins / total
        avg_p = np.mean([p['token_price'] for p in picks])
        be = avg_p  # break-even = avg token price
        edge = wr - be

        # P&L: win pays (1/avg_price - 1) per $1, loss = -$1
        win_profit = (1.0 / avg_p) - 1.0
        pnl = wins * win_profit - (total - wins) * 1.0

        # Longest losing streak
        streak = 0
        max_streak = 0
        for p in picks:
            if not p['won']:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        capital = max_streak + 10  # Buffer

        print(f"  {'≤' + str(int(thresh*100)) + '¢':>10}  {total:>6}  {wins:>5}  {wr:>8.1%}  "
              f"  {avg_p:>8.1%}  {be:>5.1%}  {edge:>+6.1%}  ${win_profit:>5.2f}  "
              f"${pnl:>+8,.0f}  {max_streak:>7}  ${capital:>6}")

    # ── ENTRY TIMING BREAKDOWN for ≤20¢ ──
    print(f"\n{'=' * 95}")
    print(f"  ≤20¢ REVERSAL — BY ENTRY TIMING")
    print(f"{'=' * 95}")

    picks_20 = [p for p in reversal_picks if p['threshold'] == 0.20]
    if picks_20:
        # Group by minutes remaining at entry
        by_time = {}
        for p in picks_20:
            secs = p['secs_left_at_entry']
            bucket = f"{secs // 60}min"
            by_time.setdefault(bucket, []).append(p)

        print(f"  {'Time Left':>10}  {'Opps':>6}  {'Wins':>5}  {'Win Rate':>9}  {'Avg Price':>10}")
        for bucket in sorted(by_time.keys(), key=lambda x: int(x.replace('min', '')), reverse=True):
            picks_b = by_time[bucket]
            w = sum(1 for p in picks_b if p['won'])
            t = len(picks_b)
            wr = w / t if t else 0
            ap = np.mean([p['token_price'] for p in picks_b])
            print(f"  {bucket:>10}  {t:>6}  {w:>5}  {wr:>8.1%}  {ap:>9.1%}")

    # ── HIGH-PROB COMPARISON ──
    print(f"\n{'=' * 95}")
    print(f"  HIGH-PROB COMPARISON: Buy the expensive token (≥ X¢)")
    print(f"{'=' * 95}")
    print(f"  {'Threshold':>10}  {'Opps':>6}  {'Wins':>5}  {'Win Rate':>9}  {'Avg Price':>10}  "
          f"{'BE':>6}  {'Edge':>7}  {'Win$':>7}  {'P&L':>10}  {'MaxLoss':>8}  {'Capital':>8}")
    print(f"  {'─' * 93}")

    # Use the same windows but pick the EXPENSIVE side
    for min_price in [0.75, 0.80, 0.85, 0.90, 0.93]:
        eligible = []
        for w in all_windows_data:
            # At 5 min remaining (minute 10)
            if len(w['minutes']) <= 10:
                continue
            m10 = w['minutes'][10]
            up_p = m10['up_price']
            down_p = m10['down_price']

            # Pick the expensive side
            if up_p >= min_price:
                eligible.append({'price': up_p, 'direction': 'UP', 'outcome': w['outcome']})
            if down_p >= min_price:
                eligible.append({'price': down_p, 'direction': 'DOWN', 'outcome': w['outcome']})

        if not eligible:
            print(f"  {'≥' + str(int(min_price*100)) + '¢':>10}  {'0':>6}  —")
            continue

        wins = sum(1 for e in eligible if e['direction'] == e['outcome'])
        total = len(eligible)
        wr = wins / total
        avg_p = np.mean([e['price'] for e in eligible])
        be = avg_p
        edge = wr - be
        win_profit = (1.0 / avg_p) - 1.0
        pnl = wins * win_profit - (total - wins) * 1.0

        streak = 0
        max_streak = 0
        for e in eligible:
            if e['direction'] != e['outcome']:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        capital = max_streak + 10

        print(f"  {'≥' + str(int(min_price*100)) + '¢':>10}  {total:>6}  {wins:>5}  {wr:>8.1%}  "
              f"  {avg_p:>8.1%}  {be:>5.1%}  {edge:>+6.1%}  ${win_profit:>5.2f}  "
              f"${pnl:>+8,.0f}  {max_streak:>7}  ${capital:>6}")

    # ── SUMMARY ──
    print(f"\n{'=' * 95}")
    print(f"  SUMMARY")
    print(f"{'=' * 95}")
    picks_20 = [p for p in reversal_picks if p['threshold'] == 0.20]
    if picks_20:
        wins = sum(1 for p in picks_20 if p['won'])
        total = len(picks_20)
        wr = wins / total
        avg_p = np.mean([p['token_price'] for p in picks_20])
        win_profit = (1.0 / avg_p) - 1.0
        pnl = wins * win_profit - (total - wins) * 1.0
        print(f"  ≤20¢ reversal: {total} opportunities, {wins} wins ({wr:.1%}), P&L: ${pnl:+,.0f}")
        print(f"  Average entry: {avg_p:.1%} → win pays ${win_profit:.2f}, loss costs $1.00")
        if wr > avg_p:
            print(f"  EDGE IS POSITIVE: {wr - avg_p:+.1%} above break-even")
        else:
            print(f"  EDGE IS NEGATIVE: {wr - avg_p:+.1%} below break-even")

    print(f"\n  Data saved to {save_path} — use for further analysis")


if __name__ == '__main__':
    main()
