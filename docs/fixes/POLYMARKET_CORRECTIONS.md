# Polymarket Integration Corrections

## Critical Fixes Applied (Based on Official Documentation)

### 1. Currency: USDC, NOT USDT ✅

**Corrected:**
- USDC contract address on Polygon: `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`
- All references updated from USDT to USDC
- Both have 6 decimals on Polygon

**Files updated:**
- `src/core/wallet.py` - Now uses USDC contract
- `config/config.yaml` - Updated to USDC address

### 2. No Gas Fees for Trading ✅

**Important:** Polymarket CLOB (Central Limit Order Book) is **off-chain**.

- ❌ **NO gas fees** for placing orders
- ❌ **NO gas fees** for canceling orders
- ✅ Gas (MATIC) **only needed** for:
  - Depositing USDC to Polymarket
  - Withdrawing USDC from Polymarket
  - On-chain settlement transactions

**For trading:** You only need USDC balance. MATIC is optional.

### 3. Correct API Endpoints ✅

**Official Polymarket APIs:**

| API | Purpose | Endpoint |
|-----|---------|----------|
| **Gamma API** | Market discovery, events, metadata | `https://gamma-api.polymarket.com` |
| **CLOB API** | Order placement, orderbook | `https://clob.polymarket.com` |
| **Data API** | Historical trades, positions | `https://data-api.polymarket.com` |
| **WebSocket** | Real-time orderbook updates | `wss://ws-subscriptions-clob.polymarket.com` |

**Files updated:**
- `src/core/polymarket.py` - Updated to use official endpoints
- `config/config.yaml` - Added all API URLs

### 4. Recommended: Use Official SDK

Instead of raw HTTP requests, use the official Python SDK:

```bash
pip install py-clob-client
```

**Benefits:**
- Authentication handled automatically
- Order signing built-in
- Type-safe API
- Maintained by Polymarket team

## What You Need to Run the Bot

### Minimum Requirements:

1. **USDC on Polygon network** (for trading)
   - Example: 0.5 USDC minimum
   - Get USDC: Bridge from Ethereum or buy on Polygon DEX

2. **Polygon wallet with private key**
   - MetaMask wallet works
   - Export private key to `.env` file

3. **Optional: Small MATIC** (only for deposits/withdrawals, NOT trading)
   - ~0.01 MATIC is enough if needed
   - Most trading doesn't require MATIC

### Configuration Checklist:

✅ **`.env` file:**
```bash
WALLET_PRIVATE_KEY=0x...  # Your Polygon wallet
POLYGON_RPC_URL=https://polygon-rpc.com
```

✅ **`config/config.yaml`:**
```yaml
trading:
  initial_bet_usdt: 0.5  # Amount in USDC (name kept for compatibility)
```

## Updated Architecture

### Before (Incorrect):
- Used USDT ❌
- Assumed gas fees for all trades ❌
- Generic Polymarket API URL ❌
- No distinction between market discovery and trading ❌

### After (Correct):
- Uses USDC ✅
- No gas fees for CLOB trading ✅
- Official API endpoints (Gamma, CLOB, Data, WebSocket) ✅
- Proper API separation ✅

## Next Steps for Full Implementation

To make this production-ready, you should:

1. **Install official SDK:**
   ```bash
   pip install py-clob-client
   ```

2. **Implement authentication** (required for placing orders)
   - CLOB API requires signed requests
   - SDK handles this automatically

3. **Update market discovery** to use Gamma API
   - Find real markets (not 15-minute crypto price markets)
   - Get market IDs, condition IDs, token IDs

4. **Implement real order placement** using CLOB API or SDK

5. **Add WebSocket** for real-time price updates

## Official Documentation

- **Main docs:** https://docs.polymarket.com
- **Gamma API:** https://docs.polymarket.com/api-reference/gamma
- **CLOB API:** https://docs.polymarket.com/api-reference/clob
- **Python SDK:** https://github.com/Polymarket/py-clob-client

## Summary of Changes

| Component | Before | After |
|-----------|--------|-------|
| Currency | USDT ❌ | USDC ✅ |
| Contract Address | `0xc213...` (USDT) | `0x2791...` (USDC) |
| Gas for trading | Required ❌ | Not required ✅ |
| API endpoints | Generic | Official (Gamma, CLOB, Data, WS) |
| Market discovery | Not implemented | Gamma API ready |
| Order placement | Simulated | CLOB API ready |

---

**Your bot is now configured correctly for Polymarket!** 🎯

The code still needs SDK integration for real trading, but the foundation is now accurate.
