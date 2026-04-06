"""
Polymarket Integration - Official SDK Implementation
Uses py-clob-client for authentication, trading, and market data
"""

import os
import requests
import json
import math
import logging
from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, MarketOrderArgs, OpenOrderParams
from py_clob_client.order_builder.constants import BUY, SELL
from web3 import Web3
from eth_account import Account

logger = logging.getLogger(__name__)


class PolymarketMechanics:
# ... (existing init) ...

    def __init__(self, private_key: str = None, chain_id: int = 137,
                 signature_type: int = 0, funder: str = None, order_type: str = "GTC"):
        self.gamma_api_url = "https://gamma-api.polymarket.com"
        self.clob_api_url = "https://clob.polymarket.com"
        self.data_api_url = "https://data-api.polymarket.com"
        self.ws_url = "wss://ws-subscriptions-clob.polymarket.com"
        self.CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"  # Checksum format
        self.USDC_BRIDGED = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # REQUIRED by CLOB
        self.USDC_NATIVE = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
        self.USDC_ADDRESS = self.USDC_BRIDGED  # Use bridged USDC for CLOB trading 

        self.private_key = private_key or os.getenv('WALLET_PRIVATE_KEY')
        if not self.private_key: raise ValueError("Private key required.")

        self.chain_id = chain_id
        polygon_rpc = os.getenv('POLYGON_RPC_URL', "https://polygon-rpc.com")
        self.w3 = Web3(Web3.HTTPProvider(polygon_rpc))
        self.account = Account.from_key(self.private_key)

        # Check for Proxy Address
        self.proxy_address = os.getenv('PROXY_ADDRESS')
        if funder is None:
            if self.proxy_address:
                funder = self.proxy_address
                print(f"  [INFO] Using Proxy Address from env: {funder}")
            elif signature_type == 0:
                funder = self.account.address

        self.funder_address = funder

        print(f"Initializing Polymarket CLOB client (Funder: {funder})...")
        try:
            self.client = ClobClient(
                self.clob_api_url,
                key=self.private_key,
                chain_id=chain_id,
                signature_type=signature_type,
                funder=funder
            )
            
            # Explicit Auth Step with Logging
            try: 
                creds = self.client.create_or_derive_api_creds()
                if creds:
                    self.client.set_api_creds(creds)
                    print(f"  [AUTH] API Credentials active: {creds.api_key[:6]}...")
                else:
                    print("  [WARN] create_or_derive_api_creds returned None.")
            except Exception as e:
                print(f"  [ERROR] L2 Auth failed: {e}")
                
        except Exception as e:
            print(f"[ERROR] Client init failed: {e}")

    def get_token_ids(self, market: Dict) -> Dict[str, str]:
        """Extract token IDs from market data"""
        try:
            if 'clobTokenIds' in market and 'outcomes' in market:
                token_ids = json.loads(market['clobTokenIds']) if isinstance(market['clobTokenIds'], str) else market['clobTokenIds']
                outcomes = json.loads(market['outcomes']) if isinstance(market['outcomes'], str) else market['outcomes']

                # CRITICAL DEBUG: Show raw token mapping
                logger.info(f"\n{'='*60}")
                logger.info(f"[TOKEN MAPPING DEBUG]")
                logger.info(f"  Market Question: {market.get('question', 'UNKNOWN')[:80]}")
                logger.info(f"  Raw Outcomes: {outcomes}")
                logger.info(f"  Raw Token IDs: {[tid[:16] + '...' for tid in token_ids]}")

                result = {}
                for i, outcome in enumerate(outcomes):
                    logger.info(f"  Outcome[{i}]: '{outcome}' → Token: {token_ids[i][:16]}...")
                    if outcome.lower() in ['up', 'yes']:
                        result['yes'] = token_ids[i]
                        logger.info(f"    ✓ Mapped to YES token")
                    elif outcome.lower() in ['down', 'no']:
                        result['no'] = token_ids[i]
                        logger.info(f"    ✓ Mapped to NO token")
                    else:
                        logger.warning(f"    ✗ UNKNOWN OUTCOME LABEL: '{outcome}' not in ['up', 'yes', 'down', 'no']")

                logger.info(f"  Final Mapping: YES={result.get('yes', 'MISSING')[:16] if result.get('yes') else 'MISSING'}..., NO={result.get('no', 'MISSING')[:16] if result.get('no') else 'MISSING'}...")
                logger.info(f"{'='*60}\n")

                return result
            
            tokens = market.get('tokens', [])
            result = {}
            for token in tokens:
                outcome = token.get('outcome', '').lower()
                token_id = token.get('token_id')
                if outcome and token_id:
                    result[outcome] = token_id
            return result
        except Exception as e:
            print(f"[ERROR] Parsing token IDs: {e}")
            return {}

    def get_positions(self) -> List[Dict]:
        user = self.funder_address if self.funder_address else self.account.address
        try:
            if hasattr(self.client, 'get_positions'): return self.client.get_positions(user=user)
            return []
        except: return []

    def get_open_orders(self) -> List[Dict]:
        """Fetch active open orders from the CLOB"""
        try:
            # If getting all open orders, params can be empty or specific to market
            # Using empty params to get ALL orders for the user
            resp = self.client.get_orders(OpenOrderParams())
            return resp if isinstance(resp, list) else []
        except Exception as e:
            print(f"[ERROR] Failed to fetch open orders: {e}")
            return []

    def auto_redeem_all_winnings(self, trade_history: List[Dict]) -> Dict:
        """
        Proxy Wallet Redemption requires interacting with the Proxy Factory.
        This cannot be done directly from the EOA key in this script context.
        """
        print("[INFO] Automatic redemption is disabled for Proxy Wallets.")
        print("[INFO] Please use the Polymarket UI or a specialized Proxy script to redeem winnings.")
        return {}

    def get_usdc_balance(self):
        """Get USDC balance directly via Web3"""
        try:
            user = self.funder_address if self.funder_address else self.account.address
            erc20 = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
            c = self.w3.eth.contract(address=self.w3.to_checksum_address(self.USDC_ADDRESS), abi=erc20)
            bal = c.functions.balanceOf(user).call() / 1e6
            return bal
        except: return 0.0

    def get_midpoint_price(self, token_id):
        try:
            result = self.client.get_midpoint(token_id)
            # get_midpoint returns dict like {'mid': '0.55'}
            if result and 'mid' in result:
                return float(result['mid'])
            else:
                logger.warning(f"Invalid midpoint response for {token_id}: {result}")
                return None
        except Exception as e:
            logger.error(f"Failed to get midpoint price for {token_id}: {e}")
            return None
    
    def get_orderbook(self, token_id):
        try: return self.client.get_order_book(token_id)
        except: return None

    def get_market(self, condition_id: str):
        """Fetch market details including settlement status"""
        try:
            return self.client.get_market(condition_id)
        except Exception as e:
            print(f"[ERROR] Failed to get market {condition_id}: {e}")
            return None

    def get_fee_rate(self, token_id: str) -> int:
        """Fetch maker/taker fee bps from API"""
        try:
            url = f"{self.clob_api_url}/fee-rate"
            params = {'token_id': token_id}
            resp = requests.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return int(data.get('fee_rate_bps', 0))
        except Exception as e:
            print(f"[WARN] Failed to fetch fee rate: {e}")
        return 0

    def _round_order_amounts(self, price, size, tick_size=0.01):
        """
        Fix decimal precision for orders to prevent 400 errors.
        - Price: Dynamic based on tick_size (e.g. 0.1 -> 1 decimal, 0.01 -> 2 decimals)
        - Size (shares): 4 decimals (safe max)
        """
        # Calculate decimals from tick_size
        try:
            if tick_size <= 0: tick_size = 0.01
            decimals = int(abs(math.log10(tick_size)))
        except:
            decimals = 2
            
        # Round price
        price = round(price, decimals)
        
        # Round size to 4 decimals (floor to be safe)
        size = math.floor(size * 10000) / 10000
        
        return price, size

    def create_market_buy_order(self, token_id, amount):
        """
        PLACES A REAL MARKET ORDER
        Strictly follows official Polymarket example:
        1. Fetch fee rate (REQUIRED for 15-minute markets)
        2. Create MarketOrderArgs with fee_rate_bps
        3. Sign with create_market_order
        4. Post with post_order(orderType=FOK)
        """
        try:
            print(f"  [EXEC] Placing Market BUY for ${amount:.2f}...")

            # 1. Fetch fee rate (CRITICAL for 15-minute markets)
            fee_rate = self.get_fee_rate(token_id)
            if fee_rate > 0:
                print(f"  [FEE] Market has {fee_rate} bps fee (~{fee_rate/100:.2f}%)")

            # 2. Prepare Arguments
            # Note: The official example uses MarketOrderArgs with token_id, amount, side.
            # fee_rate_bps is REQUIRED for fee-enabled markets (15-minute crypto markets)
            market_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount,
                side=BUY,
                fee_rate_bps=fee_rate
            )

            # 3. Create and Sign Order (L1)
            signed_order = self.client.create_market_order(market_args)

            # 4. Post Order (L2)
            # The example explicitly passes orderType=OrderType.FOK
            resp = self.client.post_order(signed_order, orderType=OrderType.FOK)

            print(f"  [SUCCESS] Order Posted: {resp}")
            return resp

        except Exception as e:
            print(f"  [ERROR] Market Order failed: {e}")
            return None

    def create_limit_order(self, token_id: str, price: float, size: float, side: str):
        """
        Place a limit order (GTC - Good-Til-Canceled)
        Used for market making to earn maker rebates

        Args:
            token_id: Token to trade
            price: Limit price (0.01 to 0.99)
            size: Number of shares
            side: BUY or SELL

        Returns:
            Order response dict or None if failed
        """
        try:
            print(f"  [LIMIT] Placing {side} limit order: {size:.2f} shares @ ${price:.3f}")

            # 1. Fetch fee rate
            fee_rate = self.get_fee_rate(token_id)
            if fee_rate > 0:
                print(f"  [FEE] Maker rebate available: {fee_rate} bps (~{fee_rate/100:.2f}%)")

            # 2. Round price and size to valid precision
            price, size = self._round_order_amounts(price, size)

            # 3. Create OrderArgs for limit order
            # Note: OrderArgs (not MarketOrderArgs) is used for limit orders
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
                fee_rate_bps=fee_rate
            )

            # 4. Create and sign order
            signed_order = self.client.create_order(order_args)

            # 5. Post order as GTC (Good-Til-Canceled)
            # GTC orders stay in orderbook until filled or manually canceled
            resp = self.client.post_order(signed_order, orderType=OrderType.GTC)

            print(f"  [SUCCESS] Limit order placed: {resp.get('orderID', 'N/A')[:16]}...")
            return resp

        except Exception as e:
            print(f"  [ERROR] Limit order failed: {e}")
            logger.error(f"Limit order placement failed: {e}")
            return None

    def cancel_order(self, order_id: str):
        """
        Cancel an active order
        Used to remove limit orders when market moves or time expires

        Args:
            order_id: Order ID to cancel

        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"  [CANCEL] Canceling order {order_id[:16]}...")
            resp = self.client.cancel(order_id)  # FIXED: cancel() not cancel_order()
            print(f"  [SUCCESS] Order canceled")
            return True

        except Exception as e:
            print(f"  [ERROR] Order cancellation failed: {e}")
            logger.error(f"Cancel order failed for {order_id}: {e}")
            return False

    def get_order_status(self, order_id: str):
        """
        Check status of an order

        Returns:
            Order dict with status, or None if not found
        """
        try:
            order = self.client.get_order(order_id)
            return order
        except Exception as e:
            logger.error(f"Get order status failed for {order_id}: {e}")
            return None

    def calculate_profit(self, shares, buy_price, won):
        if won: return (shares * 1.0) - (shares * buy_price)
        return -(shares * buy_price)