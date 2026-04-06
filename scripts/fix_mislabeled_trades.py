#!/usr/bin/env python3
"""
Fix mislabeled 'expired_loss' trades in trade_history.json.

Root cause: deleted code (recover_unsettled_trades in order_lifecycle.py) assumed
any unsettled trade was a loss. Many were actually wins with positive CSV redeems.

This script:
1. Loads trade_history.json and identifies expired_loss records
2. Cross-references with CSV redeems to find which are actually wins
3. Verifies via Data API closed-positions (realizedPnl)
4. Corrects won/profit/status fields
5. Reports the impact on P&L and ML training
"""

import json
import csv
import re
import os
import sys
import requests
from datetime import datetime
from collections import defaultdict

# Paths
TRADE_HISTORY = os.path.join(os.path.dirname(__file__), '..', 'data', 'trade_history.json')
CSV_FILE = os.path.join(os.path.dirname(__file__), '..', 'Polymarket-History-2026-02-06 (2).csv')
DATA_API = "https://data-api.polymarket.com"
PROXY_ADDRESS = "0xYOUR_PROXY_WALLET_ADDRESS_HERE"


def load_trade_history():
    with open(TRADE_HISTORY, 'r') as f:
        return json.load(f)


def load_csv_redeems():
    """Parse CSV and build a map of market_name -> list of redeems."""
    redeems_by_market = defaultdict(list)
    buys_by_market = defaultdict(list)

    with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('marketName', '').strip()
            action = row.get('action', '').strip()
            amount = float(row.get('usdcAmount', 0) or 0)
            token_name = row.get('tokenName', '').strip()
            tx_hash = row.get('hash', '').strip()

            if action == 'Redeem' and amount > 0:
                redeems_by_market[name].append({
                    'amount': amount,
                    'token_name': token_name,
                    'tx_hash': tx_hash,
                })
            elif action == 'Buy':
                buys_by_market[name].append({
                    'amount': amount,
                    'token_name': token_name,
                    'tx_hash': tx_hash,
                })

    return redeems_by_market, buys_by_market


def fetch_closed_positions():
    """Fetch all closed positions from Data API."""
    all_positions = []
    offset = 0
    while True:
        try:
            resp = requests.get(f"{DATA_API}/closed-positions", params={
                'user': PROXY_ADDRESS,
                'limit': 50,
                'offset': offset,
            }, timeout=15)
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            all_positions.extend(batch)
            offset += len(batch)
            if len(batch) < 50:
                break
        except Exception as e:
            print(f"  Warning: Data API error: {e}")
            break
    return all_positions


def slug_to_market_time(slug):
    """Extract market open epoch from slug like 'btc-updown-15m-1770394500'."""
    try:
        return int(slug.split('-')[-1])
    except (ValueError, IndexError):
        return None


def match_trade_to_csv(trade, redeems_by_market):
    """Try to match a trade_history record to CSV redeems by market name patterns."""
    slug = trade.get('market_slug', '')
    coin = trade.get('coin', '').upper()

    # Extract epoch from slug
    epoch = slug_to_market_time(slug)
    if not epoch:
        return None

    # Convert epoch to human-readable parts for matching
    dt = datetime.fromtimestamp(epoch)
    month_day = dt.strftime('%B %-d')  # "February 3"
    # Time formats to try
    hour_12 = dt.strftime('%-I:%M%p').replace('AM', 'AM').replace('PM', 'PM')
    hour_12_upper = hour_12.upper()

    # Build end time (15 min later)
    end_dt = datetime.fromtimestamp(epoch + 900)
    end_hour_12 = end_dt.strftime('%-I:%M%p')

    # Coin name mapping
    coin_names = {'BTC': 'Bitcoin', 'ETH': 'Ethereum', 'SOL': 'Solana'}
    coin_name = coin_names.get(coin, coin)

    # Search through CSV market names
    for market_name, redeems in redeems_by_market.items():
        # Check if coin matches
        if coin_name.lower() not in market_name.lower() and coin not in market_name:
            continue

        # Check if it's an Up or Down market
        if 'up or down' not in market_name.lower():
            continue

        # Check date match
        if month_day not in market_name:
            continue

        # Check time match (flexible)
        # CSV format: "February 3, 11:00PM-11:15PM ET"
        time_match = re.search(r'(\d{1,2}:\d{2}[AP]M)\s*-\s*(\d{1,2}:\d{2}[AP]M)', market_name)
        if time_match:
            csv_start = time_match.group(1)
            # Compare start times
            # Normalize: remove leading zeros, uppercase
            norm_hour = hour_12_upper.lstrip('0') if hour_12_upper[0] == '0' else hour_12_upper
            norm_csv = csv_start.upper().lstrip('0') if csv_start.upper()[0] == '0' else csv_start.upper()
            if norm_hour == norm_csv:
                return {
                    'market_name': market_name,
                    'redeems': redeems,
                    'total_redeemed': sum(r['amount'] for r in redeems),
                }

    return None


def main():
    print("=" * 70)
    print("FIX MISLABELED 'expired_loss' TRADES")
    print("=" * 70)

    # Load data
    print("\n1. Loading trade history...")
    trades = load_trade_history()
    print(f"   Total records: {len(trades)}")

    expired_loss = [(i, t) for i, t in enumerate(trades) if t.get('recovered_via') == 'expired_loss']
    print(f"   Records with recovered_via='expired_loss': {len(expired_loss)}")

    print("\n2. Loading CSV redeems...")
    redeems_by_market, buys_by_market = load_csv_redeems()
    print(f"   Markets with positive redeems: {len(redeems_by_market)}")

    print("\n3. Fetching closed positions from Data API...")
    closed_positions = fetch_closed_positions()
    closed_by_cid = {}
    for cp in closed_positions:
        cid = cp.get('conditionId', '')
        if cid:
            closed_by_cid[cid] = cp
    print(f"   Closed positions fetched: {len(closed_by_cid)}")

    # Cross-reference
    print("\n4. Cross-referencing expired_loss trades...")
    print("-" * 70)

    corrections = []
    confirmed_losses = []
    unknown = []

    for idx, trade in expired_loss:
        coin = trade.get('coin', '?')
        pred = trade.get('prediction', '?')
        cost = trade.get('cost', 0)
        slug = trade.get('market_slug', '')
        cid = trade.get('condition_id', '')

        # Method 1: Check Data API realizedPnl
        api_result = None
        if cid and cid in closed_by_cid:
            cp = closed_by_cid[cid]
            rpnl = float(cp.get('realizedPnl', 0))
            api_result = {'realizedPnl': rpnl, 'won': rpnl > 0}

        # Method 2: Check CSV redeems
        csv_match = match_trade_to_csv(trade, redeems_by_market)

        # Determine true outcome
        if api_result and api_result['won']:
            # Data API says it's a win
            corrections.append({
                'idx': idx,
                'trade': trade,
                'source': 'data_api',
                'realizedPnl': api_result['realizedPnl'],
                'csv_match': csv_match,
            })
        elif csv_match and csv_match['total_redeemed'] > 0:
            # CSV shows positive redeem — it's a win
            corrections.append({
                'idx': idx,
                'trade': trade,
                'source': 'csv',
                'csv_match': csv_match,
                'realizedPnl': api_result['realizedPnl'] if api_result else None,
            })
        elif api_result and not api_result['won']:
            # Data API confirms it's a loss
            confirmed_losses.append({
                'idx': idx,
                'trade': trade,
                'realizedPnl': api_result['realizedPnl'],
            })
        else:
            unknown.append({
                'idx': idx,
                'trade': trade,
            })

    # Print results
    print(f"\n{'='*70}")
    print(f"RESULTS:")
    print(f"  Mislabeled as loss (actually WON): {len(corrections)}")
    print(f"  Confirmed real losses:             {len(confirmed_losses)}")
    print(f"  Unknown (no API/CSV match):        {len(unknown)}")
    print(f"{'='*70}")

    if corrections:
        print(f"\n--- TRADES TO CORRECT (were marked loss, actually won) ---\n")
        total_profit_recovered = 0
        total_wrong_loss = 0

        for c in corrections:
            t = c['trade']
            coin = t.get('coin', '?')
            pred = t.get('prediction', '?')
            cost = t.get('cost', 0)
            old_profit = t.get('profit', 0)
            slug = t.get('market_slug', '')

            if c.get('realizedPnl') and c['realizedPnl'] > 0:
                new_profit = c['realizedPnl']
            elif c.get('csv_match'):
                # Estimate from CSV: redeemed - cost
                new_profit = c['csv_match']['total_redeemed'] - cost
            else:
                new_profit = 0

            csv_info = ""
            if c.get('csv_match'):
                csv_info = f" | CSV redeem: ${c['csv_match']['total_redeemed']:.2f} ({c['csv_match']['market_name'][:50]}...)"

            total_profit_recovered += new_profit
            total_wrong_loss += abs(old_profit) if old_profit < 0 else 0

            print(f"  {coin} {pred} | cost=${cost:.2f} | old_profit=${old_profit:+.2f} -> new_profit=${new_profit:+.2f} "
                  f"| source={c['source']}{csv_info}")

        print(f"\n  TOTAL P&L IMPACT:")
        print(f"    Old (wrong) total profit from these trades: ${sum(c['trade'].get('profit', 0) for c in corrections):+.2f}")
        print(f"    New (correct) total profit:                 ${total_profit_recovered:+.2f}")
        print(f"    P&L SWING:                                  ${total_profit_recovered - sum(c['trade'].get('profit', 0) for c in corrections):+.2f}")

    if confirmed_losses:
        print(f"\n--- CONFIRMED LOSSES (correctly marked, but via wrong method) ---\n")
        for cl in confirmed_losses[:10]:
            t = cl['trade']
            print(f"  {t.get('coin','?')} {t.get('prediction','?')} | cost=${t.get('cost',0):.2f} | "
                  f"realizedPnl=${cl['realizedPnl']:+.4f}")
        if len(confirmed_losses) > 10:
            print(f"  ... and {len(confirmed_losses) - 10} more")

    if unknown:
        print(f"\n--- UNKNOWN (no API or CSV match) ---\n")
        for u in unknown[:5]:
            t = u['trade']
            print(f"  {t.get('coin','?')} {t.get('prediction','?')} | cost=${t.get('cost',0):.2f} | "
                  f"cid={t.get('condition_id','')[:20]}... | slug={t.get('market_slug','')}")
        if len(unknown) > 5:
            print(f"  ... and {len(unknown) - 5} more")

    # Apply fixes
    if corrections:
        print(f"\n{'='*70}")
        print(f"APPLYING CORRECTIONS to trade_history.json...")

        for c in corrections:
            idx = c['idx']

            if c.get('realizedPnl') and c['realizedPnl'] > 0:
                new_profit = c['realizedPnl']
            elif c.get('csv_match'):
                new_profit = c['csv_match']['total_redeemed'] - trades[idx].get('cost', 0)
            else:
                new_profit = 0

            old_profit = trades[idx].get('profit', 0)
            trades[idx]['won'] = True
            trades[idx]['profit'] = new_profit
            trades[idx]['status'] = 'settled'
            trades[idx]['recovered_via'] = 'csv_correction'
            trades[idx]['correction_note'] = (
                f"Was expired_loss (profit={old_profit:+.2f}), "
                f"corrected to won (profit={new_profit:+.2f}) via {c['source']}"
            )

        # Also fix confirmed_losses: keep won=False but update recovered_via
        for cl in confirmed_losses:
            idx = cl['idx']
            trades[idx]['recovered_via'] = 'expired_loss_confirmed'
            trades[idx]['profit'] = cl['realizedPnl']

        # Write backup
        backup_path = TRADE_HISTORY + '.bak.pre_correction'
        if not os.path.exists(backup_path):
            import shutil
            shutil.copy2(TRADE_HISTORY, backup_path)
            print(f"  Backup saved: {backup_path}")

        # Atomic write
        tmp_path = TRADE_HISTORY + '.tmp'
        with open(tmp_path, 'w') as f:
            json.dump(trades, f, indent=2)
        os.replace(tmp_path, TRADE_HISTORY)
        print(f"  trade_history.json updated with {len(corrections)} corrections")

    # Final summary
    print(f"\n{'='*70}")
    print("FINAL TRADE HISTORY SUMMARY")
    print(f"{'='*70}")

    total_trades = len(trades)
    won = [t for t in trades if t.get('won') is True]
    lost = [t for t in trades if t.get('won') is False]
    unsettled = [t for t in trades if t.get('won') is None]
    total_profit = sum(t.get('profit', 0) or 0 for t in trades if t.get('won') is not None)
    total_cost = sum(t.get('cost', 0) or 0 for t in trades)

    print(f"  Total trades:   {total_trades}")
    print(f"  Won:            {len(won)}")
    print(f"  Lost:           {len(lost)}")
    print(f"  Unsettled:      {len(unsettled)}")
    print(f"  Win rate:       {len(won)/(len(won)+len(lost))*100:.1f}%" if (len(won)+len(lost)) > 0 else "  Win rate: N/A")
    print(f"  Total cost:     ${total_cost:.2f}")
    print(f"  Total profit:   ${total_profit:+.2f}")
    print(f"  ROI:            {total_profit/total_cost*100:+.1f}%" if total_cost > 0 else "  ROI: N/A")

    # ML impact
    print(f"\n  ML IMPACT:")
    print(f"    {len(corrections)} training labels were WRONG (labeled DOWN should be UP)")
    print(f"    Replay buffer should be rebuilt after this correction")
    print(f"    Run: python -m src.bot (ML backfill will run at startup)")


if __name__ == '__main__':
    main()
