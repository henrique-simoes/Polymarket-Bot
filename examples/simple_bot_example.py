"""
Simple Polymarket Bot Example
Demonstrates real integration with Polymarket using official SDK

This is a simplified version showing how to:
1. Connect to Polymarket with authentication
2. Discover real markets
3. Get prices and orderbooks
4. Place actual orders

For production use, integrate with ML models from the main bot.
"""

import os
import yaml
from dotenv import load_dotenv
from core.wallet import WalletManager
from core.polymarket import PolymarketMechanics


class SimplePolymarketBot:
    """
    Simple bot demonstrating real Polymarket integration
    """

    def __init__(self, config_path: str = 'config/config.yaml'):
        """Initialize bot with real Polymarket connection"""
        print("\n" + "="*80)
        print("SIMPLE POLYMARKET BOT - REAL INTEGRATION EXAMPLE")
        print("="*80 + "\n")

        # Load environment
        load_dotenv()

        # Load config
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Initialize wallet
        print("1. Initializing wallet...")
        self.wallet = WalletManager()

        print(f"\n   Wallet: {self.wallet.address}")
        print(f"   USDC Balance: {self.wallet.get_usdc_balance():.2f} USDC")
        print(f"   POL Balance: {self.wallet.get_matic_balance():.4f} POL (for approvals)")

        # Check token approvals
        print("\n2. Checking token approvals...")
        approvals = self.wallet.check_polymarket_approvals()

        if approvals['usdc_approved'] and approvals['ctf_approved']:
            print("   [OK] USDC approved")
            print("   [OK] CTF approved")
            print("   Ready to trade!")
        else:
            print("   [ERROR] Tokens not approved")
            print("\n   You need to approve tokens first.")
            print("   Run: python -c \"from src.core.wallet import WalletManager; WalletManager().approve_polymarket_trading()\"")
            print("\n   Or set approve_on_start=True in this script.")

            # Optionally approve automatically (requires POL for gas, self-managed wallets)
            approve = input("\n   Approve tokens now? (y/n): ")
            if approve.lower() == 'y':
                self.wallet.approve_polymarket_trading()

        # Initialize Polymarket
        print("\n3. Initializing Polymarket SDK...")
        polymarket_config = self.config['polymarket']

        self.polymarket = PolymarketMechanics(
            private_key=os.getenv('WALLET_PRIVATE_KEY'),
            chain_id=polymarket_config['chain_id'],
            signature_type=polymarket_config.get('signature_type', 0)
        )

        print("\n" + "="*80)
        print("[OK] BOT INITIALIZED SUCCESSFULLY")
        print("="*80 + "\n")

    def discover_markets(self, search_query: str = None, limit: int = 10):
        """
        Discover available markets

        Args:
            search_query: Search term (e.g., "crypto", "sports")
            limit: Maximum markets to return
        """
        print("\n" + "-"*80)
        print("DISCOVERING MARKETS")
        print("-"*80 + "\n")

        if search_query:
            print(f"Searching for markets: '{search_query}'")
            markets = self.polymarket.search_markets(search_query, limit=limit)
        else:
            print(f"Fetching active markets...")
            markets = self.polymarket.get_markets(limit=limit, active=True)

        if not markets:
            print("No markets found.")
            return []

        print(f"\nFound {len(markets)} markets:\n")

        for i, market in enumerate(markets, 1):
            # Extract market info
            question = market.get('question', 'N/A')
            market_id = market.get('id', 'N/A')
            active = market.get('active', False)
            end_date = market.get('end_date_iso', 'N/A')

            # Get tokens
            tokens = self.polymarket.get_token_ids(market)
            yes_token = tokens.get('yes', 'N/A')

            # Get current price if token available
            price_str = "N/A"
            if yes_token != 'N/A':
                try:
                    price = self.polymarket.get_midpoint_price(yes_token)
                    if price:
                        price_str = f"{price:.2%}"
                except:
                    pass

            print(f"{i}. {question[:70]}")
            print(f"   Market ID: {market_id}")
            print(f"   YES Price: {price_str}")
            print(f"   Active: {active} | Ends: {end_date[:10]}")
            print()

        return markets

    def analyze_market(self, market_id: str):
        """
        Analyze a specific market

        Args:
            market_id: Market identifier
        """
        print("\n" + "-"*80)
        print(f"ANALYZING MARKET: {market_id}")
        print("-"*80 + "\n")

        # Get market details
        market = self.polymarket.get_market_by_id(market_id)
        if not market:
            print("Market not found")
            return

        # Display market info
        print(f"Question: {market.get('question', 'N/A')}")
        print(f"Description: {market.get('description', 'N/A')[:200]}")
        print(f"Active: {market.get('active', False)}")
        print(f"Closed: {market.get('closed', False)}")

        # Get token IDs
        tokens = self.polymarket.get_token_ids(market)
        yes_token = tokens.get('yes')
        no_token = tokens.get('no')

        if not yes_token:
            print("\nNo token IDs available")
            return

        print(f"\nToken IDs:")
        print(f"  YES: {yes_token}")
        print(f"  NO: {no_token}")

        # Get orderbook
        print(f"\nOrderbook (YES token):")
        orderbook = self.polymarket.get_orderbook(yes_token)

        if orderbook:
            bids = orderbook.get('bids', [])[:5]
            asks = orderbook.get('asks', [])[:5]

            print("\n  Best Bids:")
            for bid in bids:
                print(f"    ${float(bid['price']):.4f} - {float(bid['size']):.2f} shares")

            print("\n  Best Asks:")
            for ask in asks:
                print(f"    ${float(ask['price']):.4f} - {float(ask['size']):.2f} shares")

        # Get prices
        midpoint = self.polymarket.get_midpoint_price(yes_token)
        buy_price = self.polymarket.get_price(yes_token, "BUY")
        sell_price = self.polymarket.get_price(yes_token, "SELL")

        print(f"\nPrices:")
        print(f"  Midpoint: {midpoint:.2%}" if midpoint else "  Midpoint: N/A")
        print(f"  Buy (Ask): {buy_price:.2%}" if buy_price else "  Buy: N/A")
        print(f"  Sell (Bid): {sell_price:.2%}" if sell_price else "  Sell: N/A")

    def place_test_order(self, token_id: str, amount_usdc: float = 1.0, side: str = "BUY"):
        """
        Place a small test order

        Args:
            token_id: Token ID to trade
            amount_usdc: Amount in USDC (default 1.0 for testing)
            side: "BUY" or "SELL"
        """
        print("\n" + "-"*80)
        print(f"PLACING TEST ORDER")
        print("-"*80 + "\n")

        # Get current price
        current_price = self.polymarket.get_midpoint_price(token_id)
        if not current_price:
            print("Unable to get current price")
            return

        print(f"Token ID: {token_id}")
        print(f"Current Price: {current_price:.2%}")
        print(f"Order Size: {amount_usdc} USDC")
        print(f"Side: {side}")

        # Calculate shares
        shares = self.polymarket.calculate_shares_from_usdc(amount_usdc, current_price)
        print(f"Shares: ~{shares:.2f}")

        # Confirm
        confirm = input("\nPlace order? (y/n): ")
        if confirm.lower() != 'y':
            print("Order cancelled")
            return

        # Place market order (immediate execution)
        result = self.polymarket.create_market_buy_order(token_id, amount_usdc)

        if result:
            print(f"\n[OK] Order placed successfully!")
            print(f"   Order ID: {result.get('orderID', 'N/A')}")
        else:
            print(f"\n[ERROR] Order failed")

    def check_positions(self):
        """Check open orders and positions"""
        print("\n" + "-"*80)
        print("CHECKING POSITIONS")
        print("-"*80 + "\n")

        # Get open orders
        orders = self.polymarket.get_open_orders()
        if orders:
            print(f"Open Orders: {len(orders)}")
            for order in orders[:10]:  # Show first 10
                print(f"  Order ID: {order.get('orderID', 'N/A')}")
                print(f"    Side: {order.get('side', 'N/A')}")
                print(f"    Price: ${float(order.get('price', 0)):.4f}")
                print(f"    Size: {float(order.get('size', 0)):.2f}")
                print()
        else:
            print("No open orders")

        # Get trade history
        trades = self.polymarket.get_trades()
        if trades:
            print(f"\nRecent Trades: {len(trades)}")
            for trade in trades[:5]:  # Show last 5
                print(f"  Trade ID: {trade.get('id', 'N/A')}")
                print(f"    Side: {trade.get('side', 'N/A')}")
                print(f"    Price: ${float(trade.get('price', 0)):.4f}")
                print(f"    Size: {float(trade.get('size', 0)):.2f}")
                print()
        else:
            print("\nNo trade history")


def main():
    """Main execution"""
    # Initialize bot
    bot = SimplePolymarketBot()

    # Interactive menu
    while True:
        print("\n" + "="*80)
        print("SIMPLE BOT MENU")
        print("="*80)
        print("1. Discover markets")
        print("2. Analyze specific market")
        print("3. Check positions")
        print("4. Place test order")
        print("5. Exit")
        print("-"*80)

        choice = input("Select option: ")

        if choice == "1":
            query = input("Search query (or press Enter for all active): ")
            bot.discover_markets(search_query=query if query else None)

        elif choice == "2":
            market_id = input("Enter market ID: ")
            bot.analyze_market(market_id)

        elif choice == "3":
            bot.check_positions()

        elif choice == "4":
            token_id = input("Enter token ID: ")
            amount = float(input("Enter amount USDC (e.g., 1.0): "))
            bot.place_test_order(token_id, amount)

        elif choice == "5":
            print("\nExiting...")
            break

        else:
            print("\nInvalid option")


if __name__ == "__main__":
    main()
