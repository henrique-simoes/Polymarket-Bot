"""
Wallet Manager - Handles USDC on Polygon network
Includes transaction signing, gas management, and security features

IMPORTANT: Polymarket uses USDC (NOT USDT)
- For self-managed wallets: Small amount of POL needed for token approvals
- For email/Google signups: Polymarket covers all gas costs via proxy wallet
"""

import os
from web3 import Web3
from eth_account import Account
from eth_account.signers.local import LocalAccount
import json
from decimal import Decimal
import time
from typing import Dict

class WalletManager:
    """Manages crypto wallet for Polymarket betting"""

    def __init__(self, private_key=None, rpc_url=None, proxy_address=None):
        """
        Initialize wallet connection

        Args:
            private_key: Wallet private key (from env var if None)
            rpc_url: Polygon RPC URL (from env var if None)
            proxy_address: Optional Proxy/Safe address to check balances for
        """
        # Load from environment if not provided
        self.private_key = private_key or os.getenv('WALLET_PRIVATE_KEY')
        self.rpc_url = rpc_url or os.getenv('POLYGON_RPC_URL', 'https://polygon-rpc.com')
        self.proxy_address = proxy_address or os.getenv('PROXY_ADDRESS') # Also check env

        if not self.private_key:
            raise ValueError("Private key not provided. Set WALLET_PRIVATE_KEY env var.")

        # Connect to Polygon
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))

        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to Polygon RPC: {self.rpc_url}")

        # Load account
        self.account: LocalAccount = Account.from_key(self.private_key)
        self.address = self.account.address
        
        # Effective address for balances
        self.effective_address = self.proxy_address if self.proxy_address else self.address

        # USDC Contract on Polygon (6 decimals) - Polymarket uses USDC
        # IMPORTANT: Polymarket CLOB uses Bridged USDC.e, NOT Native USDC
        self.usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

        # CTF (Conditional Token Framework) Contract on Polygon
        self.ctf_address = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

        # Polymarket Exchange/Router contracts (spenders for approvals)
        # ALL THREE contracts must be approved for full trading capability
        self.polymarket_exchange = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"  # Main exchange
        self.neg_risk_exchange = "0xC5d563A36AE78145C45a50134d48A1215220f80a"    # Neg risk markets
        self.neg_risk_adapter = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"     # Neg risk adapter

        # ERC20/ERC1155 Mixed ABI
        token_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [
                    {"name": "_owner", "type": "address"},
                    {"name": "_spender", "type": "address"}
                ],
                "name": "allowance",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            # ERC1155 Specific
            {
                "constant": False,
                "inputs": [
                    {"name": "operator", "type": "address"},
                    {"name": "approved", "type": "bool"}
                ],
                "name": "setApprovalForAll",
                "outputs": [],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [
                    {"name": "owner", "type": "address"},
                    {"name": "operator", "type": "address"}
                ],
                "name": "isApprovedForAll",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]

        self.usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.usdc_address),
            abi=token_abi
        )

        # CTF Contract
        self.ctf_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.ctf_address),
            abi=token_abi
        )

        print(f"Wallet connected: {self.address}")
        print(f"Network: Polygon (Chain ID: {self.w3.eth.chain_id})")
        print(f"Gas Price: {self.w3.eth.gas_price / 10**9:.2f} Gwei")

    def get_usdc_balance(self):
        """Get USDC balance in human-readable format"""
        try:
            # Check Bridged USDC (Standard for CLOB)
            balance_wei = self.usdc_contract.functions.balanceOf(self.effective_address).call()
            balance = Decimal(balance_wei) / Decimal(10**6)
            
            if balance == 0:
                print(f"[WARN] Bridged USDC (0x2791...) Balance is 0 for {self.effective_address[:10]}...")
                
                # Diagnostic: Check Native USDC
                try:
                    native_addr = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
                    native_contract = self.w3.eth.contract(address=native_addr, abi=self.usdc_contract.abi)
                    native_bal = native_contract.functions.balanceOf(self.effective_address).call()
                    if native_bal > 0:
                        print(f"[ALERT] FOUND {native_bal/1e6} NATIVE USDC (0x3c49...)!")
                        print("[INFO] Polymarket CLOB requires Bridged USDC (0x2791...). Please swap/bridge your USDC.")
                except: pass
                
            return float(balance)
        except Exception as e:
            print(f"Error fetching USDC balance: {e}")
            return 0.0

    def approve_polymarket_trading(self, amount_usdc: float = 1000000) -> bool:
        """
        Approve both USDC and CTF tokens for ALL THREE Polymarket contracts:
        1. Main Exchange (standard markets)
        2. Neg Risk Exchange (negative risk markets)
        3. Neg Risk Adapter (negative risk market adapter)

        This is REQUIRED by official Polymarket documentation for full trading capability.
        """
        print("\n" + "="*60)
        print("APPROVING TOKENS FOR POLYMARKET TRADING")
        print("="*60)

        success = True
        contracts = [
            ("Main Exchange", self.polymarket_exchange),
            ("Neg Risk Exchange", self.neg_risk_exchange),
            ("Neg Risk Adapter", self.neg_risk_adapter)
        ]

        # Approve USDC for all three contracts
        print("\n1. Approving USDC for all contracts...")
        for name, contract in contracts:
            print(f"   - {name}...")
            usdc_tx = self.approve_contract(contract, amount_usdc)
            if usdc_tx is None:
                print(f"     (Already approved)")
            elif usdc_tx:
                print(f"     [OK] Approved")
            else:
                print(f"     [ERROR] Failed")
                success = False

        # Approve CTF (ERC1155) for all three contracts
        print("\n2. Approving CTF (Conditional Tokens) for all contracts...")
        for name, contract in contracts:
            print(f"   - {name}...")
            try:
                # Check isApprovedForAll
                is_approved = self.ctf_contract.functions.isApprovedForAll(
                    self.address,
                    Web3.to_checksum_address(contract)
                ).call()

                if is_approved:
                    print(f"     (Already approved)")
                else:
                    # Build approval transaction
                    nonce = self.w3.eth.get_transaction_count(self.address)
                    gas_price = self.w3.eth.gas_price

                    txn = self.ctf_contract.functions.setApprovalForAll(
                        Web3.to_checksum_address(contract),
                        True
                    ).build_transaction({
                        'from': self.address,
                        'gas': 100000,
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'chainId': 137
                    })

                    # Sign and send
                    signed_txn = self.w3.eth.account.sign_transaction(txn, self.private_key)
                    txn_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)

                    print(f"     Transaction sent: {txn_hash.hex()}")

                    # Wait for confirmation
                    receipt = self.w3.eth.wait_for_transaction_receipt(txn_hash, timeout=120)

                    if receipt.status == 1:
                        print(f"     [OK] Approved")
                    else:
                        print(f"     [ERROR] Failed")
                        success = False

            except Exception as e:
                print(f"     [ERROR] Error: {e}")
                success = False

        print("\n" + "="*60)
        if success:
            print("[OK] ALL APPROVALS COMPLETE - Ready to trade!")
        else:
            print("[ERROR] SOME APPROVALS FAILED - Check errors above")
        print("="*60 + "\n")

        return success

    def check_polymarket_approvals(self) -> Dict[str, bool]:
        """
        Check if tokens are approved for Polymarket
        """
        try:
            # Check USDC allowance
            usdc_allowance = self.usdc_contract.functions.allowance(
                self.address,
                Web3.to_checksum_address(self.polymarket_exchange)
            ).call()

            # Check CTF allowance (isApprovedForAll)
            ctf_approved = self.ctf_contract.functions.isApprovedForAll(
                self.address,
                Web3.to_checksum_address(self.polymarket_exchange)
            ).call()

            # Need at least 1 USDC worth approved
            min_amount = int(1 * 10**6)

            return {
                'usdc_approved': usdc_allowance >= min_amount,
                'ctf_approved': ctf_approved,
                'usdc_allowance': float(Decimal(usdc_allowance) / Decimal(10**6)),
                'ctf_allowance': 1.0 if ctf_approved else 0.0
            }

        except Exception as e:
            print(f"Error checking approvals: {e}")
            return {
                'usdc_approved': False,
                'ctf_approved': False,
                'usdc_allowance': 0,
                'ctf_allowance': 0
            }
