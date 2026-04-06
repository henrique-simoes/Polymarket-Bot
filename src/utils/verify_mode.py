"""
Mode Detection Verification Script
Helps diagnose which mode the bot is running in by examining logs and state
"""

import os
import sys
import json
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


def check_log_files():
    """Check recent log entries for mode indicators"""
    print("\n" + "=" * 60)
    print("CHECKING LOG FILES")
    print("=" * 60)

    # Check bot.log for mode indicators
    log_file = 'bot.log'
    if os.path.exists(log_file):
        print(f"\nReading {log_file}...")
        with open(log_file, 'r') as f:
            lines = f.readlines()

        # Look for mode indicators
        mode_lines = [l for l in lines if 'BOT MODE:' in l or '[LEARNING]' in l or '[REAL]' in l]

        if mode_lines:
            print("\nMode indicators found:")
            for line in mode_lines[-10:]:  # Last 10 mode-related lines
                print(f"  {line.strip()}")
        else:
            print("\nNo explicit mode indicators found in log")

        # Check settlement logs
        settlement_lines = [l for l in lines if 'SETTLEMENT' in l]
        if settlement_lines:
            print("\nRecent settlement logs:")
            for line in settlement_lines[-5:]:  # Last 5 settlement lines
                print(f"  {line.strip()}")

    else:
        print(f"\n{log_file} not found")


def check_trade_files():
    """Check trade history files"""
    print("\n" + "=" * 60)
    print("CHECKING TRADE FILES")
    print("=" * 60)

    # Check real mode trades
    real_trades_file = 'data/trade_history.json'
    if os.path.exists(real_trades_file):
        with open(real_trades_file, 'r') as f:
            real_trades = json.load(f)
        print(f"\nReal Mode Trades (data/trade_history.json): {len(real_trades)} trades")

        if real_trades:
            # Show most recent
            recent = real_trades[-3:]
            print("\nMost recent real trades:")
            for trade in recent:
                timestamp = trade.get('timestamp', 'unknown')
                coin = trade.get('coin', 'unknown')
                direction = trade.get('prediction', 'unknown')
                won = trade.get('won', False)
                print(f"  {timestamp}: {coin} {direction} - {'WON' if won else 'LOST'}")
    else:
        print(f"\n{real_trades_file} not found (no real trades yet)")

    # Check learning mode trades
    learning_trades_file = 'data/learning_trades.json'
    if os.path.exists(learning_trades_file):
        with open(learning_trades_file, 'r') as f:
            learning_trades = json.load(f)
        print(f"\nLearning Mode Trades (data/learning_trades.json): {len(learning_trades)} trades")

        if learning_trades:
            # Show most recent
            recent = learning_trades[-3:]
            print("\nMost recent learning trades:")
            for trade in recent:
                timestamp = trade.get('timestamp', 'unknown')
                coin = trade.get('coin', 'unknown')
                direction = trade.get('prediction', 'unknown')
                won = trade.get('won', False)
                print(f"  {timestamp}: {coin} {direction} - {'WON' if won else 'LOST'}")
    else:
        print(f"\n{learning_trades_file} not found (no learning trades yet)")


def check_learning_state():
    """Check learning mode state file"""
    print("\n" + "=" * 60)
    print("CHECKING LEARNING STATE")
    print("=" * 60)

    state_file = 'data/learning_state.json'
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            state = json.load(f)

        print(f"\nLearning State (data/learning_state.json):")
        print(f"  Virtual Balance: ${state.get('virtual_balance', 0):.2f}")
        print(f"  Total P&L: ${state.get('total_pnl', 0):.2f}")
        print(f"  Wins: {state.get('wins', 0)}")
        print(f"  Losses: {state.get('losses', 0)}")
        print(f"  Last Updated: {state.get('last_updated', 'unknown')}")
    else:
        print(f"\n{state_file} not found (learning mode never used)")


def main():
    print("=" * 60)
    print("POLYMARKET BOT MODE VERIFICATION")
    print("=" * 60)
    print("\nThis script checks which mode the bot is running in")
    print("by examining logs, trade files, and state")

    check_log_files()
    check_trade_files()
    check_learning_state()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    # Provide summary and recommendations
    print("\nTo verify the bot is in REAL MODE:")
    print("  1. Log files should show '[REAL]' markers, not '[LEARNING]'")
    print("  2. data/trade_history.json should be updating after each round")
    print("  3. data/learning_trades.json should NOT be updating")
    print("  4. Dashboard header should NOT show '| LEARNING MODE |'")

    print("\nTo verify the bot is in LEARNING MODE:")
    print("  1. Log files should show '[LEARNING]' markers, not '[REAL]'")
    print("  2. data/learning_trades.json should be updating after each round")
    print("  3. data/trade_history.json should NOT be updating")
    print("  4. Dashboard header should show '| LEARNING MODE |'")

    print("\nNext steps:")
    print("  - Check bot.log for mode indicators at startup")
    print("  - Restart bot and observe which mode is selected")
    print("  - If wrong mode, check startup selection code")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
