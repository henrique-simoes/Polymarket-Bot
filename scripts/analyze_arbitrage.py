#!/usr/bin/env python3
"""
Arbitrage analysis from saved Polymarket + Binance data.

1. Pure hedged arb: UP + DOWN < $1 (risk-free)
2. Directional arb: Polymarket price diverges from BS → bet the underpriced side
3. Cross-snapshot: When Polymarket UP is cheap vs BS, does buying it win?
"""

import json
import numpy as np
from collections import defaultdict


def main():
    # Load saved data
    with open('data/polymarket_validation_30d.json') as f:
        data = json.load(f)

    markets = data['markets']
    snapshots = data['polymarket_snapshots']
    print(f"Loaded {len(markets)} markets, {len(snapshots)} price snapshots")

    # ═══ 1. PURE HEDGED ARBITRAGE: UP + DOWN < $1 ═══
    print(f"\n{'=' * 90}")
    print(f"  1. PURE HEDGED ARBITRAGE: UP + DOWN < $1 (risk-free profit)")
    print(f"{'=' * 90}")

    arb_opps = []
    for mkt in markets:
        up_pts = {pt['t']: pt['p'] for pt in mkt.get('poly_points_up', [])}
        down_pts = {pt['t']: pt['p'] for pt in mkt.get('poly_points_down', [])}

        # Find overlapping timestamps (within 60s)
        for ut, up in up_pts.items():
            for dt, dn in down_pts.items():
                if abs(ut - dt) <= 120:  # Within 2 minutes
                    total = up + dn
                    if total < 1.0:
                        arb_opps.append({
                            'slug': mkt['slug'],
                            'up': up, 'down': dn,
                            'total': total,
                            'gap': 1.0 - total,
                            'outcome': mkt['gamma_outcome'],
                        })
                    break  # One match per up point

    if arb_opps:
        print(f"  Found {len(arb_opps)} hedged arb opportunities (UP + DOWN < $1)")
        gaps = [a['gap'] for a in arb_opps]
        print(f"  Average gap: {np.mean(gaps):.4f} (${np.mean(gaps):.4f} profit per $1 invested)")
        print(f"  Max gap: {max(gaps):.4f}")
        print(f"  Min gap: {min(gaps):.4f}")

        # P&L: buy $1 UP + $1 DOWN = $2 cost, one pays 1/price shares * $1
        total_profit = 0
        for a in arb_opps:
            # Buy $1 of UP, $1 of DOWN
            up_shares = 1.0 / a['up'] if a['up'] > 0 else 0
            down_shares = 1.0 / a['down'] if a['down'] > 0 else 0
            if a['outcome'] == 'UP':
                payout = up_shares * 1.0  # UP shares pay $1 each
            else:
                payout = down_shares * 1.0
            profit = payout - 2.0  # Cost was $2
            total_profit += profit

        print(f"  Total P&L (buying $1 each side): ${total_profit:+,.2f}")
        print(f"  Per-trade avg profit: ${total_profit / len(arb_opps):+.4f}")
    else:
        print(f"  NO hedged arb opportunities found (UP + DOWN always ≥ $1)")

    # Also check: UP + DOWN > $1 (overpriced, could short both if possible)
    over_opps = []
    for mkt in markets:
        up_pts = {pt['t']: pt['p'] for pt in mkt.get('poly_points_up', [])}
        down_pts = {pt['t']: pt['p'] for pt in mkt.get('poly_points_down', [])}
        for ut, up in up_pts.items():
            for dt, dn in down_pts.items():
                if abs(ut - dt) <= 120:
                    total = up + dn
                    over_opps.append(total)
                    break

    if over_opps:
        print(f"\n  UP + DOWN distribution ({len(over_opps)} paired snapshots):")
        print(f"    Mean: {np.mean(over_opps):.4f}")
        print(f"    Median: {np.median(over_opps):.4f}")
        print(f"    Min: {min(over_opps):.4f}")
        print(f"    Max: {max(over_opps):.4f}")
        print(f"    < $1.00: {sum(1 for x in over_opps if x < 1.0)} ({sum(1 for x in over_opps if x < 1.0)/len(over_opps)*100:.1f}%)")
        print(f"    = $1.00: {sum(1 for x in over_opps if x == 1.0)} ({sum(1 for x in over_opps if x == 1.0)/len(over_opps)*100:.1f}%)")
        print(f"    > $1.00: {sum(1 for x in over_opps if x > 1.0)} ({sum(1 for x in over_opps if x > 1.0)/len(over_opps)*100:.1f}%)")

        # Distribution buckets
        print(f"\n    {'Sum Range':>12}  {'Count':>6}  {'Pct':>6}")
        for lo, hi in [(0.90, 0.95), (0.95, 0.98), (0.98, 0.99), (0.99, 1.00),
                       (1.00, 1.01), (1.01, 1.02), (1.02, 1.05), (1.05, 1.10)]:
            ct = sum(1 for x in over_opps if lo <= x < hi)
            if ct > 0:
                print(f"    {lo:.2f}-{hi:.2f}  {ct:>6}  {ct/len(over_opps)*100:>5.1f}%")

    # ═══ 2. DIRECTIONAL ARBITRAGE: BS says underpriced → buy it ═══
    print(f"\n{'=' * 90}")
    print(f"  2. DIRECTIONAL ARBITRAGE: When Polymarket diverges from BS, bet on BS")
    print(f"{'=' * 90}")
    print(f"  Logic: If BS says UP=60% but Polymarket prices UP at 50%, buy UP")
    print(f"  (BS thinks it's underpriced → positive expected value)")

    # Group by divergence magnitude
    # Positive divergence = Poly > BS (Polymarket overprices UP → sell UP / buy DOWN)
    # Negative divergence = Poly < BS (Polymarket underprices UP → buy UP)

    div_buckets = defaultdict(lambda: {'bets': 0, 'wins': 0, 'pnl': 0.0})

    for snap in snapshots:
        div = snap['divergence']  # Poly - BS for UP token
        poly_up = snap['poly_up_price']
        outcome = snap['outcome']

        # Strategy: bet AGAINST Polymarket's mispricing
        if div < -0.02:
            # Polymarket underprices UP → BUY UP
            direction = 'UP'
            entry_price = poly_up
        elif div > 0.02:
            # Polymarket overprices UP → BUY DOWN
            direction = 'DOWN'
            entry_price = 1.0 - poly_up
        else:
            continue  # Divergence too small, skip

        if entry_price <= 0 or entry_price >= 1:
            continue

        won = (direction == outcome)
        shares = 1.0 / entry_price
        profit = (shares - 1.0) if won else -1.0  # Per $1 bet

        # Bucket by divergence magnitude
        abs_div = abs(div)
        if abs_div >= 0.20:
            bucket = '≥20¢'
        elif abs_div >= 0.15:
            bucket = '15-20¢'
        elif abs_div >= 0.10:
            bucket = '10-15¢'
        elif abs_div >= 0.05:
            bucket = '5-10¢'
        else:
            bucket = '2-5¢'

        div_buckets[bucket]['bets'] += 1
        if won:
            div_buckets[bucket]['wins'] += 1
        div_buckets[bucket]['pnl'] += profit

    print(f"\n  {'Divergence':>12}  {'Bets':>6}  {'Wins':>5}  {'Win Rate':>9}  {'P&L':>10}  {'$/trade':>8}")
    print(f"  {'─' * 60}")

    for bucket in ['2-5¢', '5-10¢', '10-15¢', '15-20¢', '≥20¢']:
        d = div_buckets[bucket]
        if d['bets'] == 0:
            continue
        wr = d['wins'] / d['bets']
        per_trade = d['pnl'] / d['bets']
        print(f"  {bucket:>12}  {d['bets']:>6}  {d['wins']:>5}  {wr:>8.1%}  ${d['pnl']:>+8,.0f}  ${per_trade:>+6.2f}")

    total_bets = sum(d['bets'] for d in div_buckets.values())
    total_wins = sum(d['wins'] for d in div_buckets.values())
    total_pnl = sum(d['pnl'] for d in div_buckets.values())
    if total_bets:
        print(f"  {'TOTAL':>12}  {total_bets:>6}  {total_wins:>5}  {total_wins/total_bets:>8.1%}  ${total_pnl:>+8,.0f}  ${total_pnl/total_bets:>+6.2f}")

    # ═══ 3. HYBRID DIRECTIONAL: BS + Binance minute-by-minute ═══
    print(f"\n{'=' * 90}")
    print(f"  3. HYBRID DIRECTIONAL: Minute-by-minute BS vs Gamma outcomes")
    print(f"     When BS says one side is ≥X% but Polymarket snapshot shows lower → buy it")
    print(f"{'=' * 90}")

    # For each market, check at each minute: what does BS say?
    # Then compare to Gamma outcome (ground truth)
    # This tells us: is BS systematically wrong in a profitable direction?

    bs_accuracy = defaultdict(lambda: {'correct': 0, 'total': 0})

    for mkt in markets:
        outcome = mkt['gamma_outcome']
        for mb in mkt.get('minute_bs', []):
            bs_up = mb['bs_up']
            bs_call = 'UP' if bs_up >= 0.5 else 'DOWN'
            correct = (bs_call == outcome)

            # Bucket by BS confidence
            confidence = max(bs_up, 1 - bs_up)
            if confidence >= 0.95:
                bucket = '≥95%'
            elif confidence >= 0.90:
                bucket = '90-95%'
            elif confidence >= 0.85:
                bucket = '85-90%'
            elif confidence >= 0.80:
                bucket = '80-85%'
            elif confidence >= 0.75:
                bucket = '75-80%'
            elif confidence >= 0.60:
                bucket = '60-75%'
            else:
                bucket = '50-60%'

            bs_accuracy[bucket]['total'] += 1
            if correct:
                bs_accuracy[bucket]['correct'] += 1

    print(f"\n  BS MODEL ACCURACY vs GAMMA OUTCOMES (all minutes, all markets):")
    print(f"  {'BS Confidence':>14}  {'Samples':>8}  {'Correct':>8}  {'Accuracy':>9}  {'Edge vs Naive':>14}")
    print(f"  {'─' * 60}")

    for bucket in ['50-60%', '60-75%', '75-80%', '80-85%', '85-90%', '90-95%', '≥95%']:
        d = bs_accuracy[bucket]
        if d['total'] == 0:
            continue
        acc = d['correct'] / d['total']
        # "Naive" = just using the confidence as win rate
        # Parse bucket midpoint for comparison
        if bucket == '≥95%':
            naive = 0.975
        elif bucket == '50-60%':
            naive = 0.55
        else:
            parts = bucket.replace('%', '').split('-')
            naive = (float(parts[0]) + float(parts[1])) / 200
        edge = acc - naive
        print(f"  {bucket:>14}  {d['total']:>8}  {d['correct']:>8}  {acc:>8.1%}  {edge:>+13.1%}")

    # ═══ 4. VOLUME-WEIGHTED ANALYSIS ═══
    print(f"\n{'=' * 90}")
    print(f"  4. DOES VOLUME MATTER? (High-volume markets may be more efficient)")
    print(f"{'=' * 90}")

    # Split markets by volume
    volumes = [mkt.get('volume', 0) for mkt in markets if mkt.get('volume')]
    if volumes:
        med_vol = np.median(volumes)
        print(f"  Median market volume: ${med_vol:,.0f}")

        for label, vol_filter in [('Low vol (< median)', lambda v: v < med_vol),
                                   ('High vol (≥ median)', lambda v: v >= med_vol)]:
            filtered = [mkt for mkt in markets if vol_filter(mkt.get('volume', 0))]
            if not filtered:
                continue

            # Check cheap token win rates
            cheap_wins = 0
            cheap_total = 0
            expensive_wins = 0
            expensive_total = 0

            for mkt in filtered:
                outcome = mkt['gamma_outcome']
                for mb in mkt.get('minute_bs', []):
                    if mb['secs_left'] != 300:
                        continue  # Only at 5 min remaining
                    bs_up = mb['bs_up']
                    bs_down = mb['bs_down']

                    # Cheap side
                    if bs_up <= 0.20:
                        cheap_total += 1
                        if outcome == 'UP':
                            cheap_wins += 1
                    elif bs_down <= 0.20:
                        cheap_total += 1
                        if outcome == 'DOWN':
                            cheap_wins += 1

                    # Expensive side
                    if bs_up >= 0.80:
                        expensive_total += 1
                        if outcome == 'UP':
                            expensive_wins += 1
                    elif bs_down >= 0.80:
                        expensive_total += 1
                        if outcome == 'DOWN':
                            expensive_wins += 1

            print(f"\n  {label} ({len(filtered)} markets):")
            if cheap_total:
                print(f"    ≤20¢ tokens: {cheap_wins}/{cheap_total} = {cheap_wins/cheap_total:.1%} WR")
            if expensive_total:
                print(f"    ≥80¢ tokens: {expensive_wins}/{expensive_total} = {expensive_wins/expensive_total:.1%} WR")

    print(f"\n  Data source: data/polymarket_validation_30d.json")


if __name__ == '__main__':
    main()
