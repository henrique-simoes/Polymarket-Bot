# Bot Health Report (Auto-Generated)
**Last Updated:** 2026-04-06 14:27:29

## 1. Vitals
- **Status:** Running
- **Uptime:** (Derived from logs)
- **Trade Attempts:** 0
- **Success Rate:** 0.0%

## 2. Diagnosis (The "Doctor's Note")
⚠️ **WARNING:** High rate of API failures. Network or Rate Limit issue.

## 3. Top Errors
- `] WebSocket error: server rejected WebSocket conne`: 348 times
- `API_Instability`: 297 times
- `] Error scraping strike from webpage: HTTPSConnect`: 120 times
- `] Initial state check failed: 'WalletManager' obje`: 25 times
- `] Failed to get midpoint price for 112992080107624`: 2 times

## 4. Recommendations
- Consider increasing retry backoff in `market_15m.py`.
