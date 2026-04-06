"""
Price Arbitrage Detector - Compares Polymarket vs Implied Fair Value
Detects mispricing using simplified Black-Scholes for Binary Options.
Specialized for Late-Window Latency Arbitrage.
"""

import time
import math
import logging
from typing import Dict, Optional
from scipy.stats import norm

logger = logging.getLogger("ArbitrageDetector")

class PriceArbitrageDetector:
    """
    Detects when Polymarket prices deviate from 'Fair Value'
    calculated from Spot Price, Strike (Start) Price, and Time Remaining.
    """

    def __init__(self, config: dict, price_feed=None):
        self.config = config
        self.exchange_prices = {}
        self.price_feed = price_feed

        # Annualized Volatility estimates (can be dynamic later)
        # Crypto is volatile: 80% to 150% annualized is standard
        self.volatility = {'BTC': 0.80, 'ETH': 0.90, 'SOL': 1.10}

        # Realized volatility: Updated each round from 1h candles
        self.realized_volatility = {}

        # Get snipe window from config (default 300s = 5 minutes)
        arb_config = config.get('pure_arbitrage', {})
        self.snipe_window = arb_config.get('snipe_window', 300)

        # Dynamic Window Configuration (NEW)
        # Allows earlier entry when edge is larger
        dynamic_window = config.get('dynamic_entry_window', {})
        self.dynamic_window_enabled = dynamic_window.get('enabled', True)

        # Edge thresholds and corresponding max entry times (in seconds before expiry)
        # Higher edge = can enter earlier
        self.edge_window_tiers = dynamic_window.get('tiers', [
            {'min_edge': 0.20, 'max_time': 720},  # 20%+ edge: enter up to 12 min before
            {'min_edge': 0.15, 'max_time': 600},  # 15%+ edge: enter up to 10 min before
            {'min_edge': 0.10, 'max_time': 480},  # 10%+ edge: enter up to 8 min before
            {'min_edge': 0.07, 'max_time': 360},  # 7%+ edge: enter up to 6 min before
            {'min_edge': 0.05, 'max_time': 300},  # 5%+ edge: enter up to 5 min before (default)
        ])

        # Minimum edge required regardless of time
        self.min_edge_threshold = dynamic_window.get('min_edge_threshold', 0.05)

        window_desc = "Dynamic" if self.dynamic_window_enabled else f"Fixed {self.snipe_window}s"
        logger.info(f"Arbitrage Detector initialized (Fair Value Mode, {window_desc} window)")

    def _sync_prices(self):
        """Copy latest prices from the shared RealtimePriceFeed into self.exchange_prices."""
        if not self.price_feed:
            return
        for coin in ['BTC', 'ETH', 'SOL']:
            data = self.price_feed.get_price_with_timestamp(coin)
            if data:
                self.exchange_prices[coin] = data

    def start_price_feeds(self, coins: list):
        """No-op: prices now come from shared RealtimePriceFeed."""
        logger.info(f"Arbitrage detector using shared price feed for: {coins}")

    def stop_price_feeds(self):
        """No-op: shared price feed lifecycle managed by bot."""
        pass

    def update_realized_volatility(self, coin: str, realized_vol: float):
        """Update realized volatility for vol-scaled distance guard."""
        self.realized_volatility[coin] = realized_vol

    def get_dynamic_window(self, edge: float) -> int:
        """
        Calculate the maximum allowed entry time based on edge size.
        Higher edge = can enter earlier in the round.

        Args:
            edge: Absolute edge value (e.g., 0.15 for 15%)

        Returns:
            Maximum time remaining (in seconds) to allow entry
        """
        if not self.dynamic_window_enabled:
            return self.snipe_window

        abs_edge = abs(edge)

        # Find the appropriate tier based on edge
        for tier in self.edge_window_tiers:
            if abs_edge >= tier['min_edge']:
                return tier['max_time']

        # Default to base snipe window if edge is below all thresholds
        return self.snipe_window

    def calculate_fair_value(self, coin: str, strike_price: float, time_remaining_seconds: float) -> float:
        """
        Calculate theoretical probability P(Spot > Strike)
        Model: Binary Call Option (Cash-or-Nothing) using Black-Scholes assumptions
        """
        self._sync_prices()
        if coin not in self.exchange_prices:
            return 0.5 # No data = 50/50 uncertainty
            
        current_spot = self.exchange_prices[coin]['price']
        
        # 1. Edge Case: Expired
        if time_remaining_seconds <= 0:
            return 1.0 if current_spot > strike_price else 0.0

        # 2. Volatility Scaling — prefer realized vol over hardcoded assumed vol
        sigma = self.realized_volatility.get(coin, self.volatility.get(coin, 0.8))
        t_years = time_remaining_seconds / 31536000.0 # 365 * 24 * 60 * 60
        
        # 3. Calculation
        try:
            # Standard Binary Option Formula
            # d2 = (ln(S/K) + (r - 0.5*sigma^2)t) / (sigma * sqrt(t))
            # Assuming r=0 (short timeframe)
            
            vol_sqrt_t = sigma * math.sqrt(t_years)
            
            if vol_sqrt_t == 0:
                return 1.0 if current_spot > strike_price else 0.0
                
            # Log-return distance
            d2 = (math.log(current_spot / strike_price) - (0.5 * sigma**2 * t_years)) / vol_sqrt_t
            
            # CDF
            prob = norm.cdf(d2)
            return prob
            
        except Exception as e:
            # Fallback for math errors (e.g., strike=0)
            return 0.5

    def check_arbitrage(self, coin: str, polymarket_price: float,
                       strike_price: float, time_remaining: float) -> Optional[Dict]:
        """
        Check if Polymarket price deviates significantly from Fair Value.
        Returns dict with details regardless of opportunity status for UI visibility.
        """
        self._sync_prices()
        # Get current spot price for debug logging
        current_spot = self.exchange_prices.get(coin, {}).get('price', 0) if coin in self.exchange_prices else 0

        # Always calculate logic, filter later
        fair_prob = self.calculate_fair_value(coin, strike_price, time_remaining)

        # Edge Calculation
        diff = fair_prob - polymarket_price

        # CRITICAL DEBUG: Show all calculation details
        logger.info(f"\n{'='*60}")
        logger.info(f"[ARBITRAGE DEBUG] {coin}:")
        logger.info(f"  Current Spot:        ${current_spot:,.2f}")
        logger.info(f"  Strike Price:        ${strike_price:,.2f}")
        logger.info(f"  Spot vs Strike:      {'ABOVE' if current_spot > strike_price else 'BELOW'} (Spot {'+' if current_spot > strike_price else ''}{((current_spot - strike_price)/strike_price)*100:.2f}%)")
        logger.info(f"  Fair Prob (calc):    {fair_prob:.3f} ({fair_prob*100:.1f}%)")
        logger.info(f"  Polymarket Price:    {polymarket_price:.3f} ({polymarket_price*100:.1f}%) [This is YES token price]")
        logger.info(f"  Diff (Fair - Poly):  {diff:+.3f} ({diff*100:+.1f}%)")
        logger.info(f"  Time Remaining:      {time_remaining:.0f}s ({time_remaining/60:.1f}m)")

        # Dynamic Threshold
        # We accept smaller edges as time runs out because certainty increases
        base_threshold = self.min_edge_threshold

        opportunity = False
        direction = None

        # DYNAMIC WINDOW: Calculate allowed entry time based on edge size
        abs_edge = abs(diff)
        dynamic_window = self.get_dynamic_window(abs_edge)
        in_window = (time_remaining <= dynamic_window)

        # Log dynamic window decision
        if self.dynamic_window_enabled:
            logger.info(f"  Dynamic Window:      {dynamic_window}s ({dynamic_window/60:.1f}m) for {abs_edge*100:.1f}% edge")

        if in_window:
            # Vol-scaled distance guard: reject if price too close to strike
            # Formula: min_distance = 0.005 * (assumed_vol / max(realized_vol, 0.01))
            # Low vol → bigger distance needed (harder for price to move)
            # High vol → smaller distance OK (price moves easily)
            assumed_vol = self.volatility.get(coin, 0.8)
            realized_vol = self.realized_volatility.get(coin, assumed_vol)
            vol_ratio = assumed_vol / max(realized_vol, 0.01)
            min_distance_pct = 0.005 * vol_ratio  # Base 0.5% scaled by vol ratio

            vol_guard_rejected = False
            if current_spot > 0 and strike_price > 0:
                actual_distance = abs(current_spot - strike_price) / strike_price
                if actual_distance < min_distance_pct:
                    vol_guard_rejected = True
                    logger.info(f"  → VOL GUARD: Distance {actual_distance*100:.3f}% < min {min_distance_pct*100:.3f}% "
                               f"(vol_ratio={vol_ratio:.2f}, assumed={assumed_vol:.2f}, realized={realized_vol:.2f})")

            if vol_guard_rejected:
                logger.info(f"  → NO SIGNAL: Vol guard rejected (price too close to strike)")
            elif diff > base_threshold:
                # Undervalued: Fair=0.8, Poly=0.6 -> Buy UP
                opportunity = True
                direction = "UP"
                logger.info(f"  → SIGNAL: BUY UP (YES token) - Fair value HIGHER than market price")
                logger.info(f"     Reasoning: Fair={fair_prob:.3f} > Poly={polymarket_price:.3f}, diff={diff:.3f} > threshold={base_threshold}")
                logger.info(f"     Entry Window: {time_remaining:.0f}s remaining (allowed up to {dynamic_window}s)")
            elif diff < -base_threshold:
                # Overvalued: Fair=0.2, Poly=0.4 -> Buy DOWN
                opportunity = True
                direction = "DOWN"
                logger.info(f"  → SIGNAL: BUY DOWN (NO token) - Fair value LOWER than market price")
                logger.info(f"     Reasoning: Fair={fair_prob:.3f} < Poly={polymarket_price:.3f}, diff={diff:.3f} < -threshold={-base_threshold}")
                logger.info(f"     Entry Window: {time_remaining:.0f}s remaining (allowed up to {dynamic_window}s)")
            else:
                logger.info(f"  → NO SIGNAL: Diff {diff:.3f} within threshold ±{base_threshold}")
        else:
            logger.info(f"  → OUTSIDE WINDOW: time_remaining={time_remaining:.0f}s > dynamic_window={dynamic_window}s (edge={abs_edge*100:.1f}%)")

        logger.info(f"{'='*60}\n")

        return {
            'opportunity': opportunity,
            'direction': direction,
            'fair_value': fair_prob,
            'poly_price': polymarket_price,
            'diff': diff * 100, # Percentage for UI
            'time_left': time_remaining,
            # NEW: Dynamic window info for ML learning
            'dynamic_window_used': dynamic_window,
            'edge_at_entry': abs_edge,
            'entry_timing_ratio': time_remaining / 900.0,  # Normalized (0-1 where 1=full 15min)
        }