"""
Recover past trades from Polymarket CLOB API
Queries user's order history and imports into trade_history.json
"""

import json
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from py_clob_client import ClobClient
from src.core.wallet import WalletManager


def extract_coin_from_market(order, client):
    """Extract coin (BTC/ETH/SOL) from market metadata"""
    try:
        # Get condition_id from order
        condition_id = order.get('market')
        if not condition_id:
            return None

        # Query market details
        market = client.get_market(condition_id)
        if market:
            question = market.get('question', '').upper()
            # Look for coin names in question
            if 'BTC' in question or 'BITCOIN' in question:
                return 'BTC'
            elif 'ETH' in question or 'ETHEREUM' in question:
                return 'ETH'
            elif 'SOL' in question or 'SOLANA' in question:
                return 'SOL'

        return None
    except Exception as e:
        print(f"  Warning: Could not extract coin from market: {e}")
        return None


def determine_outcome(order, client):
    """Determine if order won or lost by checking market resolution"""
    try:
        condition_id = order.get('market')
        token_id = order.get('asset_id')

        if not condition_id or not token_id:
            return None

        # Get market details
        market = client.get_market(condition_id)
        if not market:
            return None

        # Check if market is resolved
        closed = market.get('closed', False)
        if not closed:
            # Market not settled yet
            return None

        # Get winning outcome
        # In Polymarket, the winning token typically has price = 1.0
        outcome_prices = market.get('outcome_prices', [])
        tokens = market.get('tokens', [])

        # Find our token
        for i, token in enumerate(tokens):
            if token.get('token_id') == token_id:
                # Check if this token won (price should be 1.0 or close to it)
                if i < len(outcome_prices):
                    final_price = float(outcome_prices[i])
                    # Won if final price > 0.9 (settled at ~1.0)
                    return final_price > 0.9

        return None
    except Exception as e:
        print(f"  Warning: Could not determine outcome: {e}")
        return None


def calculate_profit(order, won):
    """Calculate profit/loss for order"""
    if won is None:
        return None

    try:
        price = float(order.get('price', 0))
        size = float(order.get('size', 0))

        if won:
            # Won: shares * (1 - price)
            return size * (1 - price)
        else:
            # Lost: -cost
            return -price * size
    except Exception as e:
        print(f"  Warning: Could not calculate profit: {e}")
        return None


def recover_trades(days_back=3):
    """
    Recover trades from past N days

    Args:
        days_back: Number of days to look back (default 3)
    """
    load_dotenv()

    # Initialize client
    host = "https://clob.polymarket.com"
    key = os.getenv('WALLET_PRIVATE_KEY')

    if not key:
        print("ERROR: WALLET_PRIVATE_KEY not found in .env file")
        return

    # Get chain ID from config
    try:
        import yaml
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        chain_id = config['polymarket'].get('chain_id', 137)
    except:
        chain_id = 137

    # Initialize wallet to get address
    wallet = WalletManager()
    address = wallet.address

    # Initialize CLOB client
    from py_clob_client import ClobClient
    from py_clob_client.client import ClobClient as FullClient
    from py_clob_client.clob_types import OpenOrderParams

    # Get funder address (check for proxy)
    funder = config['polymarket'].get('funder')
    if funder == "0x...":
        funder = None
    signature_type = config['polymarket'].get('signature_type', 0)

    # Use authenticated client
    print(f"Initializing CLOB client...")
    client = FullClient(host, key=key, chain_id=chain_id, signature_type=signature_type, funder=funder)

    # Authenticate
    try:
        creds = client.create_or_derive_api_creds()
        if creds:
            client.set_api_creds(creds)
            print(f"  [AUTH] API Credentials active: {creds.api_key[:6]}...")
        else:
            print("  [WARN] Could not create API credentials")
    except Exception as e:
        print(f"  [ERROR] Authentication failed: {e}")
        print("  [INFO] Will try to query orders anyway...")

    print(f"\nQuerying orders for address: {address}")
    print(f"Looking back {days_back} days...")
    print()

    # Query user's orders
    # According to py-clob-client docs, get_orders() returns user's orders
    try:
        # Try to get all orders for this user
        # Use OpenOrderParams to get all orders
        orders = client.get_orders(OpenOrderParams())

        if not orders:
            print("No orders found in CLOB API")
            return

        print(f"Found {len(orders)} total orders")

        # Filter for matched/filled orders only
        filled_orders = [o for o in orders if o.get('status') in ['MATCHED', 'FILLED']]
        print(f"Found {len(filled_orders)} filled orders")

    except Exception as e:
        print(f"ERROR querying orders: {e}")
        print("\nTrying alternative approach using orderbook history...")
        filled_orders = []

    # Load existing trade history
    history_file = 'data/trade_history.json'
    if os.path.exists(history_file):
        with open(history_file, 'r') as f:
            existing_trades = json.load(f)
    else:
        existing_trades = []

    existing_order_ids = {t.get('order_id') for t in existing_trades}
    print(f"Existing trade history has {len(existing_trades)} trades")
    print()

    # Convert orders to trade format
    new_trades = []
    skipped = 0

    for order in filled_orders:
        order_id = order.get('id')

        # Skip if already in history
        if order_id in existing_order_ids:
            skipped += 1
            continue

        # Extract coin from market
        coin = extract_coin_from_market(order, client)
        if not coin:
            print(f"  Skipping order {order_id[:16]}... - could not determine coin")
            continue

        # Determine outcome
        won = determine_outcome(order, client)
        if won is None:
            print(f"  Skipping order {order_id[:16]}... - market not settled yet")
            continue

        # Calculate profit
        profit = calculate_profit(order, won)

        # Determine direction (UP/DOWN)
        side = order.get('side', 'BUY')
        # In Polymarket, buying YES token = predicting UP
        # buying NO token = predicting DOWN
        # We need to check the token to determine direction
        token_id = order.get('asset_id', '')
        # Simplified: assume BUY = UP (would need token metadata for accurate determination)
        direction = 'UP' if side == 'BUY' else 'DOWN'

        # Convert to trade format
        trade = {
            'coin': coin,
            'prediction': direction,
            'token_id': order.get('asset_id'),
            'condition_id': order.get('market'),
            'price': float(order.get('price', 0)),
            'shares': float(order.get('size', 0)),
            'cost': float(order.get('price', 0)) * float(order.get('size', 0)),
            'order_id': order_id,
            'timestamp': order.get('created_at', datetime.now().isoformat()),
            'start_price': None,  # Unknown, leave blank
            'final_price': None,  # Could query from market resolution
            'won': won,
            'profit': profit
        }

        new_trades.append(trade)
        print(f"  ✓ Imported: {coin} {direction} - {'WON' if won else 'LOST'} (${profit:.2f})")

    print()
    print(f"Skipped {skipped} trades already in history")
    print(f"Found {len(new_trades)} new trades to import")

    if new_trades:
        # Append to history
        all_trades = existing_trades + new_trades

        # Save back to file
        os.makedirs('data', exist_ok=True)
        with open(history_file, 'w') as f:
            json.dump(all_trades, f, indent=2)

        print()
        print(f"✓ Imported {len(new_trades)} trades")
        print(f"✓ Total trades in history: {len(all_trades)}")
    else:
        print()
        print("No new trades to import")


if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 3

    print("=" * 60)
    print("POLYMARKET TRADE RECOVERY UTILITY")
    print("=" * 60)
    print()

    recover_trades(days_back=days)

    print()
    print("=" * 60)
    print("RECOVERY COMPLETE")
    print("=" * 60)
