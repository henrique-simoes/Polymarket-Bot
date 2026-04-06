"""
15-Minute Market Integration
Specialized module for Polymarket's 15-minute crypto price prediction markets
"""

import os
import requests
import re
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List, Union
import time
import logging

logger = logging.getLogger("Market15M")

# Constants
TAG_ID_15M = 102467
DATA_API = "https://data-api.polymarket.com"

class Market15M:
    def __init__(self, polymarket_client):
        self.client = polymarket_client
        self.gamma_api = polymarket_client.gamma_api_url
        self.market_cache = {}
        self.token_cache = {}
        self.coingecko_cache = {}
        self.coingecko_cache_time = {}

    def clear_market_cache(self):
        self.market_cache.clear()
        self.token_cache.clear()

    def _fetch_15m_markets_from_api(self):
        response = requests.get(f"{self.gamma_api}/markets", params={
            'tag_id': TAG_ID_15M,
            'closed': 'false',
            'active': 'true',
            'limit': 100 
        }, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_rtds_price(self, market_id: str) -> Optional[float]:
        """
        Fetch the current 'Price to Beat' or 'Reference Price' from Polymarket's Data API.
        This is the source the website uses.
        """
        try:
            url = f"{DATA_API}/prices"
            params = {'market': market_id}
            resp = requests.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                # RTDS usually returns a list of price points
                if isinstance(data, list) and len(data) > 0:
                    return float(data[-1].get('price', 0))
                elif isinstance(data, dict):
                    return float(data.get('price', 0))
        except: pass
        return None

    def get_strike_from_webpage(self, slug: str, coin: str, start_time: datetime, end_time: datetime) -> Optional[float]:
        """
        Scrapes the 'Price to Beat' (Strike Price) directly from the Polymarket webpage.
        This mimics the user's manual check.
        """
        try:
            url = f"https://polymarket.com/event/{slug}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code != 200:
                logger.warning(f"Webpage fetch failed: {resp.status_code}")
                return None
                
            html = resp.text
            
            # Find __NEXT_DATA__ manually (regex can fail on huge lines)
            start_marker = '<script id="__NEXT_DATA__" type="application/json"'
            start_idx = html.find(start_marker)
            if start_idx == -1: return None
            
            # Find the closing tag
            json_start = html.find('>', start_idx) + 1
            json_end = html.find('</script>', json_start)
            
            if json_start == -1 or json_end == -1: return None
            
            json_str = html[json_start:json_end]
            data = json.loads(json_str)
            
            # Navigate to the specific query key we found during debugging
            # Key structure: ['crypto-prices', 'price', COIN, START_ISO, 'fifteen', END_ISO]
            # Note: ISO strings in key might vary slightly (e.g. Z vs +00:00), need to be careful.
            # The debug output showed '2026-02-01T22:15:00Z'.
            
            # Ensure UTC and strip tzinfo for Z formatting
            if start_time.tzinfo:
                start_time = start_time.astimezone(timezone.utc)
            if end_time.tzinfo:
                end_time = end_time.astimezone(timezone.utc)
                
            # Polymarket seems to use '2026-02-01T22:15:00Z' format
            start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
            end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
            
            symbol = coin.upper()
            
            queries = data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
            for q in queries:
                key = q.get('queryKey')
                if isinstance(key, list) and len(key) >= 6:
                    if key[0] == 'crypto-prices' and key[1] == 'price' and key[2] == symbol:
                        # We found a crypto-price query. Check if it roughly matches our window.
                        if key[4] == 'fifteen':
                            state = q.get('state', {}).get('data', {})
                            open_price = state.get('openPrice')
                            if open_price:
                                logger.info(f"WEB SCRAPE SUCCESS: Found strike {open_price} for {coin}")
                                return float(open_price)
                                
        except Exception as e:
            logger.error(f"Error scraping strike from webpage: {e}")
            
        return None

    def get_official_strike_price(self, coin: str) -> Optional[float]:
        """
        Attempts to extract strike from metadata.
        """
        market = self.market_cache.get(coin)
        if not market: return None
        
        # 0. Try Webpage Scrape (Most Authoritative as per user)
        try:
            slug = market.get('slug') or market.get('events', [{}])[0].get('slug')
            end_str = market.get('endDate')
            
            if slug and end_str:
                 # Parse end time
                 end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                 start_time = end_time - timedelta(minutes=15)
                 
                 web_price = self.get_strike_from_webpage(slug, coin, start_time, end_time)
                 if web_price: return web_price
        except Exception as e:
            logger.error(f"Failed to prep web scrape: {e}")
        
        # 1. Try RTDS Data API first (The Website Source)
        rtds_price = self.get_rtds_price(market.get('id'))
        if rtds_price and rtds_price > 0:
            return rtds_price

        # 2. Fallback to Regex on Description
        text = (market.get('question', '') + " " + market.get('description', '')).replace(',', '')
        price_pattern = re.compile(r'\$(\d+\.?\d*)')
        matches = price_pattern.findall(text)
        if matches:
            try:
                strike = float(matches[0])
                if strike > 0: return strike
            except: pass
            
        return None

    def get_current_15m_markets(self, coins: List[str] = None) -> Dict[str, Dict]:
        if coins is None: coins = ['BTC', 'ETH', 'SOL']
        markets = {}
        try:
            all_15m_markets = self._fetch_15m_markets_from_api()
            coin_map = {'BTC': ['bitcoin', 'btc'], 'ETH': ['ethereum', 'eth'], 'SOL': ['solana', 'sol']}
            now = datetime.now(timezone.utc)
            
            for coin in coins:
                terms = coin_map.get(coin, [coin.lower()])
                candidates = []
                for m in all_15m_markets:
                    question = m.get('question', '').lower()
                    if not any(term in question for term in terms): continue
                    end_str = m.get('endDate')
                    if not end_str: continue
                    try: end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                    except: continue
                    
                    if end_time > (now + timedelta(seconds=30)):
                        candidates.append((m, end_time))
                        
                if candidates:
                    candidates.sort(key=lambda x: x[1])
                    best_market = candidates[0][0]
                    markets[coin] = best_market
                    self.market_cache[coin] = best_market
        except Exception as e: logger.error(f"Error fetching 15M markets: {e}")
        return markets

    def get_token_ids_for_coin(self, coin: str) -> Optional[Dict[str, str]]:
        # Check if cached market is still valid (not closed)
        if coin in self.market_cache:
            market = self.market_cache[coin]
            # Check if market is closed
            if market.get('closed', False):
                logger.warning(f"{coin}: Cached market is CLOSED, clearing cache and fetching new market")
                self.market_cache.pop(coin, None)
                self.token_cache.pop(coin, None)
            else:
                # Check if market end time has passed
                end_str = market.get('endDate')
                if end_str:
                    try:
                        end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                        if datetime.now(timezone.utc) >= end_time:
                            logger.warning(f"{coin}: Cached market expired (end time passed), clearing cache")
                            self.market_cache.pop(coin, None)
                            self.token_cache.pop(coin, None)
                    except:
                        pass

        # Return cached tokens if still valid
        if coin in self.token_cache and coin in self.market_cache:
            return self.token_cache[coin]

        # Fetch new market if cache was cleared or doesn't exist
        if coin not in self.market_cache:
            self.get_current_15m_markets([coin])

        if coin not in self.market_cache:
            return None

        market = self.market_cache[coin]
        tokens = self.client.get_token_ids(market)
        if tokens:
            self.token_cache[coin] = tokens
        return tokens

    def get_current_price(self, coin: str) -> Optional[float]:
        tokens = self.get_token_ids_for_coin(coin)
        if not tokens or 'yes' not in tokens: return None
        yes_price = self.client.get_midpoint_price(tokens['yes'])

        # Check if market appears closed (YES=$1.00 means resolved)
        if yes_price == 1.0:
            # Verify by checking NO price
            no_price = self.client.get_midpoint_price(tokens.get('no')) if tokens.get('no') else None
            if no_price == 0.0:
                logger.warning(f"{coin}: Market appears CLOSED (YES=$1.00, NO=$0.00), clearing cache")
                self.market_cache.pop(coin, None)
                self.token_cache.pop(coin, None)
                return None

        return yes_price

    def get_both_prices(self, coin: str) -> Optional[Dict[str, float]]:
        """
        Get both YES and NO token prices for a coin.

        Uses the simple CLOB midpoint API with proper market validation.

        Returns:
            {'yes': float, 'no': float} or None if market not active
        """
        # Get fresh token IDs (validates market is active)
        tokens = self.get_token_ids_for_coin(coin)
        if not tokens:
            return None

        # Verify market is actually active
        market = self.market_cache.get(coin)
        if not market:
            logger.warning(f"{coin}: No market in cache")
            return None

        # Check market status
        if market.get('closed', False):
            logger.warning(f"{coin}: Market is CLOSED")
            self.market_cache.pop(coin, None)
            self.token_cache.pop(coin, None)
            return None

        if not market.get('active', True):
            logger.warning(f"{coin}: Market is NOT ACTIVE")
            return None

        # Get prices using simple midpoint API (with exception handling for market transitions)
        yes_price = None
        no_price = None

        if tokens.get('yes'):
            try:
                yes_price = self.client.get_midpoint_price(tokens['yes'])
            except Exception as e:
                logger.warning(f"  YES price fetch failed (market may be transitioning): {e}")
                # Clear cache and return None - market is likely closed/transitioning
                self.market_cache.pop(coin, None)
                self.token_cache.pop(coin, None)
                return None

        if tokens.get('no'):
            try:
                no_price = self.client.get_midpoint_price(tokens['no'])
            except Exception as e:
                logger.warning(f"  NO price fetch failed (market may be transitioning): {e}")
                # If YES worked but NO failed, clear cache and return None
                self.market_cache.pop(coin, None)
                self.token_cache.pop(coin, None)
                return None

        logger.info(f"  YES Token Price: ${yes_price:.2f}" if yes_price else "  YES Token Price: None")
        logger.info(f"  NO Token Price: ${no_price:.2f}" if no_price else "  NO Token Price: None")

        # Return None only if BOTH prices are missing
        if yes_price is None and no_price is None:
            logger.warning(f"  Both YES and NO prices are None - market may be closed")
            self.market_cache.pop(coin, None)
            self.token_cache.pop(coin, None)
            return None

        # If only one price is missing, calculate it from the other (YES + NO = 1.0)
        if yes_price is not None and no_price is None:
            no_price = 1.0 - yes_price
            logger.info(f"  NO price calculated from YES: ${no_price:.2f}")
        elif no_price is not None and yes_price is None:
            yes_price = 1.0 - no_price
            logger.info(f"  YES price calculated from NO: ${yes_price:.2f}")

        # CRITICAL CHECK: If prices are $1.00/$0.00, market likely closed!
        if yes_price == 1.0 and no_price == 0.0:
            logger.error(f"  ✗ ERROR: Market appears CLOSED (YES=$1.00, NO=$0.00) - clearing cache and returning None")
            # Clear the cache immediately
            self.market_cache.pop(coin, None)
            self.token_cache.pop(coin, None)
            # Try to fetch new market
            self.get_current_15m_markets([coin])
            # Return None to force refresh on next call
            return None

        return {'yes': yes_price, 'no': no_price}

    def place_prediction(self, coin: str, prediction: str, amount_usdc: float) -> Optional[Dict]:
        logger.info(f"PLACING {prediction} BET: {coin} (${amount_usdc:.2f})")
        tokens = self.get_token_ids_for_coin(coin)
        if not tokens: return None

        # CRITICAL DEBUG: Show which token we're betting on
        token_type = 'YES' if prediction == "UP" else 'NO'
        token_id = tokens.get('yes') if prediction == "UP" else tokens.get('no')
        logger.info(f"[TOKEN DEBUG] Prediction={prediction} → Betting on {token_type} token (ID: {token_id[:16]}...)")
        logger.info(f"[TOKEN DEBUG] Available tokens: YES={tokens.get('yes', 'MISSING')[:16] if tokens.get('yes') else 'MISSING'}..., NO={tokens.get('no', 'MISSING')[:16] if tokens.get('no') else 'MISSING'}...")

        if not token_id: return None
        
        result = self.client.create_market_buy_order(token_id, amount_usdc)
        if result:
            market = self.market_cache.get(coin, {})
            condition_id = market.get('conditionId') or market.get('condition_id')
            if not condition_id:
                logger.error(f"No conditionId found for {coin} - market resolution will fail. "
                             f"Available keys: {list(market.keys())[:10]}")
            price = self.client.get_midpoint_price(token_id) or 0.5
            shares = amount_usdc / price

            # Capture blockchain identifiers from order response
            tx_hashes = result.get('transactionHashes', [])
            order_status = result.get('status', '')

            return {
                'coin': coin, 'prediction': prediction, 'token_id': token_id,
                'condition_id': condition_id, 'price': price, 'shares': shares,
                'cost': amount_usdc, 'order_id': result.get('orderID'),
                'timestamp': datetime.now(timezone.utc),
                # Market metadata for traceability
                'market_slug': market.get('slug', ''),
                'market_question': market.get('question', ''),
                'market_end_date': market.get('endDate', ''),
                # Blockchain identifiers
                'transaction_hashes': tx_hashes,
                'clob_status': order_status,
            }
        return None

    def get_current_window_info(self) -> Dict:
        now = datetime.now(timezone.utc)
        minute = (now.minute // 15) * 15
        start = now.replace(minute=minute, second=0, microsecond=0)
        end = start + timedelta(minutes=15)
        remaining = (end - now).total_seconds()
        if remaining < 0:
            start = end
            end = start + timedelta(minutes=15)
            remaining = (end - now).total_seconds()
        return {'start_time': start, 'end_time': end, 'seconds_remaining': remaining, 'seconds_elapsed': 900 - remaining}

    def check_gamma_resolution(self, condition_id: str) -> Optional[str]:
        """
        Check market resolution via Gamma API (powers the Polymarket frontend).

        The Gamma API reliably returns:
        - closed: boolean (true when market is resolved)
        - outcomePrices: string like "1,0" (first outcome won) or "0,1" (second outcome won)
        - outcomes: array like ["Up", "Down"]

        Returns:
            'UP' or 'DOWN' if resolved, None if not resolved yet
        """
        try:
            url = f"{self.gamma_api}/markets"
            params = {'condition_id': condition_id}
            resp = requests.get(url, params=params, timeout=10)

            if resp.status_code != 200:
                logger.warning(f"[SETTLEMENT] Gamma API returned {resp.status_code} for {condition_id[:16]}...")
                return None

            markets = resp.json()

            # Gamma API returns a list of markets matching the condition_id
            if not markets or not isinstance(markets, list) or len(markets) == 0:
                logger.warning(f"[SETTLEMENT] Gamma API: No markets found for {condition_id[:16]}...")
                return None

            market = markets[0]
            closed = market.get('closed', False)
            outcome_prices = market.get('outcomePrices', '')
            outcomes = market.get('outcomes', [])

            # Check UMA resolution status for additional confirmation
            uma_status = market.get('umaResolutionStatus', '')
            if uma_status:
                logger.info(f"[SETTLEMENT] Gamma API: umaResolutionStatus={uma_status}")
                if uma_status in ('proposed', 'disputed'):
                    logger.info(f"[SETTLEMENT] UMA status '{uma_status}' — market not yet finalized, skipping")
                    return None

            # Parse outcomes if it's a JSON string like '["Up","Down"]'
            if isinstance(outcomes, str):
                try:
                    outcomes = json.loads(outcomes)
                except (json.JSONDecodeError, ValueError):
                    outcomes = [o.strip().strip('"\'') for o in outcomes.strip('[]').split(',')]

            logger.info(f"[SETTLEMENT] Gamma API: closed={closed}, outcomePrices={outcome_prices}, outcomes={outcomes}")

            if not closed:
                return None

            # Parse outcomePrices: returned as stringified list from API per official example
            # Official Polymarket agents code uses: json.loads(market["outcomePrices"])
            if outcome_prices:
                try:
                    if isinstance(outcome_prices, list):
                        prices = [float(p) for p in outcome_prices]
                    elif isinstance(outcome_prices, str):
                        # Official method: json.loads() the stringified list
                        try:
                            parsed = json.loads(outcome_prices)
                            prices = [float(p) for p in parsed]
                        except (json.JSONDecodeError, TypeError):
                            # Fallback: manual CSV parsing
                            cleaned = outcome_prices.strip().strip('[]"\'')
                            prices = [float(p.strip().strip('"\'')) for p in cleaned.split(',')]
                    else:
                        prices = [float(outcome_prices)]
                    if len(prices) >= 2 and len(outcomes) >= 2:
                        # Find the winning outcome (price = 1.0)
                        for i, price in enumerate(prices):
                            if price >= 0.99:  # Winner has price ~1.0
                                winning_outcome = outcomes[i].upper()
                                if 'UP' in winning_outcome or winning_outcome == 'YES':
                                    logger.info(f"[SETTLEMENT] ✓ Gamma RESOLVED: UP (outcomePrices={outcome_prices})")
                                    return 'UP'
                                elif 'DOWN' in winning_outcome or winning_outcome == 'NO':
                                    logger.info(f"[SETTLEMENT] ✓ Gamma RESOLVED: DOWN (outcomePrices={outcome_prices})")
                                    return 'DOWN'
                                else:
                                    # Fallback by index: index 0 = first outcome, index 1 = second
                                    result = 'UP' if i == 0 else 'DOWN'
                                    logger.info(f"[SETTLEMENT] ✓ Gamma RESOLVED: {result} (by index, outcome={winning_outcome})")
                                    return result
                except (ValueError, IndexError) as e:
                    logger.warning(f"[SETTLEMENT] Failed to parse outcomePrices '{outcome_prices}': {e}")

            # Fallback: Check tokens[].winner from Gamma response
            tokens = market.get('tokens', [])
            for i, token in enumerate(tokens):
                if token.get('winner'):
                    outcome_str = token.get('outcome', '').upper()
                    if 'UP' in outcome_str or outcome_str == 'YES':
                        return 'UP'
                    elif 'DOWN' in outcome_str or outcome_str == 'NO':
                        return 'DOWN'
                    else:
                        return 'UP' if i == 0 else 'DOWN'

            # Market closed but can't determine winner
            logger.warning(f"[SETTLEMENT] Gamma: Market closed but winner unclear. Full response keys: {list(market.keys())}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"[SETTLEMENT] Gamma API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"[SETTLEMENT] Gamma resolution check error: {e}")
            return None

    def check_onchain_resolution(self, condition_id: str) -> Optional[str]:
        """
        Check market resolution directly on-chain via CTF contract.

        Reads payoutDenominator() and payoutNumerators() from the Conditional
        Token Framework contract. This is the ultimate source of truth.

        Args:
            condition_id: Market condition ID (0x-prefixed hex)

        Returns:
            'UP' or 'DOWN' if resolved on-chain, None if not resolved or error
        """
        try:
            from web3 import Web3

            rpc_url = os.environ.get("POLYGON_RPC_URL", "https://polygon-bor-rpc.publicnode.com")
            ctf_address = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

            ctf_abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "conditionId", "type": "bytes32"}],
                    "name": "payoutDenominator",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [
                        {"name": "conditionId", "type": "bytes32"},
                        {"name": "index", "type": "uint256"}
                    ],
                    "name": "payoutNumerators",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function"
                }
            ]

            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if not w3.is_connected():
                logger.warning("[SETTLEMENT] On-chain check: Cannot connect to Polygon RPC")
                return None

            ctf = w3.eth.contract(
                address=Web3.to_checksum_address(ctf_address),
                abi=ctf_abi
            )

            # Convert condition_id to bytes32
            cid_hex = condition_id[2:] if condition_id.startswith('0x') else condition_id
            cid_bytes = bytes.fromhex(cid_hex).rjust(32, b'\x00')

            denom = ctf.functions.payoutDenominator(cid_bytes).call()
            if denom == 0:
                logger.info(f"[SETTLEMENT] On-chain: Not resolved yet (payoutDenominator=0)")
                return None

            # Get payout numerators for binary outcomes (index 0=Up, 1=Down)
            num_up = ctf.functions.payoutNumerators(cid_bytes, 0).call()
            num_down = ctf.functions.payoutNumerators(cid_bytes, 1).call()

            logger.info(f"[SETTLEMENT] On-chain: denom={denom}, numerators=[{num_up}, {num_down}]")

            if num_up > 0 and num_down == 0:
                logger.info(f"[SETTLEMENT] ✓ ON-CHAIN RESOLVED: UP")
                return 'UP'
            elif num_down > 0 and num_up == 0:
                logger.info(f"[SETTLEMENT] ✓ ON-CHAIN RESOLVED: DOWN")
                return 'DOWN'
            else:
                logger.warning(f"[SETTLEMENT] On-chain: Unusual payouts [{num_up}, {num_down}]")
                return None

        except ImportError:
            logger.debug("[SETTLEMENT] web3 not available for on-chain check")
            return None
        except Exception as e:
            logger.warning(f"[SETTLEMENT] On-chain check failed (non-fatal): {e}")
            return None

    def check_official_resolution(self, condition_id: str) -> Optional[str]:
        """
        Checks if the market is officially resolved on Polymarket.

        Resolution sources (in order of reliability):
        1. Gamma API - outcomePrices + closed flag (powers the frontend, most reliable)
        2. CLOB API - token.winner flag on market tokens (backup)
        3. On-chain CTF contract - payoutNumerators (ultimate source of truth, last resort)

        Wallet-level reconciliation (sync_trades_from_wallet) handles everything else.

        Args:
            condition_id: Market condition ID

        Returns:
            'UP' or 'DOWN' if resolved, None if not resolved yet
        """
        try:
            # Method 1: Gamma API (MOST RELIABLE - powers the Polymarket website)
            gamma_result = self.check_gamma_resolution(condition_id)
            if gamma_result:
                return gamma_result

            # Method 2: CLOB API fallback - check market data
            try:
                market = self.client.get_market(condition_id)
                if not market:
                    logger.info(f"[SETTLEMENT] CLOB: Market not found for {condition_id[:16]}...")
                else:
                    closed = market.get('closed', False)
                    logger.info(f"[SETTLEMENT] CLOB: Market {condition_id[:16]}... closed={closed}")

                    if closed:
                        # Check winner flag on tokens
                        tokens = market.get('tokens', [])
                        for i, token in enumerate(tokens):
                            is_winner = token.get('winner', False)
                            outcome_str = token.get('outcome', 'unknown')
                            logger.info(f"[SETTLEMENT]   CLOB Token {i}: outcome={outcome_str}, winner={is_winner}")

                            if is_winner:
                                outcome_upper = outcome_str.upper()
                                if 'UP' in outcome_upper or outcome_upper == 'YES':
                                    logger.info(f"[SETTLEMENT] ✓ CLOB RESOLVED: UP")
                                    return 'UP'
                                elif 'DOWN' in outcome_upper or outcome_upper == 'NO':
                                    logger.info(f"[SETTLEMENT] ✓ CLOB RESOLVED: DOWN")
                                    return 'DOWN'
                                else:
                                    result = 'UP' if i == 0 else 'DOWN'
                                    logger.info(f"[SETTLEMENT] ✓ CLOB RESOLVED: {result} (by index)")
                                    return result

                        logger.info(f"[SETTLEMENT] CLOB: Market closed but no winner flag on tokens")

            except Exception as clob_err:
                logger.error(f"[SETTLEMENT] CLOB API fallback error: {clob_err}")

            # Method 3: On-chain CTF contract (ultimate source of truth)
            onchain_result = self.check_onchain_resolution(condition_id)
            if onchain_result:
                return onchain_result

            return None

        except Exception as e:
            logger.error(f"[SETTLEMENT] Error checking official resolution: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def get_real_crypto_price(self, coin: str) -> Optional[float]:
        try:
            if coin in self.coingecko_cache and (time.time() - self.coingecko_cache_time.get(coin, 0) < 60):
                return self.coingecko_cache[coin]
            ids = {'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana'}
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids.get(coin)}&vs_currencies=usd"
            data = requests.get(url, timeout=5).json()
            price = data[ids.get(coin)]['usd']
            self.coingecko_cache[coin] = price
            self.coingecko_cache_time[coin] = time.time()
            return price
        except: return None