"""
Order Tracking System - Monitors open orders and stores completed trades

Wallet Data API is the source of truth for trade reconciliation.
Live settlement uses settle_and_save_trade() upsert pattern.
Startup recovery uses sync_trades_from_wallet() for comprehensive reconciliation.

Field naming convention (matches place_prediction() and dashboard):
  - 'prediction' (not 'direction') - UP or DOWN
  - 'price' (not 'entry_price') - token entry price paid
  - 'cost' (not 'amount') - USDC spent
  - 'profit' (not 'pnl') - profit/loss in USDC
  - 'condition_id' - market identifier for Gamma API resolution
"""

import logging
import requests
from datetime import datetime
from typing import Dict, Optional, List
from threading import Lock

logger = logging.getLogger("OrderTracker")

DATA_API = "https://data-api.polymarket.com"


class OrderTracker:
    """
    Tracks active orders and records completed trades for ML learning.

    Methods:
    - track_order(): Register new order for dashboard display
    - get_active_orders(): List active orders for dashboard
    - settle_and_save_trade(): Upsert settled trade record (live settlement)
    - sync_trades_from_wallet(): Comprehensive wallet reconciliation (startup)
    - clear_stale_orders(): Remove old active orders from dashboard
    """

    def __init__(self, client, history_manager):
        self.client = client
        self.history = history_manager
        self.active_orders = {}  # order_id -> order_data
        self._lock = Lock()

        logger.info("OrderTracker initialized")

    def track_order(self, order_id: str, coin: str, prediction: str,
                   cost: float, token_id: str, start_price: float,
                   condition_id: str = None, shares: float = 0,
                   price: float = 0, market_slug: str = '',
                   transaction_hashes: list = None) -> None:
        """
        Register new order for tracking (dashboard display + settlement).

        Args:
            order_id: Order ID from CLOB
            coin: Coin symbol (BTC, ETH, SOL)
            prediction: UP or DOWN
            cost: Bet amount in USDC
            token_id: Token ID for YES or NO
            start_price: Strike price at market start
            condition_id: Market condition ID (for Gamma API resolution)
            shares: Number of shares purchased
            price: Entry price per share
            market_slug: Market URL slug for reference
            transaction_hashes: Blockchain transaction hashes
        """
        with self._lock:
            self.active_orders[order_id] = {
                'order_id': order_id,
                'coin': coin,
                'prediction': prediction,
                'cost': cost,
                'token_id': token_id,
                'start_price': start_price,
                'condition_id': condition_id,
                'shares': shares,
                'price': price,
                'market_slug': market_slug,
                'transaction_hashes': transaction_hashes or [],
                'timestamp': datetime.now().isoformat(),
                'status': 'open'
            }

        logger.info(f"Tracking order: {coin} {prediction} ${cost:.2f} @ {price:.3f} "
                     f"(ID: {order_id[:16]}..., market: {condition_id[:16] if condition_id else 'N/A'}...)")

    def get_active_orders(self) -> List[Dict]:
        with self._lock:
            return list(self.active_orders.values())

    def settle_and_save_trade(self, bet: dict, final_price: float, won: bool, profit: float) -> None:
        """
        Upsert a fully-settled trade record into trade_history.json.

        If a record with the same order_id already exists, update it in-place.
        Otherwise append a new complete record.

        Args:
            bet: The bet dict from current_round_bets (has all placement data)
            final_price: Final crypto price at market close
            won: True if trade won, False if lost
            profit: Profit/Loss in USDC
        """
        order_id = bet.get('order_id')
        settled_data = {
            'won': won,
            'final_price': final_price,
            'profit': profit,
            'status': 'settled',
            'settled_at': datetime.now().isoformat()
        }

        with self.history._lock:
            found = False
            if order_id:
                for i, t in enumerate(self.history.history):
                    if t.get('order_id') == order_id:
                        # Update existing record in-place (keeps original fill data)
                        self.history.history[i].update(settled_data)
                        # Attach arb metadata if present and not already saved
                        if bet.get('arb_metadata') and 'arb_metadata' not in self.history.history[i]:
                            self.history.history[i]['arb_metadata'] = bet['arb_metadata']
                        if bet.get('td_metadata') and 'td_metadata' not in self.history.history[i]:
                            self.history.history[i]['td_metadata'] = bet['td_metadata']
                        found = True
                        logger.info(f"Trade settled (updated existing): {bet.get('coin')} {bet.get('prediction')} "
                                    f"{'WON' if won else 'LOST'} ${profit:+.2f}")
                        break

            if not found:
                # No existing record — create a complete one from bet data
                trade_data = {
                    'order_id': order_id or '',
                    'coin': bet.get('coin', ''),
                    'prediction': bet.get('prediction', ''),
                    'price': bet.get('price', 0),
                    'cost': bet.get('cost', 0),
                    'shares': bet.get('shares', 0),
                    'token_id': bet.get('token_id', ''),
                    'condition_id': bet.get('condition_id', ''),
                    'start_price': bet.get('start_price', 0),
                    'market_slug': bet.get('market_slug', ''),
                    'transaction_hashes': bet.get('transaction_hashes', []),
                    'timestamp': bet.get('timestamp', datetime.now().isoformat()),
                }
                # Preserve arbitrage metadata for post-hoc profitability analysis
                if bet.get('arb_metadata'):
                    trade_data['arb_metadata'] = bet['arb_metadata']
                if bet.get('td_metadata'):
                    trade_data['td_metadata'] = bet['td_metadata']
                if bet.get('is_low_vol_lotto'):
                    trade_data['is_low_vol_lotto'] = True
                if bet.get('is_fallback'):
                    trade_data['is_fallback'] = True
                trade_data.update(settled_data)
                self.history.history.append(trade_data)
                logger.info(f"Trade settled (new record): {bet.get('coin')} {bet.get('prediction')} "
                            f"{'WON' if won else 'LOST'} ${profit:+.2f}")

            self.history._save_to_disk()

    def sync_trades_from_wallet(self, proxy_address: str) -> dict:
        """
        Comprehensive wallet sync: reconcile local history with on-chain data.

        Step 1: Settle unsettled local trades via closed-positions API
        Step 2: Discover missing trades via wallet activity API

        Args:
            proxy_address: The proxy/funder wallet address

        Returns:
            {'settled': N, 'discovered': N}
        """
        result = {'settled': 0, 'discovered': 0}

        # Step 1: Settle unsettled local trades
        closed_positions = self._fetch_closed_positions(proxy_address)
        closed_by_cid = {}
        for cp in closed_positions:
            cid = cp.get('conditionId', '')
            if cid:
                closed_by_cid[cid] = cp

        if closed_by_cid:
            logger.info(f"[WALLET SYNC] Fetched {len(closed_by_cid)} closed positions from Data API")

        with self.history._lock:
            unsettled = [
                (i, dict(t)) for i, t in enumerate(self.history.history)
                if t.get('won') is None
            ]

        if unsettled:
            logger.info(f"[WALLET SYNC] Found {len(unsettled)} unsettled local trades")

            for idx, trade in unsettled:
                cid = trade.get('condition_id', '')
                if not cid or cid not in closed_by_cid:
                    continue

                cp = closed_by_cid[cid]
                realized_pnl = float(cp.get('realizedPnl', 0))

                # realizedPnl > 0 means user profited (prediction was correct)
                won = realized_pnl > 0

                # Use realizedPnl directly from Data API — it's the actual P&L
                profit = realized_pnl

                with self.history._lock:
                    self.history.history[idx]['won'] = won
                    self.history.history[idx]['profit'] = profit
                    self.history.history[idx]['final_price'] = trade.get('start_price') or 0
                    self.history.history[idx]['status'] = 'settled'
                    self.history.history[idx]['settled_at'] = datetime.now().isoformat()
                    self.history.history[idx]['recovered_via'] = 'wallet_sync'
                    self.history._save_to_disk()

                coin = trade.get('coin', '?')
                prediction = trade.get('prediction', '?')
                result['settled'] += 1
                logger.info(f"[WALLET SYNC] Settled {coin} {prediction}: "
                            f"{'WON' if won else 'LOST'} ${profit:+.2f} (realizedPnl=${realized_pnl:.4f})")

        # Step 2: Discover missing trades from wallet activity
        activities = []
        try:
            activities = self._fetch_wallet_activity(proxy_address, activity_type='TRADE')
            if activities:
                # Build set of local condition_ids for dedup
                with self.history._lock:
                    local_cids = {t.get('condition_id') for t in self.history.history if t.get('condition_id')}

                for activity in activities:
                    act_cid = activity.get('conditionId', '')
                    if not act_cid or act_cid in local_cids:
                        continue

                    # Parse trade details from activity
                    title = activity.get('title', '') or activity.get('marketName', '')
                    outcome = activity.get('outcome', '') or activity.get('tokenName', '')
                    coin = self._parse_coin_from_title(title)
                    prediction = self._parse_prediction_from_activity(title, outcome)
                    # Fallback: use outcomeIndex (0=UP, 1=DOWN for Up-or-Down markets)
                    if not prediction and 'outcomeIndex' in activity:
                        prediction = 'UP' if activity['outcomeIndex'] == 0 else 'DOWN'

                    if not coin:
                        continue

                    # Check if we have closed position data for PnL
                    cp = closed_by_cid.get(act_cid)
                    realized_pnl = float(cp.get('realizedPnl', 0)) if cp else 0
                    won = realized_pnl > 0 if cp else None

                    cost = abs(float(activity.get('usdcSize', 0)))
                    price = float(activity.get('price', 0))
                    shares = cost / price if price > 0 else 0
                    # Use realizedPnl directly from Data API when available
                    profit = realized_pnl if cp else None

                    trade_data = {
                        'order_id': activity.get('transactionHash', ''),
                        'coin': coin,
                        'prediction': prediction or '?',
                        'price': price,
                        'cost': cost,
                        'shares': shares,
                        'token_id': activity.get('assetId', ''),
                        'condition_id': act_cid,
                        'start_price': 0,
                        'market_slug': activity.get('slug', ''),
                        'transaction_hashes': [activity.get('transactionHash', '')],
                        'timestamp': self._normalize_timestamp(activity.get('timestamp')),
                        'won': won,
                        'final_price': 0,
                        'profit': profit,
                        'status': 'settled' if won is not None else 'filled',
                        'source': 'wallet_discovered',
                    }
                    if won is not None:
                        trade_data['settled_at'] = datetime.now().isoformat()

                    with self.history._lock:
                        self.history.history.append(trade_data)
                        self.history._save_to_disk()
                        local_cids.add(act_cid)

                    result['discovered'] += 1
                    logger.info(f"[WALLET SYNC] Discovered {coin} {prediction or '?'}: "
                                f"${cost:.2f} (from wallet activity)")

        except Exception as e:
            logger.warning(f"[WALLET SYNC] Activity discovery failed (non-fatal): {e}")

        # Step 3: Repair prediction='?' trades using activity outcomeIndex
        try:
            repair_count = 0
            with self.history._lock:
                missing_pred = [
                    (i, dict(t)) for i, t in enumerate(self.history.history)
                    if t.get('prediction') == '?'
                ]
            if missing_pred and activities:
                # Build activity lookup by condition_id
                act_by_cid = {}
                for act in activities:
                    cid = act.get('conditionId', '')
                    if cid and cid not in act_by_cid:
                        act_by_cid[cid] = act
                for idx, trade in missing_pred:
                    cid = trade.get('condition_id', '')
                    if cid in act_by_cid:
                        act = act_by_cid[cid]
                        oi = act.get('outcomeIndex')
                        if oi is not None:
                            pred = 'UP' if oi == 0 else 'DOWN'
                            with self.history._lock:
                                self.history.history[idx]['prediction'] = pred
                            repair_count += 1
                if repair_count > 0:
                    with self.history._lock:
                        self.history._save_to_disk()
                    logger.info(f"[WALLET SYNC] Repaired prediction for {repair_count} trades")
        except Exception as e:
            logger.warning(f"[WALLET SYNC] Prediction repair failed (non-fatal): {e}")

        total = result['settled'] + result['discovered']
        if total > 0:
            logger.info(f"[WALLET SYNC] Complete: {result['settled']} settled, {result['discovered']} discovered")
        else:
            logger.info("[WALLET SYNC] No trades to reconcile — all clean")

        return result

    def _fetch_closed_positions(self, proxy_address: str) -> list:
        """Paginate through Data API /closed-positions endpoint."""
        all_positions = []
        offset = 0
        while True:
            try:
                resp = requests.get(f"{DATA_API}/closed-positions", params={
                    'user': proxy_address,
                    'limit': 50,
                    'offset': offset,
                }, timeout=15)
                if resp.status_code != 200:
                    logger.warning(f"[WALLET SYNC] Data API returned {resp.status_code}")
                    break
                batch = resp.json()
                if not batch:
                    break
                all_positions.extend(batch)
                offset += len(batch)
                if len(batch) < 50:
                    break
            except requests.exceptions.RequestException as e:
                logger.error(f"[WALLET SYNC] Data API request failed: {e}")
                break
        return all_positions

    def _fetch_wallet_activity(self, proxy_address: str, activity_type: str = 'TRADE') -> list:
        """Paginate through Data API /activity endpoint."""
        all_activities = []
        offset = 0
        while True:
            try:
                resp = requests.get(f"{DATA_API}/activity", params={
                    'user': proxy_address,
                    'type': activity_type,
                    'limit': 50,
                    'offset': offset,
                }, timeout=15)
                if resp.status_code != 200:
                    logger.warning(f"[WALLET SYNC] Activity API returned {resp.status_code}")
                    break
                batch = resp.json()
                if not batch:
                    break
                all_activities.extend(batch)
                offset += len(batch)
                if len(batch) < 50:
                    break
            except requests.exceptions.RequestException as e:
                logger.error(f"[WALLET SYNC] Activity API request failed: {e}")
                break
        return all_activities

    @staticmethod
    def _parse_coin_from_title(title: str) -> Optional[str]:
        """Extract coin symbol from market title. E.g. 'Will BTC be above...' -> 'BTC'"""
        if not title:
            return None
        title_upper = title.upper()
        for coin in ('BTC', 'ETH', 'SOL'):
            if coin in title_upper:
                return coin
        # Try longer names
        coin_map = {'BITCOIN': 'BTC', 'ETHEREUM': 'ETH', 'SOLANA': 'SOL'}
        for name, symbol in coin_map.items():
            if name in title_upper:
                return symbol
        return None

    @staticmethod
    def _parse_prediction_from_activity(title: str, outcome: str) -> Optional[str]:
        """Derive UP/DOWN from title + outcome."""
        if not outcome and not title:
            return None

        # Direct match: outcome is "Up" or "Down" (from tokenName or outcome field)
        if outcome:
            outcome_lower = outcome.strip().lower()
            if outcome_lower == 'up':
                return 'UP'
            elif outcome_lower == 'down':
                return 'DOWN'

        if not title:
            return None
        title_lower = title.lower()

        # Legacy: "above"/"below" + "yes"/"no" pattern
        outcome_lower = (outcome or '').strip().lower()
        is_above = 'above' in title_lower
        is_below = 'below' in title_lower
        is_yes = outcome_lower in ('yes',)
        is_no = outcome_lower in ('no',)

        if is_above and is_yes:
            return 'UP'
        elif is_above and is_no:
            return 'DOWN'
        elif is_below and is_yes:
            return 'DOWN'
        elif is_below and is_no:
            return 'UP'
        return None

    @staticmethod
    def _normalize_timestamp(ts) -> str:
        """Convert any timestamp format to ISO string."""
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts).isoformat()
        if isinstance(ts, str) and ts:
            return ts
        return datetime.now().isoformat()

    def clear_stale_orders(self, max_age_seconds: int = 1800) -> None:
        now = datetime.now()
        stale_orders = []

        with self._lock:
            for order_id, order_data in self.active_orders.items():
                order_time = datetime.fromisoformat(order_data['timestamp'])
                age = (now - order_time).total_seconds()

                if age > max_age_seconds:
                    stale_orders.append((order_id, age))

            for order_id, age in stale_orders:
                logger.warning(f"Removing stale order: {order_id[:16]}... (age: {age:.0f}s)")
                del self.active_orders[order_id]
