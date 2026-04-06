# Bot Health Report (Auto-Generated)
**Last Updated:** 2026-02-08 00:52:27

## 1. Vitals
- **Status:** Running
- **Uptime:** (Derived from logs)
- **Trade Attempts:** 92
- **Success Rate:** 82494.6%

## 2. Diagnosis (The "Doctor's Note")
⚠️ **WARNING:** High rate of API failures. Network or Rate Limit issue.

## 3. Top Errors
- `API_Instability`: 173810 times
- `] WebSocket error: server rejected WebSocket conne`: 30223 times
- `] [SETTLEMENT] Error checking trade outcomes: 'Pol`: 134 times
- `] Error scraping strike from webpage: ('Connection`: 110 times
- `] Error scraping strike from webpage: HTTPSConnect`: 79 times

## 4. Recommendations
- Consider increasing retry backoff in `market_15m.py`.
