#!/usr/bin/env python3
"""
On-Chain Settlement Verification

Verifies trade outcomes directly against the CTF (Conditional Token Framework)
smart contract on Polygon. This is the ultimate source of truth — the contract's
payoutDenominator() and payoutNumerators() functions tell us exactly how a market
resolved, independent of any API.

Uses JSON-RPC batch requests for fast verification (~30s for 300 trades).

Usage:
    # Verify all trades in trade_history.json
    python scripts/verify_onchain.py

    # Verify and fix any discrepancies (updates trade_history.json + ML)
    python scripts/verify_onchain.py --fix

    # Verify a single condition_id
    python scripts/verify_onchain.py --condition-id 0xabc123...

    # Verbose mode (show every trade)
    python scripts/verify_onchain.py --verbose
"""

import os
import sys
import json
import argparse
import time
import requests as http_requests
from typing import Optional, List

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# --- Constants ---
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
# publicnode supports JSON-RPC batch calls (polygon-rpc.com does not)
RPC_URL = os.getenv("POLYGON_RPC_URL", "https://polygon-bor-rpc.publicnode.com")
TRADE_HISTORY = os.path.join(os.path.dirname(__file__), '..', 'data', 'trade_history.json')

# Function selectors (keccak256 of function signature, first 4 bytes)
# payoutDenominator(bytes32) = 0xdd34de67
# payoutNumerators(bytes32,uint256) = 0x0504c814
SEL_PAYOUT_DENOM = "dd34de67"
SEL_PAYOUT_NUMER = "0504c814"


def cid_to_bytes32_hex(condition_id: str) -> str:
    """Convert condition_id to 64-char hex string (no 0x prefix), zero-padded."""
    cid_hex = condition_id[2:] if condition_id.startswith('0x') else condition_id
    return cid_hex.zfill(64)


def encode_payout_denominator(cid_hex: str) -> str:
    """Encode payoutDenominator(bytes32) call data."""
    return "0x" + SEL_PAYOUT_DENOM + cid_hex


def encode_payout_numerators(cid_hex: str, index: int) -> str:
    """Encode payoutNumerators(bytes32,uint256) call data."""
    return "0x" + SEL_PAYOUT_NUMER + cid_hex + hex(index)[2:].zfill(64)


def batch_rpc_call(calls: list, max_retries: int = 3) -> list:
    """
    Send a batch of eth_call requests in a single HTTP request.

    Args:
        calls: list of (call_data_hex, label) tuples
        max_retries: retry count for rate limits

    Returns:
        list of (result_hex_or_None, label) tuples
    """
    batch = []
    for i, (data, label) in enumerate(calls):
        batch.append({
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": CTF_ADDRESS, "data": data}, "latest"],
            "id": i
        })

    for attempt in range(max_retries):
        try:
            resp = http_requests.post(RPC_URL, json=batch, timeout=30)
            if resp.status_code == 429:
                time.sleep(2 ** attempt + 1)
                continue
            results_raw = resp.json()
            break
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt + 1)
                continue
            return [(None, label) for _, label in calls]
    else:
        return [(None, label) for _, label in calls]

    # Parse responses — may be list or single error
    if isinstance(results_raw, dict) and 'error' in results_raw:
        err_msg = results_raw['error'].get('message', str(results_raw['error']))
        if 'rate limit' in err_msg.lower():
            # Retry once more after longer wait
            time.sleep(5)
            try:
                resp = http_requests.post(RPC_URL, json=batch, timeout=30)
                results_raw = resp.json()
                if isinstance(results_raw, dict) and 'error' in results_raw:
                    return [(None, label) for _, label in calls]
            except Exception:
                return [(None, label) for _, label in calls]
        else:
            return [(None, label) for _, label in calls]

    # Index results by id
    results_by_id = {}
    if isinstance(results_raw, list):
        for r in results_raw:
            rid = r.get('id', -1)
            if 'result' in r:
                results_by_id[rid] = r['result']
            else:
                results_by_id[rid] = None

    output = []
    for i, (data, label) in enumerate(calls):
        hex_val = results_by_id.get(i)
        output.append((hex_val, label))
    return output


def decode_uint256(hex_val: str) -> Optional[int]:
    """Decode a uint256 from hex RPC response."""
    if not hex_val or hex_val == '0x':
        return None
    try:
        return int(hex_val, 16)
    except (ValueError, TypeError):
        return None


def verify_conditions_batch(condition_ids: list) -> dict:
    """
    Verify a batch of condition_ids using batched RPC calls.

    Returns: {condition_id: {'resolved': bool, 'winner': str|None, 'payout_numerators': list}}
    """
    results = {}

    if not condition_ids:
        return results

    # Step 1: Batch payoutDenominator for all conditions
    denom_calls = []
    for cid in condition_ids:
        cid_hex = cid_to_bytes32_hex(cid)
        data = encode_payout_denominator(cid_hex)
        denom_calls.append((data, cid))

    denom_results = batch_rpc_call(denom_calls)

    # Step 2: For resolved conditions, batch payoutNumerators(cid, 0) and (cid, 1)
    resolved_cids = []
    for hex_val, cid in denom_results:
        denom = decode_uint256(hex_val)
        if denom is not None and denom > 0:
            resolved_cids.append(cid)
            results[cid] = {'resolved': True, 'payout_denominator': denom}
        elif denom == 0:
            results[cid] = {'resolved': False, 'winner': None, 'payout_numerators': []}
        else:
            results[cid] = {'resolved': False, 'winner': None, 'payout_numerators': [], 'error': True}

    if resolved_cids:
        numer_calls = []
        for cid in resolved_cids:
            cid_hex = cid_to_bytes32_hex(cid)
            numer_calls.append((encode_payout_numerators(cid_hex, 0), (cid, 0)))  # Up
            numer_calls.append((encode_payout_numerators(cid_hex, 1), (cid, 1)))  # Down

        numer_results = batch_rpc_call(numer_calls)

        # Collect numerators per cid
        numerators_map = {}  # cid -> {0: val, 1: val}
        for hex_val, (cid, idx) in numer_results:
            if cid not in numerators_map:
                numerators_map[cid] = {}
            numerators_map[cid][idx] = decode_uint256(hex_val) or 0

        # Determine winners
        for cid in resolved_cids:
            nums = numerators_map.get(cid, {})
            num_up = nums.get(0, 0)
            num_down = nums.get(1, 0)
            results[cid]['payout_numerators'] = [num_up, num_down]

            if num_up > 0 and num_down == 0:
                results[cid]['winner'] = 'UP'
            elif num_down > 0 and num_up == 0:
                results[cid]['winner'] = 'DOWN'
            elif num_up > 0 and num_down > 0:
                results[cid]['winner'] = 'SPLIT'
            else:
                results[cid]['winner'] = None

    return results


def load_trade_history():
    """Load trade_history.json safely."""
    try:
        with open(TRADE_HISTORY, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {TRADE_HISTORY} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {TRADE_HISTORY}: {e}")
        sys.exit(1)


def verify_single(condition_id: str):
    """Verify and print a single condition's on-chain state."""
    print(f"\nCondition: {condition_id}")
    results = verify_conditions_batch([condition_id])
    r = results.get(condition_id, {})

    if r.get('error'):
        print(f"  ERROR: RPC call failed")
        return

    if not r.get('resolved'):
        print(f"  Status: NOT RESOLVED (payoutDenominator=0)")
        return

    print(f"  Status: RESOLVED")
    print(f"  Payout Denominator: {r.get('payout_denominator', '?')}")
    print(f"  Payout Numerators: {r.get('payout_numerators', [])}")
    print(f"  Winner: {r.get('winner', '?')}")


def verify_all(trades: list, verbose: bool = False):
    """
    Verify all trades against on-chain data using batched RPC.

    Returns stats dict.
    """
    stats = {
        'total': len(trades),
        'verified_correct': 0,
        'discrepancies': [],
        'unresolved_onchain': 0,
        'no_condition_id': 0,
        'errors': 0,
        'skipped_unsettled': 0
    }

    # Group trades by condition_id
    cid_to_trades = {}
    for i, trade in enumerate(trades):
        cid = trade.get('condition_id', '')
        if not cid:
            stats['no_condition_id'] += 1
            continue
        if cid not in cid_to_trades:
            cid_to_trades[cid] = []
        cid_to_trades[cid].append((i, trade))

    all_cids = list(cid_to_trades.keys())
    total_cids = len(all_cids)
    print(f"\nVerifying {total_cids} unique conditions ({stats['total']} trades)...")
    print(f"  (Trades without condition_id: {stats['no_condition_id']})")

    # Process in batches of 20 conditions (20 denom calls + up to 40 numer calls per batch)
    BATCH_SIZE = 20
    start_time = time.time()

    for batch_start in range(0, total_cids, BATCH_SIZE):
        batch_cids = all_cids[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (total_cids + BATCH_SIZE - 1) // BATCH_SIZE

        # Rate limit between batches
        if batch_start > 0:
            time.sleep(2)

        elapsed = time.time() - start_time
        print(f"  Batch {batch_num}/{total_batches} ({batch_start + len(batch_cids)}/{total_cids} conditions, {elapsed:.0f}s)")

        # Batch verify
        onchain_results = verify_conditions_batch(batch_cids)

        # Process results
        for cid in batch_cids:
            onchain = onchain_results.get(cid, {})

            if onchain.get('error'):
                stats['errors'] += len(cid_to_trades[cid])
                if verbose:
                    print(f"    ERROR {cid[:16]}...: RPC call failed")
                continue

            if not onchain.get('resolved'):
                stats['unresolved_onchain'] += len(cid_to_trades[cid])
                if verbose:
                    coins = [t.get('coin', '?') for _, t in cid_to_trades[cid]]
                    print(f"    UNRESOLVED {cid[:16]}...: {', '.join(coins)}")
                continue

            onchain_winner = onchain.get('winner')

            for idx, trade in cid_to_trades[cid]:
                recorded_won = trade.get('won')
                prediction = trade.get('prediction', '').upper()

                if recorded_won is None:
                    stats['skipped_unsettled'] += 1
                    continue

                if onchain_winner == 'SPLIT':
                    if verbose:
                        print(f"    SPLIT {cid[:16]}...: Market voided")
                    continue

                if not onchain_winner:
                    stats['errors'] += 1
                    continue

                should_have_won = (prediction == onchain_winner)

                if should_have_won == recorded_won:
                    stats['verified_correct'] += 1
                    if verbose:
                        coin = trade.get('coin', '?')
                        status = 'WON' if recorded_won else 'LOST'
                        print(f"    OK {coin} {prediction} -> {status} (on-chain: {onchain_winner})")
                else:
                    disc = {
                        'idx': idx,
                        'condition_id': cid,
                        'coin': trade.get('coin', '?'),
                        'prediction': prediction,
                        'recorded_won': recorded_won,
                        'should_have_won': should_have_won,
                        'onchain_winner': onchain_winner,
                        'cost': trade.get('cost', 0),
                        'shares': trade.get('shares', 0),
                        'profit': trade.get('profit', 0),
                        'market_slug': trade.get('market_slug', ''),
                        'payout_numerators': onchain.get('payout_numerators', [])
                    }
                    stats['discrepancies'].append(disc)
                    print(f"    *** DISCREPANCY: {disc['coin']} {prediction} "
                          f"recorded={'WON' if recorded_won else 'LOST'} "
                          f"but on-chain says {onchain_winner} "
                          f"-> should be {'WON' if should_have_won else 'LOST'}")

    return stats


def apply_fixes(trades: list, discrepancies: list) -> int:
    """Fix discrepancies in trade_history.json and save."""
    if not discrepancies:
        return 0

    from src.core.persistence import atomic_json_write

    backup_path = TRADE_HISTORY + '.bak.pre_onchain_verify'
    if not os.path.exists(backup_path):
        import shutil
        shutil.copy2(TRADE_HISTORY, backup_path)
        print(f"  Backup saved: {backup_path}")

    fixed = 0
    for disc in discrepancies:
        idx = disc['idx']
        old_won = trades[idx].get('won')
        old_profit = trades[idx].get('profit', 0)

        trades[idx]['won'] = disc['should_have_won']

        cost = trades[idx].get('cost', 0)
        shares = trades[idx].get('shares', 0)
        if disc['should_have_won']:
            trades[idx]['profit'] = round(shares - cost, 6)
        else:
            trades[idx]['profit'] = round(-cost, 6)

        trades[idx]['onchain_verified'] = True
        trades[idx]['onchain_correction'] = (
            f"Was won={old_won} (profit={old_profit:+.2f}), "
            f"corrected to won={disc['should_have_won']} "
            f"(profit={trades[idx]['profit']:+.2f}) "
            f"via on-chain payoutNumerators={disc['payout_numerators']}"
        )
        fixed += 1

    atomic_json_write(TRADE_HISTORY, trades)
    return fixed


def backfill_ml(trades: list, discrepancies: list) -> int:
    """Retrain ML with corrected labels from on-chain verification."""
    if not discrepancies:
        return 0

    try:
        from src.ml.learning import ContinuousLearningEngine
        engine = ContinuousLearningEngine({})

        affected = 0
        for disc in discrepancies:
            old_label = 1 if disc['prediction'] == 'UP' and disc['recorded_won'] else 0
            new_label = 1 if disc['onchain_winner'] == 'UP' else 0
            if old_label != new_label:
                affected += 1

        if affected > 0:
            print(f"\n  ML IMPACT: {affected} training labels were incorrect")
            print(f"  Running backfill from corrected trade history...")

            if hasattr(engine, 'backfill_from_trade_history'):
                n = engine.backfill_from_trade_history(trades)
                print(f"  Backfilled {n} samples into replay buffer")
                return n
            else:
                print(f"  Note: backfill_from_trade_history() not available")
                print(f"  Replay buffer should be manually cleared and rebuilt")

        return affected

    except ImportError:
        print("  Warning: Could not import ML engine for backfill")
        return 0
    except Exception as e:
        print(f"  Warning: ML backfill failed (non-fatal): {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description='Verify trade settlements on-chain via CTF contract')
    parser.add_argument('--fix', action='store_true',
                        help='Fix discrepancies in trade_history.json and retrain ML')
    parser.add_argument('--condition-id', type=str,
                        help='Verify a single condition ID')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show every trade verification result')
    args = parser.parse_args()

    print("=" * 70)
    print("ON-CHAIN SETTLEMENT VERIFICATION")
    print(f"CTF Contract: {CTF_ADDRESS}")
    print(f"RPC: {RPC_URL}")
    print("=" * 70)

    # Quick connectivity check
    print("\nConnecting to Polygon...")
    try:
        resp = http_requests.post(RPC_URL, json={
            "jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1
        }, timeout=10)
        block = int(resp.json()['result'], 16)
        print(f"  Connected. Current block: {block}")
    except Exception as e:
        print(f"ERROR: Cannot connect to Polygon RPC: {e}")
        sys.exit(1)

    # Single condition check
    if args.condition_id:
        verify_single(args.condition_id)
        return

    # Mass verification
    print(f"\nLoading {TRADE_HISTORY}...")
    trades = load_trade_history()
    print(f"  Loaded {len(trades)} trades")

    stats = verify_all(trades, verbose=args.verbose)

    elapsed = time.time()

    # Print summary
    print(f"\n{'=' * 70}")
    print("VERIFICATION SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total trades:           {stats['total']}")
    print(f"  Verified correct:       {stats['verified_correct']}")
    print(f"  Discrepancies:          {len(stats['discrepancies'])}")
    print(f"  Unresolved on-chain:    {stats['unresolved_onchain']}")
    print(f"  Skipped (unsettled):    {stats['skipped_unsettled']}")
    print(f"  No condition_id:        {stats['no_condition_id']}")
    print(f"  RPC errors:             {stats['errors']}")

    if stats['discrepancies']:
        print(f"\n{'=' * 70}")
        print("DISCREPANCIES FOUND")
        print(f"{'=' * 70}")
        total_pnl_swing = 0
        for d in stats['discrepancies']:
            cost = d['cost']
            shares = d.get('shares', 0)
            if d['should_have_won'] and not d['recorded_won']:
                old_profit = d['profit']
                new_profit = shares - cost if shares else cost * 0.5
                swing = new_profit - old_profit
            else:
                old_profit = d['profit']
                new_profit = -cost
                swing = new_profit - old_profit
            total_pnl_swing += swing

            print(f"  {d['coin']} {d['prediction']} | cid={d['condition_id'][:20]}... | "
                  f"recorded={'WON' if d['recorded_won'] else 'LOST'} -> "
                  f"actual={'WON' if d['should_have_won'] else 'LOST'} "
                  f"(on-chain: {d['onchain_winner']})")

        print(f"\n  Estimated P&L swing: ${total_pnl_swing:+.2f}")

        if args.fix:
            print(f"\n{'=' * 70}")
            print("APPLYING FIXES")
            print(f"{'=' * 70}")
            fixed = apply_fixes(trades, stats['discrepancies'])
            print(f"  Fixed {fixed} trades in trade_history.json")

            ml_affected = backfill_ml(trades, stats['discrepancies'])
            if ml_affected:
                print(f"  ML pipeline updated: {ml_affected} samples affected")
        else:
            print(f"\n  Run with --fix to correct these discrepancies")
    else:
        print(f"\n  All settled trades match on-chain resolution.")
        if stats['unresolved_onchain'] > 0:
            print(f"  ({stats['unresolved_onchain']} trades still unresolved on-chain)")

    # Final trade_history summary
    won = sum(1 for t in trades if t.get('won') is True)
    lost = sum(1 for t in trades if t.get('won') is False)
    unsettled = sum(1 for t in trades if t.get('won') is None)
    total_profit = sum(t.get('profit', 0) or 0 for t in trades if t.get('won') is not None)
    print(f"\n  Trade History: {won}W / {lost}L / {unsettled} unsettled | Net P&L: ${total_profit:+.2f}")


if __name__ == '__main__':
    main()
