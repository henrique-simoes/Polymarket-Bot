#!/usr/bin/env python3
"""
Mode Profitability Analyzer — fetches last N hours of resolved BTC 15-minute
markets from Gamma API + Binance 1m candles, simulates what each mode (A-F)
would have done, and recommends the best mode.

Caches raw data (markets + candles) to data/mode_analysis_cache.json so
subsequent runs only fetch new data since last cache.

Usage:
    python scripts/analyze_best_mode.py --hours 6
    python scripts/analyze_best_mode.py --hours 6 --plain
"""

import argparse
import json
import logging
import os
import time as time_module
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import ccxt
import numpy as np
import requests
from scipy.stats import norm

logger = logging.getLogger("ModeAnalyzer")

GAMMA_API = "https://gamma-api.polymarket.com"
TAG_ID_15M = 102467
ASSUMED_VOL = {'BTC': 0.80, 'ETH': 0.90, 'SOL': 1.10}

# Trading constants — must match real bot thresholds
POLY_FEE = 0.0315          # 3.15% Polymarket fee on winning profit
MODE_A_SNIPE_WINDOW = 300  # Mode A snipe window (seconds) — pure_arbitrage.snipe_window
MODE_D_MIN_EDGE = 0.15     # 15% BS edge required for Mode D main — is_time_decay_opportunity
MODE_D_MAIN_WINDOW = 420   # Mode D default entry window (seconds)
MODE_D_FB_MAX_TIME = 200   # Late-game fallback max time — late_game_fallback.max_time_remaining
MODE_D_FB_MIN_PRICE = 0.80 # Late-game fallback min price — late_game_fallback.min_price
MODE_D_FB_MAX_PRICE = 0.85 # Late-game fallback max price — late_game_fallback.max_price
MODE_F_MAX_PRICE = 0.25    # Low-vol lotto max token price
MODE_F_MIN_VOL_RATIO = 1.5 # Low-vol lotto min vol ratio
MODE_F_WINDOW = 300        # Low-vol lotto entry window
PREDICTION_LOOKBACK_HOURS = 168  # 7 days of data for forward-looking prediction
CACHE_VERSION = 2               # Bump to force cache rebuild when format changes
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
CACHE_PATH = os.path.join(_DATA_DIR, 'mode_analysis_cache.json')


# ---------------------------------------------------------------------------
# Helper functions (from validate_win_rates.py)
# ---------------------------------------------------------------------------

def realized_vol(closes):
    """Annualized vol from 1-min closes."""
    if len(closes) < 3:
        return 0.80
    rets = np.diff(np.log(np.array(closes, dtype=float)))
    s = np.std(rets)
    if s == 0:
        return 0.80
    return float(s * np.sqrt(365.25 * 24 * 60))


def bs_prob_up(spot, strike, vol, secs_left):
    """BS probability spot > strike at expiry (binary option, d2 formula)."""
    if secs_left <= 0:
        return 1.0 if spot > strike else (0.0 if spot < strike else 0.5)
    T = secs_left / (365.25 * 24 * 3600)
    sig = vol * np.sqrt(T)
    if sig < 1e-12:
        return 1.0 if spot > strike else 0.0
    # d2 = (ln(S/K) - 0.5*σ²*T) / (σ√T)  — matches bot's calculate_fair_value()
    d2 = (np.log(spot / strike) - 0.5 * vol ** 2 * T) / sig
    return float(norm.cdf(d2))


# ---------------------------------------------------------------------------
# ModeAnalyzer
# ---------------------------------------------------------------------------

class ModeAnalyzer:
    """Analyzes recent resolved markets and simulates each trading mode."""

    def __init__(self, hours: int = 12, coin_slug: str = 'btc'):
        self.hours = hours
        self.coin_slug = coin_slug
        self.coin = coin_slug.upper()
        self.assumed_vol = ASSUMED_VOL.get(self.coin, 0.80)

    # -----------------------------------------------------------------------
    # Cache
    # -----------------------------------------------------------------------

    def _load_cache(self) -> Dict:
        try:
            with open(CACHE_PATH) as f:
                cache = json.load(f)
            if cache.get('version') != CACHE_VERSION:
                return {}  # Force rebuild on version mismatch
            return cache
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save_cache(self, cache: Dict):
        try:
            cache['version'] = CACHE_VERSION
            tmp = CACHE_PATH + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(cache, f)
            os.replace(tmp, CACHE_PATH)
        except OSError as e:
            logger.debug(f"Cache save failed: {e}")

    # -----------------------------------------------------------------------
    # Data fetching
    # -----------------------------------------------------------------------

    def _fetch_new_markets(self, since_str: str = '', fetch_hours: int = 0) -> List[Dict]:
        """Fetch resolved 15-min markets from Gamma API, newer than since_str."""
        all_markets = []
        offset = 0
        limit = 100
        hours = fetch_hours if fetch_hours > 0 else self.hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')

        while True:
            try:
                resp = requests.get(f"{GAMMA_API}/markets", params={
                    'tag_id': TAG_ID_15M,
                    'closed': 'true',
                    'order': 'endDate',
                    'ascending': 'false',
                    'limit': limit,
                    'offset': offset,
                }, timeout=15)
                resp.raise_for_status()
                markets = resp.json()

                if not markets:
                    break

                for m in markets:
                    slug = m.get('slug', '')
                    end_date = m.get('endDate', '')

                    if not slug.startswith(f'{self.coin_slug}-'):
                        continue

                    if end_date < cutoff_str:
                        return all_markets

                    # Skip already-cached markets
                    if since_str and end_date <= since_str:
                        return all_markets

                    try:
                        raw_prices = m.get('outcomePrices', '')
                        if isinstance(raw_prices, str):
                            prices = json.loads(raw_prices)
                        else:
                            prices = raw_prices
                        if not prices or len(prices) != 2:
                            continue
                        p0, p1 = float(prices[0]), float(prices[1])
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                        continue

                    if p0 > 0.5:
                        winner = 'UP'
                    elif p1 > 0.5:
                        winner = 'DOWN'
                    else:
                        continue

                    all_markets.append({
                        'conditionId': m.get('conditionId', ''),
                        'slug': slug,
                        'question': m.get('question', ''),
                        'endDate': end_date,
                        'startDate': m.get('startDate', ''),
                        'winner': winner,
                    })

                offset += limit
                if len(markets) < limit:
                    break

                time_module.sleep(0.15)

            except Exception as e:
                logger.warning(f"Gamma fetch error at offset {offset}: {e}")
                time_module.sleep(1)
                offset += limit

        return all_markets

    def _fetch_new_candles(self, since_ms: int = 0, fetch_hours: int = 0) -> List:
        """Fetch 1m candles from Binance, starting from since_ms (or hours+1h ago)."""
        exchange = ccxt.binance()
        symbol = f'{self.coin}/USDT'
        hours = fetch_hours if fetch_hours > 0 else self.hours
        if since_ms == 0:
            since_ms = int((datetime.now(timezone.utc) - timedelta(hours=hours + 1)).timestamp() * 1000)
        all_candles = []
        end = int(datetime.now(timezone.utc).timestamp() * 1000)

        while since_ms < end:
            try:
                candles = exchange.fetch_ohlcv(symbol, '1m', since=since_ms, limit=1000)
                if not candles:
                    break
                all_candles.extend(candles)
                since_ms = candles[-1][0] + 60000
                if len(candles) < 1000:
                    break
                time_module.sleep(0.2)
            except Exception as e:
                logger.warning(f"Binance fetch error: {e}")
                time_module.sleep(1)
                break

        return all_candles

    def _get_data_with_cache(self):
        """Load cache, fetch only new data, merge, prune old, save cache.

        Retains PREDICTION_LOOKBACK_HOURS (7 days) in cache for prediction.
        Returns (display_markets, all_markets_7d, candles_by_ts).
        display_markets is filtered to self.hours; all_markets_7d is full 7 days.
        """
        cache = self._load_cache()
        retention_hours = PREDICTION_LOOKBACK_HOURS
        retention_dt = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
        retention_str = retention_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        retention_ms = int(retention_dt.timestamp() * 1000)

        display_dt = datetime.now(timezone.utc) - timedelta(hours=self.hours)
        display_str = display_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        # --- Markets ---
        cached_markets = cache.get('markets', [])
        # Prune to 7-day retention window
        cached_markets = [m for m in cached_markets if m.get('endDate', '') >= retention_str]
        # Determine newest cached market
        newest_end = ''
        if cached_markets:
            newest_end = max(m['endDate'] for m in cached_markets)

        # Fetch only newer markets (full 7-day window)
        new_markets = self._fetch_new_markets(since_str=newest_end, fetch_hours=retention_hours)
        # Deduplicate by conditionId
        seen_ids = {m['conditionId'] for m in cached_markets}
        for m in new_markets:
            if m['conditionId'] not in seen_ids:
                cached_markets.append(m)
                seen_ids.add(m['conditionId'])

        # --- Candles ---
        cached_candles = cache.get('candles', [])
        # Prune to 7-day retention window
        cached_candles = [c for c in cached_candles if c[0] >= retention_ms]
        # Determine newest cached candle
        newest_ts = 0
        if cached_candles:
            newest_ts = max(c[0] for c in cached_candles)

        # Fetch only newer candles (full 7-day window)
        if newest_ts > 0:
            new_candles = self._fetch_new_candles(since_ms=newest_ts)
        else:
            new_candles = self._fetch_new_candles(fetch_hours=retention_hours)
        # Deduplicate by timestamp
        seen_ts = {c[0] for c in cached_candles}
        for c in new_candles:
            if c[0] not in seen_ts:
                cached_candles.append(c)
                seen_ts.add(c[0])

        # Save updated cache
        self._save_cache({
            'markets': cached_markets,
            'candles': cached_candles,
            'updated_utc': datetime.now(timezone.utc).isoformat(),
        })

        # Build candles lookup
        candles_by_ts = {}
        for c in cached_candles:
            candles_by_ts[c[0]] = {
                'open': c[1], 'high': c[2], 'low': c[3], 'close': c[4], 'volume': c[5]
            }

        # Split: display markets (self.hours) and full 7-day markets
        display_markets = [m for m in cached_markets if m.get('endDate', '') >= display_str]
        all_markets_7d = cached_markets

        return display_markets, all_markets_7d, candles_by_ts

    # -----------------------------------------------------------------------
    # Per-market analysis
    # -----------------------------------------------------------------------

    def analyze_market(self, market: Dict, candles_by_ts: Dict[int, Dict]) -> Dict:
        """Simulate what each mode would have done for a single resolved market."""
        end_str = market['endDate']
        try:
            end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        except ValueError:
            return {}

        end_ts = int(end_dt.timestamp())
        start_ts = end_ts - 900  # 15-minute window
        winner = market['winner']

        # Collect minute-by-minute spot prices during the window
        window_closes = []
        window_entries = []  # (secs_left, close_price)
        for minute_offset in range(15):
            ts_ms = (start_ts + minute_offset * 60) * 1000
            candle = candles_by_ts.get(ts_ms)
            if candle:
                window_closes.append(candle['close'])
                secs_left = 900 - minute_offset * 60
                window_entries.append((secs_left, candle['close']))

        if len(window_closes) < 3:
            return {}

        strike = window_closes[0]

        # Trailing 30 candles for realized vol (before this window)
        trailing_closes = []
        for i in range(30, 0, -1):
            ts_ms = (start_ts - i * 60) * 1000
            candle = candles_by_ts.get(ts_ms)
            if candle:
                trailing_closes.append(candle['close'])

        vol = realized_vol(trailing_closes) if len(trailing_closes) >= 10 else self.assumed_vol
        vol_ratio = self.assumed_vol / max(vol, 0.01)

        results = {
            'strike': strike,
            'winner': winner,
            'vol': vol,
            'vol_ratio': vol_ratio,
            'end_time': end_str,
        }

        # Mode A sub-profiles: each risk profile is simulated independently
        results['A-Lotto'] = self._sim_mode_a_lotto(window_entries, strike, vol, winner)
        results['A-Safe'] = self._sim_mode_a_safe(window_entries, strike, vol, winner)
        results['A-Any'] = self._sim_mode_a_any(window_entries, strike, vol, winner)

        # Mode D with sub-mode breakdown (main / fallback / lowvol)
        results['D_sub'] = self._sim_mode_d(window_entries, strike, vol, vol_ratio, winner)

        # Mode F standalone
        results['F'] = self._sim_mode_f(window_entries, strike, vol, vol_ratio, winner)

        return results

    # -----------------------------------------------------------------------
    # Mode A simulations — one per risk profile
    # -----------------------------------------------------------------------

    def _sim_mode_a_lotto(self, entries, strike, vol, winner) -> Dict:
        """Mode A + Lotto profile: buy cheap tokens (BS fair value ≤15¢).

        Lotto targets extreme mispricings where one side's token is very cheap.
        BS prob ≤ 0.15 means UP token is cheap → buy UP.
        BS prob ≥ 0.85 means DOWN token is cheap (1-prob ≤ 0.15) → buy DOWN.
        Asymmetric payoff: buy at 10¢, win → +$9.00, lose → -$1.00.
        Break-even win rate: ~10-15%.
        """
        for secs_left, spot in entries:
            if secs_left > MODE_A_SNIPE_WINDOW:
                continue
            prob = bs_prob_up(spot, strike, vol, secs_left)

            if prob <= 0.15:
                direction = 'UP'
                entry_price = prob
            elif prob >= 0.85:
                direction = 'DOWN'
                entry_price = 1.0 - prob
            else:
                continue

            if entry_price < 0.01:
                continue

            won = (direction == winner)
            pnl = (1.0 / entry_price - 1.0) * (1.0 - POLY_FEE) if won else -1.0
            return {
                'traded': True, 'direction': direction, 'entry_price': round(entry_price, 4),
                'secs_left': secs_left, 'won': won, 'pnl': round(pnl, 4),
            }

        return {'traded': False}

    def _sim_mode_a_safe(self, entries, strike, vol, winner) -> Dict:
        """Mode A + Safe profile: buy high-probability tokens (BS fair value ≥60¢).

        Safe targets tokens with ≥60% implied probability.
        BS prob ≥ 0.60 means UP token is ≥60¢ → buy UP.
        BS prob ≤ 0.40 means DOWN token is ≥60¢ (1-prob ≥ 0.60) → buy DOWN.
        Small payoff: buy at 75¢, win → +$0.33, lose → -$1.00.
        Break-even win rate: ~60-75%.
        """
        for secs_left, spot in entries:
            if secs_left > MODE_A_SNIPE_WINDOW:
                continue
            prob = bs_prob_up(spot, strike, vol, secs_left)

            if prob >= 0.60:
                direction = 'UP'
                entry_price = prob
            elif prob <= 0.40:
                direction = 'DOWN'
                entry_price = 1.0 - prob
            else:
                continue

            won = (direction == winner)
            pnl = (1.0 / entry_price - 1.0) * (1.0 - POLY_FEE) if won else -1.0
            return {
                'traded': True, 'direction': direction, 'entry_price': round(entry_price, 4),
                'secs_left': secs_left, 'won': won, 'pnl': round(pnl, 4),
            }

        return {'traded': False}

    def _sim_mode_a_any(self, entries, strike, vol, winner) -> Dict:
        """Mode A + Any profile: buy any token with ≥5% BS divergence from 50%.

        Trust Algorithm — no price filtering, enters on any edge ≥5%.
        BS prob ≥ 0.55 → buy UP.  BS prob ≤ 0.45 → buy DOWN.
        Entry prices range from 0.55 to ~1.0.
        """
        for secs_left, spot in entries:
            if secs_left > MODE_A_SNIPE_WINDOW:
                continue
            prob = bs_prob_up(spot, strike, vol, secs_left)
            if prob >= 0.55:
                direction = 'UP'
                entry_price = prob
            elif prob <= 0.45:
                direction = 'DOWN'
                entry_price = 1.0 - prob
            else:
                continue

            won = (direction == winner)
            pnl = (1.0 / entry_price - 1.0) * (1.0 - POLY_FEE) if won else -1.0
            return {
                'traded': True, 'direction': direction, 'entry_price': round(entry_price, 4),
                'secs_left': secs_left, 'won': won, 'pnl': round(pnl, 4),
            }

        return {'traded': False}

    # -----------------------------------------------------------------------
    # Mode D simulation — returns sub-mode breakdown
    # -----------------------------------------------------------------------

    def _sim_mode_d(self, entries, strike, vol, vol_ratio, winner) -> Dict:
        """Mode D: Time-Decay Sniper with fallback hierarchy.

        Returns a dict with three sub-mode results (mutually exclusive per market):
          'main':     BS ≥90% probability (≥15% edge over 75¢ market) with vol guard
          'fallback': Late-game 80-85¢ momentum at ≤200s (no vol guard)
          'lowvol':   Low-Vol Lotto auto-fallback (≤25¢ tokens, vol_ratio ≥ 1.5x)

        The bot tries main first, then fallback, then lowvol — first match wins.
        """
        result = {
            'main': {'traded': False},
            'fallback': {'traded': False},
            'lowvol': {'traded': False},
        }

        # --- 1. Main: BS ≥90% with vol-scaled distance guard ---
        # Bot requires ≥15% edge: BS prob ≥ 0.90 means market at ~0.75 → 15% edge
        # Entry price = realistic market price (BS prob minus the edge), clamped to 75-85¢
        min_distance = 0.005 * vol_ratio

        for secs_left, spot in entries:
            if secs_left > MODE_D_MAIN_WINDOW:
                continue

            distance = abs(spot - strike) / strike
            if distance < min_distance:
                continue

            prob = bs_prob_up(spot, strike, vol, secs_left)

            if prob >= (0.75 + MODE_D_MIN_EDGE):
                direction = 'UP'
                entry_price = max(0.75, min(prob - MODE_D_MIN_EDGE, 0.85))
                won = (direction == winner)
                pnl = (1.0 / entry_price - 1.0) * (1.0 - POLY_FEE) if won else -1.0
                result['main'] = {
                    'traded': True, 'direction': direction, 'entry_price': round(entry_price, 4),
                    'secs_left': secs_left, 'won': won, 'pnl': round(pnl, 4),
                    'vol_ratio': round(vol_ratio, 2),
                }
                return result

            down_prob = 1.0 - prob
            if down_prob >= (0.75 + MODE_D_MIN_EDGE):
                direction = 'DOWN'
                entry_price = max(0.75, min(down_prob - MODE_D_MIN_EDGE, 0.85))
                won = (direction == winner)
                pnl = (1.0 / entry_price - 1.0) * (1.0 - POLY_FEE) if won else -1.0
                result['main'] = {
                    'traded': True, 'direction': direction, 'entry_price': round(entry_price, 4),
                    'secs_left': secs_left, 'won': won, 'pnl': round(pnl, 4),
                    'vol_ratio': round(vol_ratio, 2),
                }
                return result

        # --- 2. Late-game fallback: 80-85¢ at ≤200s (no vol guard) ---
        for secs_left, spot in entries:
            if secs_left > MODE_D_FB_MAX_TIME:
                continue
            prob = bs_prob_up(spot, strike, vol, secs_left)
            if MODE_D_FB_MIN_PRICE <= prob <= MODE_D_FB_MAX_PRICE:
                direction = 'UP'
                entry_price = prob
                won = (direction == winner)
                pnl = (1.0 / entry_price - 1.0) * (1.0 - POLY_FEE) if won else -1.0
                result['fallback'] = {
                    'traded': True, 'direction': direction, 'entry_price': round(entry_price, 4),
                    'secs_left': secs_left, 'won': won, 'pnl': round(pnl, 4),
                    'is_fallback': True,
                }
                return result
            down_prob = 1.0 - prob
            if MODE_D_FB_MIN_PRICE <= down_prob <= MODE_D_FB_MAX_PRICE:
                direction = 'DOWN'
                entry_price = down_prob
                won = (direction == winner)
                pnl = (1.0 / entry_price - 1.0) * (1.0 - POLY_FEE) if won else -1.0
                result['fallback'] = {
                    'traded': True, 'direction': direction, 'entry_price': round(entry_price, 4),
                    'secs_left': secs_left, 'won': won, 'pnl': round(pnl, 4),
                    'is_fallback': True,
                }
                return result

        # --- 3. Low-Vol Lotto auto-fallback: ≤25¢ when vol_ratio ≥ 1.5x ---
        if vol_ratio >= MODE_F_MIN_VOL_RATIO:
            for secs_left, spot in entries:
                if secs_left > MODE_F_WINDOW:
                    continue
                prob = bs_prob_up(spot, strike, vol, secs_left)
                up_price = prob
                down_price = 1.0 - prob

                if up_price <= MODE_F_MAX_PRICE:
                    direction = 'UP'
                    entry_price = up_price
                elif down_price <= MODE_F_MAX_PRICE:
                    direction = 'DOWN'
                    entry_price = down_price
                else:
                    continue

                if entry_price < 0.01:
                    continue

                won = (direction == winner)
                pnl = (1.0 / entry_price - 1.0) * (1.0 - POLY_FEE) if won else -1.0
                result['lowvol'] = {
                    'traded': True, 'direction': direction, 'entry_price': round(entry_price, 4),
                    'secs_left': secs_left, 'won': won, 'pnl': round(pnl, 4),
                    'vol_ratio': round(vol_ratio, 2),
                }
                return result

        return result

    # -----------------------------------------------------------------------
    # Mode F simulation (unchanged)
    # -----------------------------------------------------------------------

    def _sim_mode_f(self, entries, strike, vol, vol_ratio, winner) -> Dict:
        """Mode F: Low-Vol Lotto — <=25¢ tokens when vol_ratio >= 1.5x."""
        if vol_ratio < MODE_F_MIN_VOL_RATIO:
            return {'traded': False, 'reason': 'vol_ratio < 1.5'}

        for secs_left, spot in entries:
            if secs_left > MODE_F_WINDOW:
                continue

            prob = bs_prob_up(spot, strike, vol, secs_left)
            up_price = prob
            down_price = 1.0 - prob

            if up_price <= MODE_F_MAX_PRICE:
                direction = 'UP'
                entry_price = up_price
            elif down_price <= MODE_F_MAX_PRICE:
                direction = 'DOWN'
                entry_price = down_price
            else:
                continue

            if entry_price < 0.01:
                continue

            won = (direction == winner)
            pnl = (1.0 / entry_price - 1.0) * (1.0 - POLY_FEE) if won else -1.0
            return {
                'traded': True, 'direction': direction, 'entry_price': round(entry_price, 4),
                'secs_left': secs_left, 'won': won, 'pnl': round(pnl, 4),
                'vol_ratio': round(vol_ratio, 2),
            }

        return {'traded': False}

    # -----------------------------------------------------------------------
    # Forward-Looking Prediction Engine
    # -----------------------------------------------------------------------

    def _tod_bucket(self, end_date_str: str) -> int:
        """Map an ISO timestamp to its 4-hour time-of-day bucket (0-5)."""
        try:
            dt = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            return dt.hour // 4
        except (ValueError, AttributeError):
            return 0

    def _forward_buckets(self, hours_ahead: int = 12) -> List:
        """Determine which ToD buckets the next hours_ahead spans and fraction each covers.

        Returns list of (bucket_id, fraction_of_period). E.g. if now=14:00 UTC:
        [(3, 2/12), (4, 4/12), (5, 4/12), (0, 2/12)]
        """
        now = datetime.now(timezone.utc)
        buckets = []
        remaining = hours_ahead * 3600  # seconds remaining to assign
        cursor = now

        while remaining > 0:
            bucket_id = cursor.hour // 4
            # End of this 4h bucket
            bucket_end_hour = (bucket_id + 1) * 4
            secs_to_bucket_end = (bucket_end_hour * 3600 - cursor.hour * 3600
                                  - cursor.minute * 60 - cursor.second)
            if secs_to_bucket_end <= 0:
                secs_to_bucket_end = 4 * 3600  # full bucket

            secs_in_bucket = min(remaining, secs_to_bucket_end)
            fraction = secs_in_bucket / (hours_ahead * 3600)
            buckets.append((bucket_id, fraction))

            remaining -= secs_in_bucket
            cursor = cursor + timedelta(seconds=secs_in_bucket)

        return buckets

    def _weighted_bucket_stats(self, trades: List[Dict], bucket_id: int,
                               half_life_hours: float = 48.0) -> Dict:
        """Compute recency-weighted stats for trades in a specific ToD bucket.

        Groups 7-day trades by 4-hour bucket. Applies exponential recency weighting:
            weight_i = exp(-ln(2) * age_hours_i / half_life)
        Returns dict with weighted trade count, win rate, avg P&L. None if <0.5 weighted trades.
        """
        now = datetime.now(timezone.utc)
        ln2 = 0.6931471805599453
        weighted_wins = 0.0
        weighted_total = 0.0
        weighted_pnl = 0.0

        for t in trades:
            t_bucket = self._tod_bucket(t.get('end_time', ''))
            if t_bucket != bucket_id:
                continue

            # Compute age in hours
            try:
                t_dt = datetime.fromisoformat(t['end_time'].replace('Z', '+00:00'))
                age_hours = (now - t_dt).total_seconds() / 3600
            except (ValueError, KeyError):
                age_hours = 168  # max age if unparseable

            weight = np.exp(-ln2 * age_hours / half_life_hours)
            weighted_total += weight
            if t.get('won'):
                weighted_wins += weight
            weighted_pnl += weight * t.get('pnl', 0)

        if weighted_total < 0.5:
            return None

        return {
            'weighted_trades': weighted_total,
            'win_rate': (weighted_wins / weighted_total * 100) if weighted_total > 0 else 0,
            'avg_pnl': weighted_pnl / weighted_total if weighted_total > 0 else 0,
        }

    def _compute_vol_adjustment(self, mode_trades_7d: List[Dict], current_vol_ratio: float,
                                mode_key: str) -> float:
        """Compare mode's win rate in similar vol conditions vs overall.

        Returns multiplier clamped to [0.5, 2.0].
        Falls back to directional priors if <5 trades in similar regime.
        """
        if not mode_trades_7d:
            return self._vol_prior(current_vol_ratio, mode_key)

        # Trades with similar vol ratio (within ±0.3)
        similar = [t for t in mode_trades_7d
                   if abs(t.get('vol_ratio', 1.0) - current_vol_ratio) <= 0.3]

        if len(similar) >= 5:
            overall_wr = sum(1 for t in mode_trades_7d if t.get('won')) / len(mode_trades_7d)
            similar_wr = sum(1 for t in similar if t.get('won')) / len(similar)
            if overall_wr > 0:
                ratio = similar_wr / overall_wr
                return max(0.5, min(2.0, ratio))
            return 1.0

        return self._vol_prior(current_vol_ratio, mode_key)

    def _vol_prior(self, vol_ratio: float, mode_key: str) -> float:
        """Directional prior when insufficient trades in current vol regime."""
        # Priors: (low_vol >=1.5, normal 0.8-1.5, high_vol <0.8)
        priors = {
            'D-Main':  (0.5, 1.0, 1.2),
            'D-FB':    (0.5, 1.0, 1.2),
            'D-LV':    (1.5, 0.0, 0.0),
            'F':       (1.5, 0.0, 0.0),
            'A-Lotto': (0.6, 1.0, 1.3),
            'A-Safe':  (1.2, 1.0, 0.8),
            'A-Any':   (0.8, 1.0, 1.1),
        }
        low, normal, high = priors.get(mode_key, (1.0, 1.0, 1.0))
        if vol_ratio >= 1.5:
            return low
        elif vol_ratio < 0.8:
            return high
        return normal

    def _compute_calibration(self) -> Dict:
        """Load real trade history and compute calibration corrections.

        Buckets actual trades by entry price range:
            lotto: price <= 0.20 → applies to A-Lotto, D-LV, F
            td_range: 0.60 <= price <= 0.90 → applies to A-Safe, D-Main, D-FB
            mid: 0.40 <= price < 0.60 → applies to A-Any
        Returns {} if <10 total trades.
        """
        all_trades = []
        for fname in ('trade_history.json', 'learning_trades.json'):
            fpath = os.path.join(_DATA_DIR, fname)
            try:
                with open(fpath) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    all_trades.extend(data)
            except (FileNotFoundError, json.JSONDecodeError):
                pass

        if len(all_trades) < 10:
            return {}

        # Bucket trades by entry price
        buckets = {'lotto': [], 'td_range': [], 'mid': []}
        for t in all_trades:
            price = t.get('entry_price', t.get('price', 0.5))
            if isinstance(price, str):
                try:
                    price = float(price)
                except ValueError:
                    continue
            if price <= 0.20:
                buckets['lotto'].append(t)
            elif 0.60 <= price <= 0.90:
                buckets['td_range'].append(t)
            elif 0.40 <= price < 0.60:
                buckets['mid'].append(t)

        calibration = {}
        for bucket_name, trades in buckets.items():
            if len(trades) < 5:
                continue
            wins = sum(1 for t in trades if t.get('won') or t.get('outcome') == 'win')
            actual_wr = wins / len(trades)
            actual_pnls = [t.get('pnl', 0) for t in trades if isinstance(t.get('pnl', 0), (int, float))]
            avg_pnl = sum(actual_pnls) / len(actual_pnls) if actual_pnls else 0
            calibration[bucket_name] = {
                'win_rate_adj': actual_wr - 0.5,  # additive correction
                'pnl_multiplier': 1.0,  # will be refined below
                'sample_size': len(trades),
            }
            # If avg P&L data meaningful, derive pnl multiplier vs expected
            if avg_pnl != 0:
                calibration[bucket_name]['avg_real_pnl'] = avg_pnl

        # Phantom trade bonus: check if rejected trades would have won often
        phantom_path = os.path.join(_DATA_DIR, 'phantom_trades.json')
        try:
            with open(phantom_path) as f:
                phantoms = json.load(f)
            if isinstance(phantoms, list) and len(phantoms) >= 10:
                won_count = sum(1 for p in phantoms if p.get('would_have_won'))
                phantom_wr = won_count / len(phantoms)
                if phantom_wr > 0.60:
                    calibration['_phantom_bonus'] = min(1.2, 0.8 + phantom_wr)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        return calibration

    def _compute_confidence(self, trades_7d: List[Dict], buckets_with_data: int,
                            total_forward_buckets: int, has_calibration: bool) -> float:
        """Weighted composite confidence score (0.0 - 1.0).

        40% sample size, 30% bucket coverage, 20% recency, 10% calibration bonus.
        """
        n = len(trades_7d)

        # Sample size: sigmoid centered at 25 trades
        sample_score = 1.0 / (1.0 + np.exp(-(n - 25) / 10))

        # Bucket coverage
        coverage_score = (buckets_with_data / total_forward_buckets) if total_forward_buckets > 0 else 0

        # Recency: fraction of trades from last 72h
        now = datetime.now(timezone.utc)
        recent_cutoff = now - timedelta(hours=72)
        recent_count = 0
        for t in trades_7d:
            try:
                t_dt = datetime.fromisoformat(t.get('end_time', '').replace('Z', '+00:00'))
                if t_dt >= recent_cutoff:
                    recent_count += 1
            except (ValueError, AttributeError):
                pass
        recency_score = (recent_count / n) if n > 0 else 0

        # Calibration bonus
        cal_score = 1.0 if has_calibration else 0.0

        confidence = 0.40 * sample_score + 0.30 * coverage_score + 0.20 * recency_score + 0.10 * cal_score
        return round(max(0.0, min(1.0, confidence)), 3)

    def _project_mode(self, mode_trades_7d: List[Dict], forward_buckets: List,
                      vol_adj: float, calibration: Dict, cal_bucket: str,
                      mode_key: str) -> Dict:
        """Per-mode forward projection using ToD-weighted historical performance.

        Returns {'pred_trades': float, 'pred_win_rate': float, 'pred_pnl': float, 'confidence': float}
        """
        if not mode_trades_7d or vol_adj == 0:
            return {'pred_trades': 0, 'pred_win_rate': 0, 'pred_pnl': 0, 'confidence': 0}

        total_pred_trades = 0.0
        total_pred_pnl = 0.0
        weighted_wr_sum = 0.0
        weighted_wr_denom = 0.0
        buckets_with_data = 0

        for bucket_id, fraction in forward_buckets:
            bstats = self._weighted_bucket_stats(mode_trades_7d, bucket_id)
            if bstats is None:
                continue

            buckets_with_data += 1
            # Scale bucket's 7-day stats to predict this fraction of 12h
            # 7-day bucket has data from 7 occurrences of this bucket; project for 1 occurrence × fraction
            bucket_trades = bstats['weighted_trades'] / 7.0 * fraction * (self.hours / 4.0)
            bucket_trades *= vol_adj

            # Apply phantom bonus to trade count
            phantom_bonus = calibration.get('_phantom_bonus', 1.0)
            if isinstance(phantom_bonus, (int, float)):
                bucket_trades *= phantom_bonus

            total_pred_trades += bucket_trades
            bucket_pnl = bucket_trades * bstats['avg_pnl']
            total_pred_pnl += bucket_pnl

            weighted_wr_sum += bstats['win_rate'] * bucket_trades
            weighted_wr_denom += bucket_trades

        # Apply calibration adjustments
        cal_data = calibration.get(cal_bucket, {})
        if cal_data:
            wr_adj = cal_data.get('win_rate_adj', 0)
            if weighted_wr_denom > 0:
                weighted_wr_sum += wr_adj * 100 * weighted_wr_denom  # additive to weighted average
            pnl_mult = cal_data.get('pnl_multiplier', 1.0)
            total_pred_pnl *= pnl_mult

        pred_wr = (weighted_wr_sum / weighted_wr_denom) if weighted_wr_denom > 0 else 0
        confidence = self._compute_confidence(
            mode_trades_7d, buckets_with_data, len(forward_buckets),
            has_calibration=bool(cal_data)
        )

        return {
            'pred_trades': round(total_pred_trades, 1),
            'pred_win_rate': round(pred_wr, 1),
            'pred_pnl': round(total_pred_pnl, 2),
            'confidence': confidence,
        }

    def _run_prediction(self, markets_7d: List[Dict], candles_by_ts: Dict,
                        current_vol_ratio: float, calibration: Dict) -> Dict:
        """Orchestrate forward-looking prediction for all modes.

        Simulates all 7-day markets (reuses analyze_market), collects per-mode
        trades with timestamps + vol_ratios, projects forward using ToD buckets.
        """
        # Simulate all 7-day markets
        mode_trades_7d = {
            'A-Lotto': [], 'A-Safe': [], 'A-Any': [],
            'D': [], 'D-Main': [], 'D-FB': [], 'D-LV': [],
            'F': [],
        }

        for market in markets_7d:
            result = self.analyze_market(market, candles_by_ts)
            if not result:
                continue

            end_time = result.get('end_time', market.get('endDate', ''))
            vol_ratio = result.get('vol_ratio', 1.0)

            # Mode A sub-profiles
            for sub in ['A-Lotto', 'A-Safe', 'A-Any']:
                r = result.get(sub)
                if r and r.get('traded'):
                    r['end_time'] = end_time
                    r.setdefault('vol_ratio', vol_ratio)
                    mode_trades_7d[sub].append(r)

            # Mode D sub-modes
            d_sub = result.get('D_sub', {})
            for sub_key, mode_key in [('main', 'D-Main'), ('fallback', 'D-FB'), ('lowvol', 'D-LV')]:
                r = d_sub.get(sub_key)
                if r and r.get('traded'):
                    r['end_time'] = end_time
                    r.setdefault('vol_ratio', vol_ratio)
                    mode_trades_7d[mode_key].append(r)
                    mode_trades_7d['D'].append(r)

            # Mode F
            r = result.get('F')
            if r and r.get('traded'):
                r['end_time'] = end_time
                r.setdefault('vol_ratio', vol_ratio)
                mode_trades_7d['F'].append(r)

        fwd_buckets = self._forward_buckets(hours_ahead=self.hours)

        # Calibration bucket mapping
        cal_map = {
            'A-Lotto': 'lotto', 'A-Safe': 'td_range', 'A-Any': 'mid',
            'D': 'td_range', 'D-Main': 'td_range', 'D-FB': 'td_range', 'D-LV': 'lotto',
            'F': 'lotto',
        }

        predictions = {}
        for mode_key, trades in mode_trades_7d.items():
            vol_adj = self._compute_vol_adjustment(trades, current_vol_ratio, mode_key)
            cal_bucket = cal_map.get(mode_key, 'mid')
            predictions[mode_key] = self._project_mode(
                trades, fwd_buckets, vol_adj, calibration, cal_bucket, mode_key
            )

        return predictions

    def _get_current_vol_ratio(self, candles_by_ts: Dict) -> float:
        """Compute current vol ratio from the latest 30 candles in the cache."""
        if not candles_by_ts:
            return 1.0
        sorted_ts = sorted(candles_by_ts.keys(), reverse=True)
        recent_closes = []
        for ts in sorted_ts[:30]:
            c = candles_by_ts[ts]
            recent_closes.append(c['close'])
        if len(recent_closes) < 10:
            return 1.0
        recent_closes.reverse()
        vol = realized_vol(recent_closes)
        return self.assumed_vol / max(vol, 0.01)

    # -----------------------------------------------------------------------
    # Training-data checks
    # -----------------------------------------------------------------------

    def _check_training_status(self) -> Dict:
        """Check ML training data availability for modes B, C, E."""
        status = {}

        rb_path = os.path.join(_DATA_DIR, 'replay_buffer.json')
        try:
            with open(rb_path) as f:
                rb = json.load(f)
            status['replay_buffer_size'] = len(rb) if isinstance(rb, list) else 0
        except (FileNotFoundError, json.JSONDecodeError):
            status['replay_buffer_size'] = 0
        status['ml_trained'] = status['replay_buffer_size'] >= 500

        lt_path = os.path.join(_DATA_DIR, 'learning_trades.json')
        try:
            with open(lt_path) as f:
                lt = json.load(f)
            lt_list = lt if isinstance(lt, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            lt_list = []
        status['learning_trades'] = len(lt_list)
        status['learning_complete'] = len(lt_list) >= 200

        td_count = sum(1 for t in lt_list if t.get('mode') == 'time_decay' or t.get('is_time_decay'))
        status['td_learning_trades'] = td_count
        status['td_trained'] = td_count >= 50

        return status

    # -----------------------------------------------------------------------
    # Recommendation algorithm
    # -----------------------------------------------------------------------

    def _recommend(self, mode_stats: Dict, training: Dict, avg_vol_ratio: float) -> Dict:
        """Generate recommendation based on simulation results and training status."""
        rec = {'mode': 'A', 'profile': None, 'reason': '', 'alternatives': []}

        # 1. Check if training data still needed
        if not training['learning_complete'] and not training['td_trained']:
            needed_c = 200 - training['learning_trades']
            needed_e = 50 - training['td_learning_trades']
            if needed_e <= needed_c:
                rec['mode'] = 'E'
                rec['reason'] = f"TD learning needs {needed_e} more trades (have {training['td_learning_trades']}/50)"
            else:
                rec['mode'] = 'C'
                rec['reason'] = f"Learning needs {needed_c} more trades (have {training['learning_trades']}/200)"
            return rec

        # 2. Find best A profile by total P&L (min 3 trades for lotto, 5 for others)
        a_profiles = [
            ('Lotto', mode_stats.get('A-Lotto', {}), 3),
            ('Safe', mode_stats.get('A-Safe', {}), 5),
            ('Any', mode_stats.get('A-Any', {}), 5),
        ]

        best_a_name = 'Any'
        best_a_stats = mode_stats.get('A-Any', {'trades': 0, 'total_pnl': -999})
        for name, stats, min_trades in a_profiles:
            if stats.get('trades', 0) >= min_trades and stats.get('total_pnl', -999) > best_a_stats.get('total_pnl', -999):
                best_a_name = name
                best_a_stats = stats

        # 3. Low-vol regime → recommend F
        if avg_vol_ratio >= 1.5:
            f_stats = mode_stats.get('F', {})
            rec['mode'] = 'F'
            rec['reason'] = f"Low-vol regime (avg ratio={avg_vol_ratio:.1f}x) — cheap tokens advantaged"
            if f_stats.get('trades', 0) == 0:
                rec['alternatives'].append("D (with auto Low-Vol Lotto fallback)")
            return rec

        # 4. Compare best A profile vs D (combined)
        d_stats = mode_stats.get('D', {})

        d_viable = d_stats.get('trades', 0) >= 3 and d_stats.get('win_rate', 0) >= 60
        a_viable = best_a_stats.get('trades', 0) >= 3 and best_a_stats.get('total_pnl', -999) > -10

        if d_viable and a_viable:
            if d_stats.get('total_pnl', 0) > best_a_stats.get('total_pnl', 0):
                rec['mode'] = 'D'
                rec['reason'] = (f"TD outperformed: {d_stats['win_rate']:.0f}% WR, "
                                 f"${d_stats['total_pnl']:+.2f} P&L vs A-{best_a_name} ${best_a_stats['total_pnl']:+.2f}")
            else:
                rec['mode'] = 'A'
                rec['profile'] = best_a_name
                rec['reason'] = (f"A-{best_a_name}: ${best_a_stats['total_pnl']:+.2f} P&L "
                                 f"(${best_a_stats['avg_pnl']:+.3f}/trade) vs TD ${d_stats['total_pnl']:+.2f}")
        elif d_viable:
            rec['mode'] = 'D'
            rec['reason'] = f"Time-Decay: {d_stats['win_rate']:.0f}% WR over {d_stats['trades']} trades"
        elif a_viable:
            rec['mode'] = 'A'
            rec['profile'] = best_a_name
            rec['reason'] = (f"A-{best_a_name}: {best_a_stats['win_rate']:.0f}% WR, "
                             f"${best_a_stats['total_pnl']:+.2f} P&L over {best_a_stats['trades']} trades")
        else:
            rec['mode'] = 'A'
            rec['profile'] = 'Any'
            rec['reason'] = "Insufficient opportunities for confident recommendation — defaulting to Arb"

        if training['ml_trained']:
            rec['alternatives'].append("B (ML trained, can enhance Arb)")

        return rec

    # -----------------------------------------------------------------------
    # Main analysis
    # -----------------------------------------------------------------------

    def _compute_stats(self, trades: List[Dict]) -> Dict:
        """Compute win/loss/P&L stats for a list of trade results."""
        if not trades:
            return {'trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'total_pnl': 0, 'avg_pnl': 0}
        wins = sum(1 for t in trades if t['won'])
        total_pnl = sum(t['pnl'] for t in trades)
        return {
            'trades': len(trades),
            'wins': wins,
            'losses': len(trades) - wins,
            'win_rate': (wins / len(trades) * 100) if trades else 0,
            'total_pnl': round(total_pnl, 4),
            'avg_pnl': round(total_pnl / len(trades), 4) if trades else 0,
        }

    def run_analysis(self) -> Dict:
        """Run full analysis: load cache, fetch new data, merge, analyze, save cache."""
        display_markets, all_markets_7d, candles_by_ts = self._get_data_with_cache()

        if not display_markets:
            return {'error': 'No resolved markets found', 'markets_analyzed': 0}
        if len(candles_by_ts) < 30:
            return {'error': 'Insufficient Binance candle data', 'markets_analyzed': 0}

        # Collect trades per sub-mode (display window only)
        mode_trades = {
            'A-Lotto': [], 'A-Safe': [], 'A-Any': [],
            'D': [], 'D-Main': [], 'D-FB': [], 'D-LV': [],
            'F': [],
        }
        vol_ratios = []

        for market in display_markets:
            result = self.analyze_market(market, candles_by_ts)
            if not result:
                continue

            if result.get('vol_ratio'):
                vol_ratios.append(result['vol_ratio'])

            # Mode A sub-profiles (each simulated independently per market)
            for sub in ['A-Lotto', 'A-Safe', 'A-Any']:
                r = result.get(sub)
                if r and r.get('traded'):
                    mode_trades[sub].append(r)

            # Mode D sub-modes (mutually exclusive per market)
            d_sub = result.get('D_sub', {})
            for sub_key, mode_key in [('main', 'D-Main'), ('fallback', 'D-FB'), ('lowvol', 'D-LV')]:
                r = d_sub.get(sub_key)
                if r and r.get('traded'):
                    mode_trades[mode_key].append(r)
                    mode_trades['D'].append(r)  # Also add to combined D total

            # Mode F standalone
            r = result.get('F')
            if r and r.get('traded'):
                mode_trades['F'].append(r)

        # Compute stats for all modes/sub-modes
        mode_stats = {}
        for mode, trades in mode_trades.items():
            mode_stats[mode] = self._compute_stats(trades)

        avg_vol_ratio = float(np.mean(vol_ratios)) if vol_ratios else 1.0
        training = self._check_training_status()
        recommendation = self._recommend(mode_stats, training, avg_vol_ratio)

        # Forward-looking prediction from 7-day data
        predictions = {}
        prediction_markets = len(all_markets_7d)
        if prediction_markets >= 48:  # At least ~1 day of data
            current_vr = self._get_current_vol_ratio(candles_by_ts)
            calibration = self._compute_calibration()
            predictions = self._run_prediction(all_markets_7d, candles_by_ts, current_vr, calibration)

            # Enhance recommendation if prediction strongly favors a different mode
            if predictions:
                self._enhance_recommendation_with_prediction(recommendation, predictions)

        return {
            'markets_analyzed': len(display_markets),
            'hours': self.hours,
            'coin': self.coin,
            'mode_stats': mode_stats,
            'avg_vol_ratio': round(avg_vol_ratio, 2),
            'training': training,
            'recommendation': recommendation,
            'predictions': predictions,
            'prediction_markets': prediction_markets,
        }

    def _enhance_recommendation_with_prediction(self, rec: Dict, predictions: Dict):
        """If prediction strongly favors a different mode, add as alternative."""
        rec_mode = rec['mode']
        # Find best predicted mode (top-level modes only)
        top_modes = ['A-Lotto', 'A-Safe', 'A-Any', 'D', 'F']
        mode_to_letter = {'A-Lotto': 'A', 'A-Safe': 'A', 'A-Any': 'A', 'D': 'D', 'F': 'F'}
        mode_to_profile = {'A-Lotto': 'Lotto', 'A-Safe': 'Safe', 'A-Any': 'Any'}

        best_pred = None
        best_pnl = -999
        for mk in top_modes:
            p = predictions.get(mk, {})
            if p.get('confidence', 0) >= 0.3 and p.get('pred_pnl', -999) > best_pnl:
                best_pnl = p['pred_pnl']
                best_pred = mk

        if best_pred:
            pred_letter = mode_to_letter.get(best_pred, best_pred)
            pred_profile = mode_to_profile.get(best_pred)
            # Only add alternative if it differs from current recommendation
            current_key = rec_mode
            if rec.get('profile'):
                current_key = f"{rec_mode}-{rec['profile']}"  # e.g. "A-Lotto"
            # Map rec to comparable key
            rec_comparable = f"A-{rec.get('profile', 'Any')}" if rec_mode == 'A' else rec_mode
            if best_pred != rec_comparable and best_pnl > 0:
                label = f"{pred_letter}"
                if pred_profile:
                    label += f" + {pred_profile}"
                label += f" (predicted ${best_pnl:+.2f})"
                if label not in rec.get('alternatives', []):
                    rec.setdefault('alternatives', []).append(label)

    # -----------------------------------------------------------------------
    # Display
    # -----------------------------------------------------------------------

    def display_results(self, results: Dict, use_rich: bool = True):
        """Print results as a rich table or plain text."""
        if results.get('error'):
            print(f"  Mode analysis: {results['error']}")
            return

        if use_rich:
            self._display_rich(results)
        else:
            self._display_plain(results)

    @staticmethod
    def _confidence_dots(confidence: float) -> str:
        """Render confidence as colored dots for rich display."""
        if confidence >= 0.7:
            return "[green]\u25cf\u25cf\u25cf[/green]"
        elif confidence >= 0.4:
            return "[yellow]\u25cf\u25cf[/yellow][dim]\u25cb[/dim]"
        elif confidence >= 0.15:
            return "[yellow]\u25cf[/yellow][dim]\u25cb\u25cb[/dim]"
        else:
            return "[dim]\u25cb\u25cb\u25cb[/dim]"

    @staticmethod
    def _confidence_dots_plain(confidence: float) -> str:
        """Render confidence as ASCII dots for plain display."""
        if confidence >= 0.7:
            return "***"
        elif confidence >= 0.4:
            return "**."
        elif confidence >= 0.15:
            return "*.."
        else:
            return "..."

    def _add_stats_row(self, table, label, stats, prediction=None, style=None, is_sub=False):
        """Add a row to a rich table for a given mode's stats + prediction."""
        trades = stats.get('trades', 0)
        pred = prediction or {}
        pred_trades = pred.get('pred_trades', 0)
        pred_pnl = pred.get('pred_pnl', 0)
        pred_conf = pred.get('confidence', 0)

        if trades == 0:
            row_style = "dim" if not is_sub else "dim italic"
            # Actual columns
            cols = [label, "0", "-", "-"]
            # Prediction columns
            if pred_trades > 0:
                pt_color = "green" if pred_pnl > 0 else "red"
                cols.extend([
                    f"~{pred_trades:.0f}",
                    f"[{pt_color}]${pred_pnl:+.2f}[/{pt_color}]",
                    self._confidence_dots(pred_conf),
                ])
            else:
                cols.extend(["-", "-", self._confidence_dots(pred_conf) if pred else "-"])
            table.add_row(*cols, style=row_style)
            return

        wr = stats['win_rate']
        wr_color = "green" if wr >= 60 else ("yellow" if wr >= 50 else "red")
        pnl = stats['total_pnl']
        pnl_color = "green" if pnl > 0 else "red"

        row_style = style or ("italic" if is_sub else None)
        # Actual columns
        cols = [
            label,
            str(trades),
            f"[{wr_color}]{wr:.0f}%[/{wr_color}]",
            f"[{pnl_color}]${pnl:+.2f}[/{pnl_color}]",
        ]
        # Prediction columns
        if pred_trades > 0:
            pt_color = "green" if pred_pnl > 0 else "red"
            cols.extend([
                f"~{pred_trades:.0f}",
                f"[{pt_color}]${pred_pnl:+.2f}[/{pt_color}]",
                self._confidence_dots(pred_conf),
            ])
        elif pred:
            cols.extend(["-", "-", self._confidence_dots(pred_conf)])
        else:
            cols.extend(["-", "-", "-"])

        table.add_row(*cols, style=row_style)

    def _display_rich(self, results: Dict):
        from rich.console import Console
        from rich.table import Table
        from rich import box

        con = Console()

        pred = results.get('predictions', {})
        pred_count = results.get('prediction_markets', 0)

        header = (f"\n[bold cyan]MODE PROFITABILITY ANALYSIS[/bold cyan]  "
                  f"({results['coin']}, last {results['hours']}h, "
                  f"{results['markets_analyzed']} markets")
        if pred:
            header += f" | prediction from 7d, {pred_count} markets"
        header += ")"
        con.print(header)

        table = Table(box=box.SIMPLE_HEAVY)
        # Actual columns
        table.add_column("Mode", style="bold")
        table.add_column("Trades", justify="right")
        table.add_column("WR", justify="right")
        table.add_column("P&L", justify="right")
        # Prediction columns
        table.add_column("~Trades", justify="right", style="dim")
        table.add_column("~P&L", justify="right", style="dim")
        table.add_column("Conf", justify="center", style="dim")

        ms = results['mode_stats']

        # --- Mode A sub-profiles ---
        self._add_stats_row(table, "A \u2014 Lotto (\u226415\u00a2)", ms.get('A-Lotto', {}),
                            prediction=pred.get('A-Lotto'))
        self._add_stats_row(table, "A \u2014 Safe  (\u226560\u00a2)", ms.get('A-Safe', {}),
                            prediction=pred.get('A-Safe'))
        self._add_stats_row(table, "A \u2014 Any   (\u226555\u00a2)", ms.get('A-Any', {}),
                            prediction=pred.get('A-Any'))

        # --- Mode D with sub-breakdown ---
        self._add_stats_row(table, "D (Time-Decay)", ms.get('D', {}),
                            prediction=pred.get('D'))
        self._add_stats_row(table, "  \u251c BS 75-85\u00a2", ms.get('D-Main', {}),
                            prediction=pred.get('D-Main'), is_sub=True)
        self._add_stats_row(table, "  \u251c Late-Game", ms.get('D-FB', {}),
                            prediction=pred.get('D-FB'), is_sub=True)
        self._add_stats_row(table, "  \u2514 Low-Vol Auto", ms.get('D-LV', {}),
                            prediction=pred.get('D-LV'), is_sub=True)

        # --- Mode F ---
        self._add_stats_row(table, "F (Low-Vol \u226425\u00a2)", ms.get('F', {}),
                            prediction=pred.get('F'))

        con.print(table)

        avg_vr = results['avg_vol_ratio']
        vr_label = "[red]LOW VOL[/red]" if avg_vr >= 1.5 else ("[yellow]MODERATE[/yellow]" if avg_vr >= 1.3 else "[green]NORMAL[/green]")
        con.print(f"  Vol Ratio: {avg_vr:.2f}x {vr_label}")

        tr = results['training']
        ml_status = "[green]trained[/green]" if tr['ml_trained'] else f"[yellow]{tr['replay_buffer_size']}/500[/yellow]"
        td_status = "[green]trained[/green]" if tr['td_trained'] else f"[yellow]{tr['td_learning_trades']}/50[/yellow]"
        con.print(f"  ML: {ml_status}  |  TD: {td_status}  |  Learning: {tr['learning_trades']}/200")

        rec = results['recommendation']
        mode_text = f"Mode {rec['mode']}"
        if rec.get('profile'):
            mode_text += f" + {rec['profile']}"
        con.print(f"\n  [bold green]>>> Recommended: {mode_text}[/bold green]  {rec['reason']}")
        for alt in rec.get('alternatives', []):
            con.print(f"      [dim]Alternative: Mode {alt}[/dim]")

        con.print()

    def _display_plain(self, results: Dict):
        pred = results.get('predictions', {})
        pred_count = results.get('prediction_markets', 0)

        header = (f"\nMODE PROFITABILITY ANALYSIS  "
                  f"({results['coin']}, last {results['hours']}h, "
                  f"{results['markets_analyzed']} markets")
        if pred:
            header += f" | prediction from 7d, {pred_count} markets"
        header += ")"
        print(header)
        print("-" * 88)

        ms = results['mode_stats']

        # Table rows: (label, stats_key, indent)
        rows = [
            ("A - Lotto (<=15c)", 'A-Lotto', False),
            ("A - Safe  (>=60c)", 'A-Safe', False),
            ("A - Any   (>=55c)", 'A-Any', False),
            ("D (Time-Decay)", 'D', False),
            ("  | BS 75-85c", 'D-Main', True),
            ("  | Late-Game", 'D-FB', True),
            ("  \\ Low-Vol Auto", 'D-LV', True),
            ("F (Low-Vol <=25c)", 'F', False),
        ]

        # Header with actual + prediction columns
        print(f"{'Mode':<22} {'Trades':>6} {'WR':>6} {'P&L':>10}   {'~Trades':>7} {'~P&L':>8} {'Conf':>4}")
        for label, key, is_sub in rows:
            stats = ms.get(key, {})
            p = pred.get(key, {})
            trades = stats.get('trades', 0)

            # Actual columns
            if trades == 0:
                actual = f"{label:<22} {'0':>6} {'-':>6} {'-':>10}"
            else:
                actual = (f"{label:<22} {trades:>6} "
                          f"{stats['win_rate']:>5.0f}% ${stats['total_pnl']:>+8.2f}")

            # Prediction columns
            pt = p.get('pred_trades', 0)
            pp = p.get('pred_pnl', 0)
            pc = p.get('confidence', 0)
            if pt > 0:
                pred_str = f"   ~{pt:>5.0f} ${pp:>+7.2f} {self._confidence_dots_plain(pc):>4}"
            elif p:
                pred_str = f"   {'-':>7} {'-':>8} {self._confidence_dots_plain(pc):>4}"
            else:
                pred_str = f"   {'-':>7} {'-':>8} {'-':>4}"

            print(actual + pred_str)

        print(f"\n  Vol Ratio: {results['avg_vol_ratio']:.2f}x")

        tr = results['training']
        print(f"  ML: {tr['replay_buffer_size']}/500  |  "
              f"TD: {tr['td_learning_trades']}/50  |  "
              f"Learning: {tr['learning_trades']}/200")

        rec = results['recommendation']
        mode_text = f"Mode {rec['mode']}"
        if rec.get('profile'):
            mode_text += f" + {rec['profile']}"
        print(f"\n  >>> Recommended: {mode_text}  {rec['reason']}")
        for alt in rec.get('alternatives', []):
            print(f"      Alternative: Mode {alt}")
        print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Analyze best trading mode from recent market data')
    parser.add_argument('--hours', type=int, default=12, help='Hours of history to analyze (default: 12)')
    parser.add_argument('--plain', action='store_true', help='Plain text output (no rich formatting)')
    parser.add_argument('--coin', default='btc', help='Coin slug to analyze (default: btc)')
    args = parser.parse_args()

    analyzer = ModeAnalyzer(hours=args.hours, coin_slug=args.coin)
    results = analyzer.run_analysis()
    analyzer.display_results(results, use_rich=not args.plain)


if __name__ == '__main__':
    main()
