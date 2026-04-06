"""
Force Redeem - Trade History Direct Map
Uses the 'market' field in trade history to find Condition IDs directly.
"""
import os
import sys
import json
import requests
import time
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

# Load environment
load_dotenv()
pk = os.getenv("WALLET_PRIVATE_KEY")
if not pk:
    print("Error: WALLET_PRIVATE_KEY not found")
    sys.exit(1)

account = Account.from_key(pk)
w3 = Web3(Web3.HTTPProvider(os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")))

# Polymarket Config
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
USDC_ADDRESS = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
HOST = "https://clob.polymarket.com"

# Load Config for Proxy
import yaml
try:
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
        funder = config['polymarket'].get('funder')
except:
    funder = None

user_address = funder if funder else account.address
print(f"Target Wallet: {user_address}")

# 1. Fetch Trade History
print("Fetching trade history via CLOB API...")
client = ClobClient(HOST, key=pk, chain_id=137, funder=funder)
try:
    try:
        with open('data/.api_credentials.json', 'r') as f:
            c = json.load(f)
            creds = ApiCreds(c['api_key'], c['api_secret'], c['api_passphrase'])
            client.set_api_creds(creds)
    except:
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        
    trades = client.get_trades()
    print(f"Found {len(trades)} historical trades.")
except Exception as e:
    print(f"Error fetching trades: {e}")
    sys.exit(1)

# 2. Extract Condition IDs from Trades
# The trade object likely has 'market' or 'condition_id' or 'asset_id'
# We map asset_id -> condition_id from the trade data itself if available
token_to_condition = {}

print("Analyzing trade data...")
if trades:
    print(f"Sample Trade Keys: {list(trades[0].keys())}")
    
    for t in trades:
        tid = t.get('asset_id')
        # Check for condition id field
        cid = t.get('market') # 'market' is usually condition_id in CLOB
        
        if tid and cid:
            token_to_condition[tid] = cid

print(f"Mapped {len(token_to_condition)} tokens from history.")

# 3. KNOWN TOKEN IDS (from your audit)
target_tokens = [
    "114789925512961285541453597688298252249463265034850180712008597613295570336192",
    "36041803948223245789709188342514866121342600181999680362306567560541164092020",
    "12235611117180380796084731810699889283838233376749626339670985466190542771225",
    "8178867129681717104737076205498096704965283019763463316638104231227233799176",
    "54633277254783263621563197526605763109479273849200256287228477068719135729804",
    "46997030808049478322824170106050604588927584775119347922650035701944948857812"
]

# 4. Match
redeemable = set()
for tid in target_tokens:
    cid = token_to_condition.get(tid)
    if cid:
        print(f" -> MATCH: Token {tid[:15]}... = Condition {cid}")
        redeemable.add(cid)
    else:
        print(f" -> NO MATCH: Token {tid[:15]}... (Not found in trade history?)")

# 5. Execute Redemption
print(f"\nRedeeming {len(redeemable)} unique conditions...")
redeem_abi = [{"inputs":[{"internalType":"contract IERC20","name":"collateralToken","type":"address"},{"internalType":"bytes32","name":"parentCollectionId","type":"bytes32"},{"internalType":"bytes32","name":"conditionId","type":"bytes32"},{"internalType":"uint256[]","name":"indexSets","type":"uint256[]"}],"name":"redeemPositions","outputs":[],"stateMutability":"nonpayable","type":"function"}]
ctf_write = w3.eth.contract(address=w3.to_checksum_address(CTF_ADDRESS), abi=redeem_abi)

for cid in redeemable:
    print(f"Redeeming Condition {cid}...")
    try:
        tx = ctf_write.functions.redeemPositions(
            w3.to_checksum_address(USDC_ADDRESS),
            bytes(32),
            bytes.fromhex(cid[2:]) if cid.startswith('0x') else bytes.fromhex(cid),
            [1, 2]
        ).build_transaction({
            'from': account.address,
            'gas': 300000,
            'gasPrice': w3.eth.gas_price,
            'nonce': w3.eth.get_transaction_count(account.address),
            'chainId': 137
        })
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f" -> Sent: {tx_hash.hex()}")
        w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        print(" -> Confirmed")
    except Exception as e:
        print(f" -> Failed: {e}")

print("Done.")