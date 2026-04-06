#!/usr/bin/env python3
"""
Fetch ACTUAL Polymarket price data for 30 days of BTC 15-min markets.

Pipeline:
  1. Gamma API → all resolved BTC 15-min markets (condition IDs, outcomes, token IDs)
  2. CLOB prices-history → actual token price snapshots during each window
  3. Binance 1-min candles → minute-by-minute spot prices
  4. Compare: actual Polymarket prices vs BS estimates
  5. Calculate real win rates from source data

Saves everything to data/polymarket_validation_30d.json
"""

import ccxt
import json
import numpy as np
import requests
from scipy.stats import norm
from datetime import datetime, timedelta, timezone
import time as time_module
import os
import sys


GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
TAG_ID_15M = 102467


def fetch_gamma_markets(coin_slug='btc', days=30):
    """Fetch all resolved 15-min markets for a coin from Gamma API."""
    all_markets = []
    offset = 0
    limit = 100
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')

    print(f"Fetching resolved {coin_slug.upper()} 15-min markets from Gamma API...")

    while True:
        try:
            resp = requests.get(f"{GAMMA_API}/markets", params={
                'tag_id': TAG_ID_15M,
                'closed': 'true',
                'order': 'endDate',
                'ascending': 'false',
                'limit': limit,
                'offset': offset,
            }, timeout=15)
            resp.raise_for_status()
            markets = resp.json()

            if not markets:
                break

            for m in markets:
                slug = m.get('slug', '')
                end_date = m.get('endDate', '')

                # Filter: only our coin
                if not slug.startswith(f'{coin_slug}-'):
                    continue

                # Filter: within date range
                if end_date < cutoff_str:
                    # Markets are ordered by endDate desc, so we're past our range
                    print(f"  Reached cutoff date at offset {offset}")
                    return all_markets

                # Parse outcome
                try:
                    prices = json.loads(m['outcomePrices']) if isinstance(m['outcomePrices'], str) else m['outcomePrices']
                    tokens = json.loads(m['clobTokenIds']) if isinstance(m['clobTokenIds'], str) else m['clobTokenIds']
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

                if len(prices) != 2 or len(tokens) != 2:
                    continue

                # Determine winner
                try:
                    p0, p1 = float(prices[0]), float(prices[1])
                except (ValueError, TypeError):
                    continue

                if p0 > 0.5:
                    winner = 'UP'
                elif p1 > 0.5:
                    winner = 'DOWN'
                else:
                    continue  # Not clearly resolved

                all_markets.append({
                    'conditionId': m['conditionId'],
                    'slug': slug,
                    'question': m.get('question', ''),
                    'endDate': end_date,
                    'winner': winner,
                    'outcomePrices': prices,
                    'upTokenId': tokens[0],
                    'downTokenId': tokens[1],
                    'volume': m.get('volume', 0),
                })

            offset += limit
            if len(markets) < limit:
                break

            if len(all_markets) % 500 < 100:
                print(f"  ...{len(all_markets)} markets collected (offset={offset})")

            time_module.sleep(0.2)

        except Exception as e:
            print(f"  Error at offset {offset}: {e}")
            time_module.sleep(2)
            offset += limit

    return all_markets


def fetch_clob_price_history(token_id, retries=3):
    """Fetch price history for a token from CLOB API."""
    for attempt in range(retries):
        try:
            resp = requests.get(f"{CLOB_API}/prices-history", params={
                'market': token_id,
                'interval': '1m',
                'fidelity': 10,  # Maximum resolution
            }, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('history', [])
            return []
        except Exception:
            if attempt < retries - 1:
                time_module.sleep(1)
    return []


def fetch_binance_1m(symbol='BTC/USDT', days=30):
    """Fetch 1-min candles from Binance."""
    exchange = ccxt.binance()
    all_candles = []
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    end = int(datetime.now(timezone.utc).timestamp() * 1000)

    print(f"Fetching {days} days of 1m {symbol} candles from Binance...")

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
            print(f"  Error: {e}, retrying...")
            time_module.sleep(2)

    # Deduplicate
    seen = set()
    unique = []
    for c in sorted(all_candles, key=lambda x: x[0]):
        if c[0] not in seen:
            seen.add(c[0])
            unique.append(c)

    print(f"  Done: {len(unique):,} candles")
    return unique


def realized_vol(closes):
    """Annualized vol from 1-min closes."""
    if len(closes) < 3:
        return 0.80
    rets = np.diff(np.log(np.array(closes, dtype=float)))
    s = np.std(rets)
    return float(s * np.sqrt(365.25 * 24 * 60)) if s > 0 else 0.80


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
    # ── Step 1: Fetch Gamma markets ──
    markets = fetch_gamma_markets('btc', days=30)
    print(f"\nTotal BTC markets: {len(markets)}")

    if not markets:
        print("No markets found!")
        return

    # ── Step 2: Fetch Binance candles ──
    binance_candles = fetch_binance_1m('BTC/USDT', days=30)

    # Index Binance data by timestamp for fast lookup
    binance_by_ts = {}
    for c in binance_candles:
        ts = c[0] // 1000
        binance_by_ts[ts] = c  # [timestamp_ms, O, H, L, C, V]

    all_closes = [c[4] for c in binance_candles]
    all_ts = [c[0] // 1000 for c in binance_candles]

    # ── Step 3: Fetch CLOB price history for each market ──
    print(f"\nFetching CLOB price history for {len(markets)} markets...")

    # Check for cached progress
    cache_path = 'data/polymarket_validation_cache.json'
    cached = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                cached = json.load(f)
            print(f"  Resuming from cache: {len(cached)} markets already fetched")
        except Exception:
            cached = {}

    fetched_count = 0
    for i, mkt in enumerate(markets):
        cid = mkt['conditionId']

        if cid in cached:
            mkt['price_history_up'] = cached[cid].get('up', [])
            mkt['price_history_down'] = cached[cid].get('down', [])
            continue

        # Fetch UP token price history
        up_hist = fetch_clob_price_history(mkt['upTokenId'])
        down_hist = fetch_clob_price_history(mkt['downTokenId'])

        mkt['price_history_up'] = up_hist
        mkt['price_history_down'] = down_hist

        # Cache
        cached[cid] = {'up': up_hist, 'down': down_hist}
        fetched_count += 1

        if fetched_count % 50 == 0:
            print(f"  ...{fetched_count} fetched, {i+1}/{len(markets)} processed")
            # Save cache periodically
            with open(cache_path, 'w') as f:
                json.dump(cached, f)

        time_module.sleep(0.15)  # Rate limit: ~6 req/s

    # Final cache save
    with open(cache_path, 'w') as f:
        json.dump(cached, f)
    print(f"  Done: fetched {fetched_count} new, {len(markets) - fetched_count} from cache")

    # ── Step 4: Analyze each market ──
    print(f"\nAnalyzing {len(markets)} markets...")

    results = []
    polymarket_snapshots = []  # For calibration analysis

    for mkt in markets:
        # Parse window times
        # endDate format: "2026-02-07T22:15:00Z"
        try:
            end_dt = datetime.fromisoformat(mkt['endDate'].replace('Z', '+00:00'))
        except Exception:
            continue

        end_ts = int(end_dt.timestamp())
        start_ts = end_ts - 900  # 15-min window

        # Get Binance candles in this window
        window_candles = []
        for sec in range(start_ts, end_ts + 1, 60):
            if sec in binance_by_ts:
                window_candles.append(binance_by_ts[sec])

        if len(window_candles) < 10:
            continue

        strike = window_candles[0][1]  # Open of first candle
        final_close = window_candles[-1][4]

        if strike == 0 or final_close == strike:
            continue

        binance_outcome = 'UP' if final_close > strike else 'DOWN'
        gamma_outcome = mkt['winner']

        # Trailing realized vol
        idx = next((i for i, t in enumerate(all_ts) if t >= start_ts), 0)
        vol = realized_vol(all_closes[max(0, idx - 30):idx])

        # Extract Polymarket price points within the 15-min window
        poly_points_up = []
        poly_points_down = []

        for pt in mkt.get('price_history_up', []):
            t = pt.get('t', 0)
            p = pt.get('p', 0)
            if start_ts <= t <= end_ts:
                poly_points_up.append({'t': t, 'p': p, 'secs_left': end_ts - t})

        for pt in mkt.get('price_history_down', []):
            t = pt.get('t', 0)
            p = pt.get('p', 0)
            if start_ts <= t <= end_ts:
                poly_points_down.append({'t': t, 'p': p, 'secs_left': end_ts - t})

        # BS estimates at each Polymarket snapshot time
        for pp in poly_points_up:
            secs = pp['secs_left']
            # Find closest Binance candle
            closest_ts = start_ts + ((pp['t'] - start_ts) // 60) * 60
            if closest_ts in binance_by_ts:
                spot = binance_by_ts[closest_ts][4]
                bs_up = bs_prob_up(spot, strike, vol, secs)
                pp['bs_estimate'] = round(bs_up, 4)
                pp['spot'] = spot
                pp['divergence'] = round(pp['p'] - bs_up, 4)

                polymarket_snapshots.append({
                    'conditionId': mkt['conditionId'],
                    'secs_left': secs,
                    'poly_up_price': pp['p'],
                    'bs_up_price': round(bs_up, 4),
                    'divergence': round(pp['p'] - bs_up, 4),
                    'spot': spot,
                    'strike': strike,
                    'vol': round(vol, 4),
                    'outcome': gamma_outcome,
                    'volume': mkt.get('volume', 0),
                })

        # Minute-by-minute BS analysis (from Binance)
        minute_bs = []
        for m, candle in enumerate(window_candles):
            spot = candle[4]
            secs_left = max((len(window_candles) - m - 1) * 60, 1)
            p_up = bs_prob_up(spot, strike, vol, secs_left)
            minute_bs.append({
                'minute': m,
                'secs_left': secs_left,
                'spot': spot,
                'bs_up': round(p_up, 4),
                'bs_down': round(1 - p_up, 4),
            })

        results.append({
            'conditionId': mkt['conditionId'],
            'slug': mkt['slug'],
            'endDate': mkt['endDate'],
            'strike': strike,
            'final_close': final_close,
            'binance_outcome': binance_outcome,
            'gamma_outcome': gamma_outcome,
            'outcomes_agree': binance_outcome == gamma_outcome,
            'vol': round(vol, 4),
            'volume': mkt.get('volume', 0),
            'poly_points_up': poly_points_up,
            'poly_points_down': poly_points_down,
            'minute_bs': minute_bs,
        })

    print(f"  Analyzed: {len(results)} markets with complete data")

    # ── Save all data ──
    save_path = 'data/polymarket_validation_30d.json'
    with open(save_path, 'w') as f:
        json.dump({
            'generated': datetime.now(timezone.utc).isoformat(),
            'symbol': 'BTC',
            'days': 30,
            'total_markets': len(results),
            'markets': results,
            'polymarket_snapshots': polymarket_snapshots,
        }, f)
    print(f"  Saved to {save_path}")

    # ── Step 5: Analysis ──

    # 5a: Outcome agreement (Binance vs Gamma/on-chain)
    agree = sum(1 for r in results if r['outcomes_agree'])
    disagree = len(results) - agree
    print(f"\n{'=' * 95}")
    print(f"  OUTCOME AGREEMENT: Binance close vs Gamma resolution")
    print(f"{'=' * 95}")
    print(f"  Agree: {agree}/{len(results)} ({agree/len(results)*100:.1f}%)")
    print(f"  Disagree: {disagree}/{len(results)} ({disagree/len(results)*100:.1f}%)")
    if disagree > 0:
        print(f"  NOTE: Disagreements = Polymarket uses official oracle, not Binance close")
        for r in results:
            if not r['outcomes_agree']:
                print(f"    {r['slug']}: Binance={r['binance_outcome']}, Gamma={r['gamma_outcome']}, "
                      f"strike={r['strike']}, close={r['final_close']}")
                if len([r2 for r2 in results if not r2['outcomes_agree']]) > 10:
                    break

    # 5b: Polymarket vs BS divergence
    if polymarket_snapshots:
        print(f"\n{'=' * 95}")
        print(f"  POLYMARKET vs BLACK-SCHOLES PRICE DIVERGENCE")
        print(f"{'=' * 95}")
        print(f"  Total price snapshots within 15-min windows: {len(polymarket_snapshots)}")

        divs = [s['divergence'] for s in polymarket_snapshots]
        print(f"  Mean divergence (Poly - BS): {np.mean(divs):+.4f}")
        print(f"  Median divergence:           {np.median(divs):+.4f}")
        print(f"  Std deviation:               {np.std(divs):.4f}")
        print(f"  Range:                        [{min(divs):.4f}, {max(divs):.4f}]")

        # Divergence by token price bucket
        print(f"\n  Divergence by Polymarket UP token price:")
        print(f"  {'Poly Price':>12}  {'Count':>6}  {'Mean Div':>10}  {'Median Div':>11}  {'Poly > BS':>10}")
        buckets = [(0, 0.10), (0.10, 0.20), (0.20, 0.30), (0.30, 0.40), (0.40, 0.50),
                   (0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 1.0)]
        for lo, hi in buckets:
            bucket_snaps = [s for s in polymarket_snapshots if lo <= s['poly_up_price'] < hi]
            if not bucket_snaps:
                continue
            bd = [s['divergence'] for s in bucket_snaps]
            poly_higher = sum(1 for d in bd if d > 0)
            print(f"  {lo*100:>5.0f}-{hi*100:<5.0f}¢  {len(bucket_snaps):>6}  {np.mean(bd):>+9.4f}  "
                  f"{np.median(bd):>+10.4f}  {poly_higher/len(bucket_snaps):>9.1%}")

    # 5c: Win rate analysis using ACTUAL Polymarket prices
    # Use the price snapshots: if Polymarket UP token was ≤ X¢, did DOWN win? (reversal)
    print(f"\n{'=' * 95}")
    print(f"  WIN RATE FROM ACTUAL POLYMARKET PRICES (reversal: buy cheap token)")
    print(f"{'=' * 95}")

    # Collect: for each snapshot, check if cheap token won
    # We use gamma_outcome as ground truth
    cheap_picks = []
    for snap in polymarket_snapshots:
        poly_up = snap['poly_up_price']
        poly_down = 1.0 - poly_up  # Approximate
        outcome = snap['outcome']

        # Check both sides
        if poly_up <= 0.30:
            cheap_picks.append({
                'direction': 'UP',
                'price': poly_up,
                'won': outcome == 'UP',
                'secs_left': snap['secs_left'],
                'volume': snap['volume'],
            })
        if poly_down <= 0.30:
            cheap_picks.append({
                'direction': 'DOWN',
                'price': poly_down,
                'won': outcome == 'DOWN',
                'secs_left': snap['secs_left'],
                'volume': snap['volume'],
            })

    if cheap_picks:
        print(f"  {'Threshold':>10}  {'Opps':>6}  {'Wins':>5}  {'Win Rate':>9}  {'Avg Price':>10}  "
              f"{'BE':>6}  {'Edge':>7}  {'Win$/bet':>8}  {'P&L':>10}")
        print(f"  {'─' * 85}")

        for thresh in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
            eligible = [p for p in cheap_picks if p['price'] <= thresh]
            if not eligible:
                print(f"  {'≤' + str(int(thresh*100)) + '¢':>10}  {'0':>6}  —")
                continue
            wins = sum(1 for p in eligible if p['won'])
            total = len(eligible)
            wr = wins / total
            avg_p = np.mean([p['price'] for p in eligible])
            be = avg_p
            edge = wr - be
            win_profit = (1.0 / avg_p) - 1.0 if avg_p > 0 else 0
            pnl = wins * win_profit - (total - wins) * 1.0

            print(f"  {'≤' + str(int(thresh*100)) + '¢':>10}  {total:>6}  {wins:>5}  {wr:>8.1%}  "
                  f"  {avg_p:>8.1%}  {be:>5.1%}  {edge:>+6.1%}  ${win_profit:>6.2f}  ${pnl:>+8,.0f}")
    else:
        print(f"  No cheap token snapshots found in Polymarket data")
        print(f"  (prices-history has ~2-3 points per window, many may not show sub-20¢ prices)")

    # 5d: Win rate for expensive tokens
    expensive_picks = []
    for snap in polymarket_snapshots:
        poly_up = snap['poly_up_price']
        poly_down = 1.0 - poly_up
        outcome = snap['outcome']

        if poly_up >= 0.75:
            expensive_picks.append({
                'direction': 'UP',
                'price': poly_up,
                'won': outcome == 'UP',
                'secs_left': snap['secs_left'],
            })
        if poly_down >= 0.75:
            expensive_picks.append({
                'direction': 'DOWN',
                'price': poly_down,
                'won': outcome == 'DOWN',
                'secs_left': snap['secs_left'],
            })

    if expensive_picks:
        print(f"\n{'=' * 95}")
        print(f"  WIN RATE FROM ACTUAL POLYMARKET PRICES (buy expensive token ≥ X¢)")
        print(f"{'=' * 95}")
        print(f"  {'Threshold':>10}  {'Opps':>6}  {'Wins':>5}  {'Win Rate':>9}  {'Avg Price':>10}  "
              f"{'BE':>6}  {'Edge':>7}  {'Win$/bet':>8}  {'P&L':>10}")
        print(f"  {'─' * 85}")

        for min_p in [0.75, 0.80, 0.85, 0.90, 0.93]:
            eligible = [p for p in expensive_picks if p['price'] >= min_p]
            if not eligible:
                continue
            wins = sum(1 for p in eligible if p['won'])
            total = len(eligible)
            wr = wins / total
            avg_p = np.mean([p['price'] for p in eligible])
            be = avg_p
            edge = wr - be
            win_profit = (1.0 / avg_p) - 1.0 if avg_p > 0 else 0
            pnl = wins * win_profit - (total - wins) * 1.0

            print(f"  {'≥' + str(int(min_p*100)) + '¢':>10}  {total:>6}  {wins:>5}  {wr:>8.1%}  "
                  f"  {avg_p:>8.1%}  {be:>5.1%}  {edge:>+6.1%}  ${win_profit:>6.2f}  ${pnl:>+8,.0f}")

    # 5e: Hybrid analysis — BS-estimated prices + Gamma outcomes (most data points)
    print(f"\n{'=' * 95}")
    print(f"  HYBRID: BS-estimated token prices + Gamma on-chain outcomes")
    print(f"  (uses minute-by-minute Binance data for prices, Gamma for settlement)")
    print(f"{'=' * 95}")

    # For each market, at each minute, check if BS token was ≤ threshold → did it win?
    hybrid_picks = {t: [] for t in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]}
    hybrid_expensive = {t: [] for t in [0.75, 0.80, 0.85, 0.90, 0.93]}

    for r in results:
        outcome = r['gamma_outcome']  # Use Gamma (verified = on-chain)
        first_seen = {}  # Track first time each threshold is hit

        for mb in r['minute_bs']:
            up_p = mb['bs_up']
            down_p = mb['bs_down']

            # Cheap tokens (reversal picks)
            for thresh in hybrid_picks:
                if thresh not in first_seen:
                    if up_p <= thresh:
                        first_seen[thresh] = True
                        hybrid_picks[thresh].append({
                            'direction': 'UP', 'price': up_p,
                            'won': outcome == 'UP', 'secs_left': mb['secs_left']
                        })
                    elif down_p <= thresh:
                        first_seen[thresh] = True
                        hybrid_picks[thresh].append({
                            'direction': 'DOWN', 'price': down_p,
                            'won': outcome == 'DOWN', 'secs_left': mb['secs_left']
                        })

            # Expensive tokens (at 5 min remaining only)
            if mb['secs_left'] == 300 or (240 <= mb['secs_left'] <= 360 and mb['minute'] >= 9):
                for min_p in hybrid_expensive:
                    if up_p >= min_p:
                        hybrid_expensive[min_p].append({
                            'direction': 'UP', 'price': up_p,
                            'won': outcome == 'UP'
                        })
                    if down_p >= min_p:
                        hybrid_expensive[min_p].append({
                            'direction': 'DOWN', 'price': down_p,
                            'won': outcome == 'DOWN'
                        })

    print(f"\n  REVERSAL (buy first token to drop ≤ X¢, outcomes from Gamma/on-chain):")
    print(f"  {'Threshold':>10}  {'Opps':>6}  {'Wins':>5}  {'Win Rate':>9}  {'Avg Price':>10}  "
          f"{'BE':>6}  {'Edge':>7}  {'Win$/bet':>8}  {'30d P&L':>10}  {'Capital':>8}")
    print(f"  {'─' * 90}")

    for thresh in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
        picks = hybrid_picks[thresh]
        if not picks:
            print(f"  {'≤' + str(int(thresh*100)) + '¢':>10}  {'0':>6}  —")
            continue
        wins = sum(1 for p in picks if p['won'])
        total = len(picks)
        wr = wins / total
        avg_p = np.mean([p['price'] for p in picks])
        be = avg_p
        edge = wr - be
        win_profit = (1.0 / avg_p) - 1.0 if avg_p > 0 else 0
        pnl = wins * win_profit - (total - wins) * 1.0

        streak = 0
        max_streak = 0
        for p in picks:
            if not p['won']:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        print(f"  {'≤' + str(int(thresh*100)) + '¢':>10}  {total:>6}  {wins:>5}  {wr:>8.1%}  "
              f"  {avg_p:>8.1%}  {be:>5.1%}  {edge:>+6.1%}  ${win_profit:>6.2f}  "
              f"${pnl:>+8,.0f}  ${max_streak + 10:>6}")

    print(f"\n  HIGH-PROB (buy token ≥ X¢ at ~5min remaining, outcomes from Gamma/on-chain):")
    print(f"  {'Threshold':>10}  {'Opps':>6}  {'Wins':>5}  {'Win Rate':>9}  {'Avg Price':>10}  "
          f"{'BE':>6}  {'Edge':>7}  {'Win$/bet':>8}  {'30d P&L':>10}")
    print(f"  {'─' * 85}")

    for min_p in [0.75, 0.80, 0.85, 0.90, 0.93]:
        picks = hybrid_expensive[min_p]
        if not picks:
            continue
        wins = sum(1 for p in picks if p['won'])
        total = len(picks)
        wr = wins / total
        avg_p = np.mean([p['price'] for p in picks])
        be = avg_p
        edge = wr - be
        win_profit = (1.0 / avg_p) - 1.0 if avg_p > 0 else 0
        pnl = wins * win_profit - (total - wins) * 1.0

        print(f"  {'≥' + str(int(min_p*100)) + '¢':>10}  {total:>6}  {wins:>5}  {wr:>8.1%}  "
              f"  {avg_p:>8.1%}  {be:>5.1%}  {edge:>+6.1%}  ${win_profit:>6.2f}  ${pnl:>+8,.0f}")

    print(f"\n  All data saved to {save_path}")
    print(f"  Cache saved to {cache_path} (rerun to skip re-fetching)")


if __name__ == '__main__':
    main()
