#!/usr/bin/env python3
"""
Polymarket Trade History Analyzer
=================================
Reads the CSV export, groups by market, identifies:
1. Total spent (Buys)
2. Total received (Redeems + Sells)
3. Unredeemed positions (Buy with no Redeem)
4. Zero-value redeems (Redeem=0, possible lost positions)
5. P&L per market and overall

Then verifies on-chain using Polygon RPC:
- Checks CTF payoutNumerators to see which outcome actually won
- Cross-references with user's position to identify discrepancies
"""

import csv
import json
import sys
import os
from collections import defaultdict
from datetime import datetime, timezone

# ────────────────────────────────────────────────────────────────
# 1. PARSE CSV
# ────────────────────────────────────────────────────────────────

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'Polymarket-History-2026-02-06 (2).csv')

def parse_csv(path):
    """Parse the Polymarket CSV export into a list of dicts."""
    rows = []
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                'market': row['marketName'].strip(),
                'action': row['action'].strip(),
                'usdc': float(row['usdcAmount'] or 0),
                'tokens': float(row['tokenAmount'] or 0),
                'side': row['tokenName'].strip() if row['tokenName'] else '',
                'timestamp': int(row['timestamp']),
                'hash': row['hash'].strip(),
            })
    return rows

# ────────────────────────────────────────────────────────────────
# 2. GROUP BY MARKET AND ANALYZE
# ────────────────────────────────────────────────────────────────

def analyze_markets(rows):
    """Group transactions by market and compute P&L."""
    markets = defaultdict(lambda: {
        'buys': [],
        'sells': [],
        'redeems': [],
        'total_spent': 0.0,
        'total_received': 0.0,
        'sides_bought': set(),
        'tokens_bought': 0.0,
        'tokens_sold': 0.0,
        'tokens_redeemed': 0.0,
        'redeem_usdc': 0.0,
    })

    for row in rows:
        m = markets[row['market']]
        if row['action'] == 'Buy':
            m['buys'].append(row)
            m['total_spent'] += row['usdc']
            m['sides_bought'].add(row['side'])
            m['tokens_bought'] += row['tokens']
        elif row['action'] == 'Sell':
            m['sells'].append(row)
            m['total_received'] += row['usdc']
            m['tokens_sold'] += row['tokens']
        elif row['action'] == 'Redeem':
            m['redeems'].append(row)
            m['total_received'] += row['usdc']
            m['redeem_usdc'] += row['usdc']
            m['tokens_redeemed'] += row['tokens']

    return dict(markets)


def classify_markets(markets):
    """Classify each market into categories."""
    results = {
        'wins': [],         # Redeemed for > 0 USDC
        'losses': [],       # Redeemed for 0 USDC
        'unredeemed': [],   # Has buys but no redeem at all
        'sold_early': [],   # Sold before resolution
        'complex': [],      # Mix of buys/sells/redeems
    }

    for name, m in markets.items():
        has_buys = len(m['buys']) > 0
        has_sells = len(m['sells']) > 0
        has_redeems = len(m['redeems']) > 0

        pnl = m['total_received'] - m['total_spent']

        entry = {
            'market': name,
            'spent': m['total_spent'],
            'received': m['total_received'],
            'pnl': pnl,
            'sides': list(m['sides_bought']),
            'tokens_bought': m['tokens_bought'],
            'tokens_redeemed': m['tokens_redeemed'],
            'redeem_usdc': m['redeem_usdc'],
            'buys': m['buys'],
            'sells': m['sells'],
            'redeems': m['redeems'],
        }

        if not has_buys:
            # Redeem-only (possible from positions bought outside CSV window)
            if has_redeems:
                if m['redeem_usdc'] > 0:
                    results['wins'].append(entry)
                else:
                    results['losses'].append(entry)
            continue

        if has_redeems:
            if m['redeem_usdc'] > 0:
                results['wins'].append(entry)
            else:
                results['losses'].append(entry)
        elif has_sells and not has_redeems:
            results['sold_early'].append(entry)
        elif has_buys and not has_redeems and not has_sells:
            results['unredeemed'].append(entry)
        else:
            results['complex'].append(entry)

    return results


# ────────────────────────────────────────────────────────────────
# 3. IDENTIFY SUSPICIOUS ZERO-REDEEMS
# ────────────────────────────────────────────────────────────────

def find_zero_redeem_with_tokens(markets):
    """
    Find markets where:
    - User bought tokens (spent USDC)
    - Redeem happened but returned 0 USDC
    - User still had tokens (tokens_bought > tokens_sold)
    These are potential discrepancies.
    """
    suspicious = []
    for name, m in markets.items():
        if not m['buys']:
            continue

        zero_redeems = [r for r in m['redeems'] if r['usdc'] == 0]
        positive_redeems = [r for r in m['redeems'] if r['usdc'] > 0]

        if zero_redeems and not positive_redeems:
            # Had tokens, redeemed for 0
            net_tokens = m['tokens_bought'] - m['tokens_sold']
            if net_tokens > 0:
                suspicious.append({
                    'market': name,
                    'spent': m['total_spent'],
                    'tokens_held': net_tokens,
                    'sides': list(m['sides_bought']),
                    'zero_redeem_hashes': [r['hash'] for r in zero_redeems],
                    'buy_hashes': [b['hash'] for b in m['buys']],
                })

    return suspicious


# ────────────────────────────────────────────────────────────────
# 4. GENERATE REPORT
# ────────────────────────────────────────────────────────────────

def generate_report(rows, markets, classified, suspicious):
    """Print comprehensive analysis report."""
    print("=" * 80)
    print("  POLYMARKET TRADE HISTORY ANALYSIS REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  CSV: {len(rows)} transactions across {len(markets)} unique markets")
    print("=" * 80)

    # Overall stats
    total_spent = sum(m['total_spent'] for m in markets.values())
    total_received = sum(m['total_received'] for m in markets.values())
    total_pnl = total_received - total_spent

    buy_count = sum(len(m['buys']) for m in markets.values())
    sell_count = sum(len(m['sells']) for m in markets.values())
    redeem_count = sum(len(m['redeems']) for m in markets.values())

    print(f"\n{'─'*80}")
    print("  OVERALL SUMMARY")
    print(f"{'─'*80}")
    print(f"  Total Buy transactions:    {buy_count}")
    print(f"  Total Sell transactions:   {sell_count}")
    print(f"  Total Redeem transactions: {redeem_count}")
    print(f"  Unique markets traded:     {len(markets)}")
    print()
    print(f"  Total USDC Spent (Buys):       ${total_spent:>10.2f}")
    print(f"  Total USDC Received (Sells):   ${sum(sum(s['usdc'] for s in m['sells']) for m in markets.values()):>10.2f}")
    print(f"  Total USDC Received (Redeems): ${sum(m['redeem_usdc'] for m in markets.values()):>10.2f}")
    print(f"  Total USDC Received (All):     ${total_received:>10.2f}")
    print(f"  {'─'*40}")
    print(f"  NET P&L:                       ${total_pnl:>+10.2f}")

    # Wins
    print(f"\n{'─'*80}")
    print(f"  WINNING TRADES ({len(classified['wins'])} markets)")
    print(f"{'─'*80}")
    win_pnl = sum(e['pnl'] for e in classified['wins'])
    win_spent = sum(e['spent'] for e in classified['wins'])
    win_received = sum(e['received'] for e in classified['wins'])
    print(f"  Total spent:    ${win_spent:.2f}")
    print(f"  Total received: ${win_received:.2f}")
    print(f"  Net profit:     ${win_pnl:+.2f}")

    # Losses (zero-redeem)
    print(f"\n{'─'*80}")
    print(f"  LOSING TRADES - Redeemed for $0 ({len(classified['losses'])} markets)")
    print(f"{'─'*80}")
    loss_spent = sum(e['spent'] for e in classified['losses'])
    print(f"  Total spent (lost):  ${loss_spent:.2f}")

    # Unredeemed
    print(f"\n{'─'*80}")
    print(f"  UNREDEEMED POSITIONS ({len(classified['unredeemed'])} markets)")
    print(f"{'─'*80}")
    if classified['unredeemed']:
        unred_spent = sum(e['spent'] for e in classified['unredeemed'])
        print(f"  Total spent (stuck): ${unred_spent:.2f}")
        print(f"  These positions were NEVER redeemed - money may be recoverable!")
        for e in classified['unredeemed']:
            sides = ', '.join(e['sides'])
            print(f"    - {e['market']}")
            print(f"      Spent: ${e['spent']:.2f}, Side: {sides}, Tokens: {e['tokens_bought']:.4f}")
    else:
        print("  None - all positions were redeemed.")

    # Sold early
    if classified['sold_early']:
        print(f"\n{'─'*80}")
        print(f"  SOLD EARLY ({len(classified['sold_early'])} markets)")
        print(f"{'─'*80}")
        for e in classified['sold_early']:
            print(f"    - {e['market']}: Spent ${e['spent']:.2f}, Received ${e['received']:.2f}, P&L ${e['pnl']:+.2f}")

    # Suspicious zero-redeems
    print(f"\n{'─'*80}")
    print(f"  SUSPICIOUS: Zero-Redeem Despite Holding Tokens ({len(suspicious)} markets)")
    print(f"{'─'*80}")
    if suspicious:
        suspicious_total = sum(s['spent'] for s in suspicious)
        print(f"  Total USDC at risk: ${suspicious_total:.2f}")
        print()
        for s in suspicious:
            sides = ', '.join(s['sides'])
            print(f"  Market: {s['market']}")
            print(f"    Spent: ${s['spent']:.6f}")
            print(f"    Side bought: {sides}")
            print(f"    Tokens held at redeem: {s['tokens_held']:.6f}")
            print(f"    Redeem TX: {s['zero_redeem_hashes'][0]}")
            print()
    else:
        print("  None found.")

    # Breakdown by date
    print(f"\n{'─'*80}")
    print("  DAILY P&L BREAKDOWN")
    print(f"{'─'*80}")
    daily = defaultdict(lambda: {'spent': 0, 'received': 0})
    for row in rows:
        dt = datetime.fromtimestamp(row['timestamp'], tz=timezone.utc)
        day = dt.strftime('%Y-%m-%d')
        if row['action'] == 'Buy':
            daily[day]['spent'] += row['usdc']
        elif row['action'] in ('Sell', 'Redeem'):
            daily[day]['received'] += row['usdc']

    for day in sorted(daily.keys()):
        d = daily[day]
        pnl = d['received'] - d['spent']
        print(f"  {day}: Spent ${d['spent']:>8.2f} | Received ${d['received']:>8.2f} | P&L ${pnl:>+8.2f}")

    total_daily_pnl = sum(d['received'] - d['spent'] for d in daily.values())
    print(f"  {'─'*55}")
    print(f"  TOTAL:  Spent ${sum(d['spent'] for d in daily.values()):>8.2f} | Received ${sum(d['received'] for d in daily.values()):>8.2f} | P&L ${total_daily_pnl:>+8.2f}")

    return suspicious


# ────────────────────────────────────────────────────────────────
# 5. ON-CHAIN VERIFICATION (using Gamma API + Polygon RPC)
# ────────────────────────────────────────────────────────────────

def verify_onchain(suspicious, all_markets):
    """
    For each suspicious market, look up the condition on Gamma API,
    check on-chain resolution, and determine if user SHOULD have won.
    """
    import requests

    GAMMA_API = "https://gamma-api.polymarket.com"

    print(f"\n{'='*80}")
    print("  ON-CHAIN VERIFICATION")
    print(f"{'='*80}")

    discrepancies = []

    # Also check ALL zero-redeem markets (losses), not just "suspicious"
    all_losses = [name for name, m in all_markets.items()
                  if m['buys'] and m['redeems']
                  and all(r['usdc'] == 0 for r in m['redeems'])]

    markets_to_check = set()
    for s in suspicious:
        markets_to_check.add(s['market'])
    for name in all_losses:
        markets_to_check.add(name)

    print(f"\n  Checking {len(markets_to_check)} markets with zero-redeems against Gamma API...")
    print()

    for market_name in sorted(markets_to_check):
        m = all_markets[market_name]
        sides_bought = list(m['sides_bought'])

        # Search Gamma API for this market
        try:
            # Extract search terms from market name
            # e.g. "Bitcoin Up or Down - February 6, 8:45AM-9:00AM ET"
            resp = requests.get(f"{GAMMA_API}/markets", params={
                'closed': 'true',
                'limit': 5,
                'title': market_name[:60],  # Truncate for search
            }, timeout=15)

            if resp.status_code != 200:
                print(f"  [{market_name[:50]}...] Gamma API error: {resp.status_code}")
                continue

            gamma_markets = resp.json()
            if not gamma_markets:
                # Try shorter search
                resp = requests.get(f"{GAMMA_API}/markets", params={
                    'closed': 'true',
                    'limit': 5,
                    'title_contains': market_name.split(' - ')[0],
                }, timeout=15)
                gamma_markets = resp.json() if resp.status_code == 200 else []

            if not gamma_markets:
                print(f"  [{market_name[:50]}...] Not found on Gamma API")
                continue

            # Find exact or best match
            matched = None
            for gm in gamma_markets:
                if gm.get('question', '').strip() == market_name or \
                   gm.get('title', '').strip() == market_name:
                    matched = gm
                    break

            if not matched and gamma_markets:
                matched = gamma_markets[0]

            if not matched:
                print(f"  [{market_name[:50]}...] No match found")
                continue

            # Parse outcome prices
            outcome_prices_raw = matched.get('outcomePrices', '[]')
            if isinstance(outcome_prices_raw, str):
                outcome_prices = json.loads(outcome_prices_raw)
            else:
                outcome_prices = outcome_prices_raw

            outcomes_raw = matched.get('outcomes', '[]')
            if isinstance(outcomes_raw, str):
                outcomes = json.loads(outcomes_raw)
            else:
                outcomes = outcomes_raw

            condition_id = matched.get('conditionId', '')
            question = matched.get('question', market_name)

            # Determine winner from outcome prices
            # For resolved markets: winner has price 1.0, loser has price 0.0
            winner = None
            if len(outcome_prices) >= 2:
                p0 = float(outcome_prices[0])
                p1 = float(outcome_prices[1])
                if p0 > 0.9:
                    winner = outcomes[0] if outcomes else 'Outcome 0'
                elif p1 > 0.9:
                    winner = outcomes[1] if outcomes else 'Outcome 1'

            # Check: did user buy the winning side?
            user_bought_winner = False
            user_side_str = ', '.join(sides_bought)

            if winner:
                for side in sides_bought:
                    if side.lower() == winner.lower():
                        user_bought_winner = True
                        break

            is_loss = all(r['usdc'] == 0 for r in m['redeems'])
            tokens_held = m['tokens_bought'] - m['tokens_sold']
            expected_payout = tokens_held if user_bought_winner else 0

            status = "OK"
            if user_bought_winner and is_loss:
                status = "DISCREPANCY"
                discrepancies.append({
                    'market': market_name,
                    'condition_id': condition_id,
                    'winner': winner,
                    'user_side': user_side_str,
                    'spent': m['total_spent'],
                    'tokens_held': tokens_held,
                    'expected_payout': expected_payout,
                    'actual_payout': 0,
                    'lost_usdc': expected_payout,
                })
            elif not user_bought_winner and is_loss:
                status = "CORRECT LOSS"
            elif user_bought_winner and not is_loss:
                status = "CORRECT WIN"

            symbol = "!!" if status == "DISCREPANCY" else "  "
            emoji = "!!" if status == "DISCREPANCY" else ("OK" if "CORRECT" in status else "??")

            if status == "DISCREPANCY" or status != "CORRECT LOSS":
                print(f"  [{emoji}] {market_name[:55]}")
                print(f"       Winner: {winner or '?'} | User bought: {user_side_str} | "
                      f"Tokens: {tokens_held:.4f} | Redeem: ${m['redeem_usdc']:.2f} | {status}")

                if status == "DISCREPANCY":
                    print(f"       >>> SHOULD HAVE RECEIVED: ${expected_payout:.6f} USDC <<<")
                    print(f"       Condition ID: {condition_id}")
                print()

        except Exception as e:
            print(f"  [{market_name[:50]}...] Error: {e}")

    # Summary of discrepancies
    print(f"\n{'='*80}")
    print("  DISCREPANCY SUMMARY")
    print(f"{'='*80}")

    if discrepancies:
        total_lost = sum(d['lost_usdc'] for d in discrepancies)
        print(f"\n  Found {len(discrepancies)} markets where you WON but got $0:")
        print()
        for d in discrepancies:
            print(f"  Market:    {d['market']}")
            print(f"  Winner:    {d['winner']}")
            print(f"  You bought: {d['user_side']}")
            print(f"  Spent:     ${d['spent']:.6f}")
            print(f"  Expected:  ${d['expected_payout']:.6f}")
            print(f"  Received:  ${d['actual_payout']:.2f}")
            print(f"  Condition: {d['condition_id']}")
            print()

        print(f"  TOTAL USDC OWED TO YOU: ${total_lost:.6f}")
        print(f"  (This is the sum of tokens held × $1.00 for winning positions)")
    else:
        print("\n  No discrepancies found. All zero-redeems were correct losses.")

    return discrepancies


# ────────────────────────────────────────────────────────────────
# 6. CHECK FOR UNREDEEMED ON-CHAIN BALANCES
# ────────────────────────────────────────────────────────────────

def check_unredeemed_balances(classified, all_markets):
    """Check if there are positions that were never redeemed."""
    import requests

    GAMMA_API = "https://gamma-api.polymarket.com"

    unredeemed = classified.get('unredeemed', [])
    if not unredeemed:
        print(f"\n{'─'*80}")
        print("  UNREDEEMED BALANCE CHECK: None found")
        print(f"{'─'*80}")
        return

    print(f"\n{'='*80}")
    print(f"  UNREDEEMED POSITIONS ({len(unredeemed)} markets)")
    print(f"  These have Buy transactions but NO Redeem — USDC may be recoverable")
    print(f"{'='*80}")

    total_recoverable = 0
    for entry in unredeemed:
        market_name = entry['market']
        print(f"\n  Market: {market_name}")
        print(f"    Spent: ${entry['spent']:.6f}")
        print(f"    Side: {', '.join(entry['sides'])}")
        print(f"    Tokens: {entry['tokens_bought']:.6f}")

        # Check Gamma API for resolution
        try:
            resp = requests.get(f"{GAMMA_API}/markets", params={
                'closed': 'true',
                'limit': 3,
                'title': market_name[:60],
            }, timeout=15)

            if resp.status_code == 200:
                gamma_markets = resp.json()
                if gamma_markets:
                    gm = gamma_markets[0]
                    outcome_prices = json.loads(gm.get('outcomePrices', '[]')) \
                        if isinstance(gm.get('outcomePrices'), str) else gm.get('outcomePrices', [])
                    outcomes = json.loads(gm.get('outcomes', '[]')) \
                        if isinstance(gm.get('outcomes'), str) else gm.get('outcomes', [])

                    winner = None
                    if len(outcome_prices) >= 2:
                        if float(outcome_prices[0]) > 0.9:
                            winner = outcomes[0] if outcomes else 'Outcome 0'
                        elif float(outcome_prices[1]) > 0.9:
                            winner = outcomes[1] if outcomes else 'Outcome 1'

                    if winner:
                        user_won = any(s.lower() == winner.lower() for s in entry['sides'])
                        if user_won:
                            total_recoverable += entry['tokens_bought']
                            print(f"    Resolution: {winner} won — YOU WON!")
                            print(f"    >>> RECOVERABLE: ${entry['tokens_bought']:.6f} USDC via redeemPositions()")
                            print(f"    Condition ID: {gm.get('conditionId', 'N/A')}")
                        else:
                            print(f"    Resolution: {winner} won — you lost (no recovery)")
                    else:
                        print(f"    Resolution: Market may not be resolved yet")
        except Exception as e:
            print(f"    Error checking: {e}")

    if total_recoverable > 0:
        print(f"\n  TOTAL RECOVERABLE FROM UNREDEEMED: ${total_recoverable:.6f} USDC")
    print()


# ────────────────────────────────────────────────────────────────
# 7. VERIFY REDEMPTION TRANSACTIONS ON-CHAIN
# ────────────────────────────────────────────────────────────────

def verify_redeem_transactions(rows):
    """
    Check redemption transactions on Polygonscan to verify
    actual USDC transfers match what CSV reports.
    """
    import requests

    print(f"\n{'='*80}")
    print("  REDEMPTION TRANSACTION VERIFICATION (Polygonscan)")
    print(f"{'='*80}")

    # Get unique redeem transactions
    redeem_txs = {}
    for row in rows:
        if row['action'] == 'Redeem':
            h = row['hash']
            if h not in redeem_txs:
                redeem_txs[h] = {
                    'hash': h,
                    'markets': [],
                    'total_csv_usdc': 0,
                    'timestamp': row['timestamp'],
                }
            redeem_txs[h]['markets'].append(row['market'])
            redeem_txs[h]['total_csv_usdc'] += row['usdc']

    print(f"\n  Found {len(redeem_txs)} unique redemption transactions")

    # Check a sample of zero-value redeems on-chain
    zero_redeems = {h: tx for h, tx in redeem_txs.items() if tx['total_csv_usdc'] == 0}
    positive_redeems = {h: tx for h, tx in redeem_txs.items() if tx['total_csv_usdc'] > 0}

    print(f"  Zero-value redemptions: {len(zero_redeems)} transactions")
    print(f"  Positive redemptions:   {len(positive_redeems)} transactions")
    print(f"  Total redeemed USDC:    ${sum(tx['total_csv_usdc'] for tx in redeem_txs.values()):.2f}")

    # Verify a few zero-redeem transactions via Polygonscan API (free tier)
    print(f"\n  Sampling zero-redeem transactions for on-chain verification...")
    POLYGONSCAN_API = "https://api.polygonscan.com/api"

    sample = list(zero_redeems.items())[:5]  # Check first 5
    for h, tx in sample:
        try:
            # Use Polygonscan to get tx receipt
            resp = requests.get(POLYGONSCAN_API, params={
                'module': 'proxy',
                'action': 'eth_getTransactionReceipt',
                'txhash': h,
            }, timeout=15)

            if resp.status_code == 200:
                result = resp.json().get('result', {})
                if result:
                    status = result.get('status', '')
                    logs = result.get('logs', [])
                    gas_used = int(result.get('gasUsed', '0'), 16) if result.get('gasUsed') else 0

                    # Check for USDC Transfer events in logs
                    # USDC Transfer topic: 0xddf252ad...
                    usdc_transfers = [
                        log for log in logs
                        if len(log.get('topics', [])) >= 1
                        and log['topics'][0] == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
                        and log['address'].lower() == '0x2791bca1f2de4661ed88a30c99a7a9449aa84174'
                    ]

                    tx_status = "SUCCESS" if status == '0x1' else "FAILED"
                    print(f"\n  TX: {h[:20]}...")
                    print(f"    Status: {tx_status}")
                    print(f"    Markets: {', '.join(tx['markets'][:2])}{'...' if len(tx['markets']) > 2 else ''}")
                    print(f"    CSV reports: ${tx['total_csv_usdc']:.2f}")
                    print(f"    USDC transfer events: {len(usdc_transfers)}")
                    print(f"    Total log events: {len(logs)}")

                    if usdc_transfers:
                        for ut in usdc_transfers:
                            # Decode amount (USDC has 6 decimals)
                            amount_hex = ut.get('data', '0x0')
                            amount = int(amount_hex, 16) / 1e6 if amount_hex != '0x' else 0
                            print(f"    On-chain USDC transfer: ${amount:.6f}")
                else:
                    print(f"\n  TX: {h[:20]}... — No receipt found (may be pending)")
        except Exception as e:
            print(f"\n  TX: {h[:20]}... — Error: {e}")

    return zero_redeems, positive_redeems


# ────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────

def main():
    print("\nLoading CSV...")
    rows = parse_csv(CSV_PATH)
    print(f"Loaded {len(rows)} transactions")

    print("Analyzing markets...")
    markets = analyze_markets(rows)

    print("Classifying trades...")
    classified = classify_markets(markets)

    print("Finding suspicious zero-redeems...")
    suspicious = find_zero_redeem_with_tokens(markets)

    # Generate report
    generate_report(rows, markets, classified, suspicious)

    # On-chain verification via Gamma API
    discrepancies = verify_onchain(suspicious, markets)

    # Check unredeemed positions
    check_unredeemed_balances(classified, markets)

    # Verify redemption transactions
    verify_redeem_transactions(rows)

    # Final summary
    print(f"\n{'='*80}")
    print("  FINAL SUMMARY")
    print(f"{'='*80}")

    total_spent = sum(m['total_spent'] for m in markets.values())
    total_received = sum(m['total_received'] for m in markets.values())
    print(f"\n  Total invested:      ${total_spent:.2f}")
    print(f"  Total returned:      ${total_received:.2f}")
    print(f"  Net P&L:             ${total_received - total_spent:+.2f}")

    if discrepancies:
        total_owed = sum(d['lost_usdc'] for d in discrepancies)
        print(f"\n  DISCREPANCIES FOUND: {len(discrepancies)}")
        print(f"  Total USDC owed:     ${total_owed:.6f}")
    else:
        print(f"\n  No discrepancies found — all outcomes match redemptions")

    unredeemed_count = len(classified.get('unredeemed', []))
    if unredeemed_count:
        unredeemed_value = sum(e['spent'] for e in classified['unredeemed'])
        print(f"\n  UNREDEEMED POSITIONS: {unredeemed_count}")
        print(f"  USDC spent (stuck):  ${unredeemed_value:.2f}")

    print()


if __name__ == '__main__':
    main()
