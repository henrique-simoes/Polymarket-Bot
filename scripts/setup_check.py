import os
import sys
import json
from decimal import Decimal
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

# Try to import optional dependencies
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False

def print_status(msg, status="info"):
    if HAS_RICH:
        if status == "pass":
            console.print(f"[green]✓ {msg}[/green]")
        elif status == "fail":
            console.print(f"[red]✗ {msg}[/red]")
        elif status == "warn":
            console.print(f"[yellow]! {msg}[/yellow]")
        else:
            console.print(f"[blue]i {msg}[/blue]")
    else:
        prefix = {"pass": "[PASS]", "fail": "[FAIL]", "warn": "[WARN]", "info": "[INFO]"}.get(status, "[INFO]")
        print(f"{prefix} {msg}")

def run_checks():
    load_dotenv()
    
    if HAS_RICH:
        console.print(Panel("Polymarket Bot Setup Validation", style="bold blue"))
    else:
        print("=== Polymarket Bot Setup Validation ===")

    # 1. Check Python Dependencies
    print_status("Checking Python dependencies...", "info")
    if HAS_RICH:
        print_status("'rich' library is installed", "pass")
    else:
        print_status("'rich' library is MISSING (pip install rich)", "fail")
        
    if HAS_TALIB:
        print_status("TA-Lib C-library and Python wrapper detected", "pass")
    else:
        print_status("TA-Lib is MISSING or C-library not found", "fail")
        print_status("   Installation guide: https://github.com/mrjbq7/ta-lib", "info")

    # 2. Check .env variables
    print_status("Checking environment variables...", "info")
    pk = os.getenv('WALLET_PRIVATE_KEY')
    rpc = os.getenv('POLYGON_RPC_URL')
    
    if not pk or pk == "your_private_key_here":
        print_status("WALLET_PRIVATE_KEY is missing or not set in .env", "fail")
    else:
        try:
            acc = Account.from_key(pk)
            print_status(f"Wallet loaded: {acc.address}", "pass")
        except Exception as e:
            print_status(f"Invalid WALLET_PRIVATE_KEY: {e}", "fail")

    if not rpc:
        print_status("POLYGON_RPC_URL is missing in .env", "fail")
    else:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc))
            if w3.is_connected():
                print_status(f"Polygon RPC connected: {rpc}", "pass")
                chain_id = w3.eth.chain_id
                if chain_id != 137:
                    print_status(f"Wrong chain ID: {chain_id} (Expected 137 for Polygon)", "fail")
            else:
                print_status(f"Failed to connect to RPC: {rpc}", "fail")
        except Exception as e:
            print_status(f"RPC Connection error: {e}", "fail")

    # 3. Check Wallet Balances
    if pk and rpc:
        try:Acc = Account.from_key(pk); W3 = Web3(Web3.HTTPProvider(rpc)); 
        if W3.is_connected():
            pol_balance = W3.eth.get_balance(Acc.address)
            pol_eth = W3.from_wei(pol_balance, 'ether')
            if pol_eth < 0.05:
                print_status(f"Low POL balance ({pol_eth:.4f} POL). You need at least ~0.1 POL for gas/approvals.", "warn")
            else:
                print_status(f"POL Balance: {pol_eth:.4f} POL (OK for gas)", "pass")
            
            # Check USDC.e (Bridged)
            usdc_e_addr = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
            usdc_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
            usdc_contract = W3.eth.contract(address=W3.to_checksum_address(usdc_e_addr), abi=usdc_abi)
            usdc_bal = usdc_contract.functions.balanceOf(Acc.address).call()
            usdc_dec = Decimal(usdc_bal) / Decimal(10**6)
            
            if usdc_dec < 1.0:
                print_status(f"Low USDC.e balance ({usdc_dec:.2f}). Polymarket minimum trade is $1.00.", "warn")
            else:
                print_status(f"USDC.e Balance: {usdc_dec:.2f} (OK for trading)", "pass")
        except: pass

    print_status("Check complete.", "info")

if __name__ == "__main__":
    run_checks()
