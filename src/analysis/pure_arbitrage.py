"""
Pure Arbitrage Detector - Simple, proven arbitrage strategies
No ML, no Black-Scholes, just mathematical edges

Strategies:
1. Binary Complement Arbitrage: YES + NO < $1.00 (guaranteed profit)
2. Spot Price Arbitrage: Current price vs strike price discrepancy
3. Extreme Mispricing: Obvious outcomes priced wrong
"""

import time
import logging
from typing import Dict, Optional

logger = logging.getLogger("PureArbitrage")

class PureArbitrageDetector:
    """
    Detects pure arbitrage opportunities without theoretical models.
    Focuses on proven strategies that extracted $40M+ from Polymarket.
    """

    def __init__(self, config: dict, price_feed=None):
        self.config = config
        self.exchange_prices = {}  # Real-time Binance prices
        self.price_feed = price_feed

        # Configuration
        arb_config = config.get('pure_arbitrage', {})

        # Strategy 1: Binary complement arbitrage
        self.enable_complement_arb = arb_config.get('complement_arbitrage', True)
        self.complement_threshold = arb_config.get('complement_threshold', 0.98)  # YES+NO < 0.98

        # Strategy 2: Spot price arbitrage
        self.enable_spot_arb = arb_config.get('spot_arbitrage', True)
        self.spot_buffer_pct = arb_config.get('spot_buffer_pct', 0.5)  # 0.5% buffer
        self.min_edge_pct = arb_config.get('min_edge_pct', 5.0)  # 5% minimum edge

        # Strategy 3: Extreme mispricing (lotto strategy)
        self.enable_lotto = arb_config.get('lotto_strategy', True)
        self.lotto_max_price = arb_config.get('lotto_max_price', 0.25)  # <25 cents
        self.lotto_min_edge_pct = arb_config.get('lotto_min_edge_pct', 5.0)  # 5% EV threshold

        # Fee awareness
        self.max_fee_pct = arb_config.get('max_fee_pct', 3.15)  # Polymarket peak fee

        # Timing
        self.snipe_window_seconds = arb_config.get('snipe_window', 300)  # Last 5 minutes

        logger.info("Pure Arbitrage Detector initialized")
        logger.info(f"  Complement Arb: {self.enable_complement_arb} (threshold: {self.complement_threshold})")
        logger.info(f"  Spot Arb: {self.enable_spot_arb} (buffer: {self.spot_buffer_pct}%, min edge: {self.min_edge_pct}%)")
        logger.info(f"  Lotto Strategy: {self.enable_lotto} (max price: ${self.lotto_max_price}, min edge: {self.lotto_min_edge_pct}%)")

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
        logger.info(f"Pure arbitrage detector using shared price feed for: {coins}")

    def stop_price_feeds(self):
        """No-op: shared price feed lifecycle managed by bot."""
        pass

    def check_complement_arbitrage(self, yes_price: float, no_price: float) -> Optional[Dict]:
        """
        Strategy 1: Binary Complement Arbitrage
        If YES + NO < $1.00, buying both guarantees profit

        Example: YES=$0.48, NO=$0.48, Sum=$0.96
        Buy both for $0.96, market resolves to $1.00 → Profit $0.04 (4.2%)

        This strategy extracted $39.5M+ from Polymarket (proven)
        """
        if not self.enable_complement_arb:
            return None

        total = yes_price + no_price

        if total < self.complement_threshold:
            edge_pct = ((1.0 - total) / total) * 100

            # Account for fees (conservative estimate)
            fee_cost = self.max_fee_pct * 2  # Buying both sides
            net_edge = edge_pct - fee_cost

            if net_edge > 0:
                logger.info(f"[COMPLEMENT ARB] YES=${yes_price:.3f} + NO=${no_price:.3f} = ${total:.3f}")
                logger.info(f"  Edge: {edge_pct:.2f}% - Fees: {fee_cost:.2f}% = Net: {net_edge:.2f}%")

                return {
                    'strategy': 'complement',
                    'opportunity': True,
                    'direction': 'BOTH',  # Buy both YES and NO
                    'edge_pct': net_edge,
                    'diff': net_edge,  # Alias for bot compatibility
                    'yes_price': yes_price,
                    'no_price': no_price,
                    'total': total
                }

        return None

    def check_spot_arbitrage(self, coin: str, strike_price: float,
                            yes_price: float, no_price: float,
                            time_remaining: float) -> Optional[Dict]:
        """
        Strategy 2: Spot Price Arbitrage
        If current spot price is clearly above/below strike, market should reflect this

        Example: BTC spot=$100,000, strike=$99,000, YES=$0.60
        BTC is already $1,000 above strike → YES should be ~0.90+
        Opportunity: Buy YES at $0.60 (underpriced)
        """
        if not self.enable_spot_arb:
            return None

        self._sync_prices()
        if coin not in self.exchange_prices:
            return None

        current_spot = self.exchange_prices[coin]['price']

        # Calculate how far current price is from strike
        pct_diff = ((current_spot - strike_price) / strike_price) * 100

        # Only consider if we're in snipe window (last 5 minutes)
        if time_remaining > self.snipe_window_seconds:
            return None

        # Determine if there's a clear directional edge
        direction = None
        expected_price = None
        actual_price = None

        if pct_diff > self.spot_buffer_pct:
            # Spot is ABOVE strike → YES should be high
            direction = "UP"
            actual_price = yes_price
            # As time approaches expiry, if spot > strike, YES → 1.0
            time_factor = 1.0 - (time_remaining / self.snipe_window_seconds)
            expected_price = 0.5 + (0.4 * time_factor) + min(pct_diff / 100, 0.1)

        elif pct_diff < -self.spot_buffer_pct:
            # Spot is BELOW strike → NO should be high
            direction = "DOWN"
            actual_price = no_price
            time_factor = 1.0 - (time_remaining / self.snipe_window_seconds)
            expected_price = 0.5 + (0.4 * time_factor) + min(abs(pct_diff) / 100, 0.1)

        if direction and expected_price and actual_price:
            edge_pct = ((expected_price - actual_price) / actual_price) * 100

            # Only flag if edge exceeds minimum threshold + fees
            net_edge = edge_pct - self.max_fee_pct

            if net_edge > self.min_edge_pct:
                logger.info(f"[SPOT ARB] {coin}: Spot=${current_spot:,.2f} vs Strike=${strike_price:,.2f}")
                logger.info(f"  Diff: {pct_diff:+.2f}% → {direction}")
                logger.info(f"  Expected: {expected_price:.3f}, Actual: {actual_price:.3f}")
                logger.info(f"  Edge: {edge_pct:.2f}% - Fees: {self.max_fee_pct:.2f}% = Net: {net_edge:.2f}%")

                return {
                    'strategy': 'spot_arbitrage',
                    'opportunity': True,
                    'direction': direction,
                    'edge_pct': net_edge,
                    'diff': net_edge,  # Alias for bot compatibility
                    'current_spot': current_spot,
                    'strike_price': strike_price,
                    'pct_from_strike': pct_diff,
                    'expected_price': expected_price,
                    'actual_price': actual_price
                }

        return None

    def check_lotto_strategy(self, coin: str, strike_price: float,
                            yes_price: float, no_price: float,
                            time_remaining: float) -> Optional[Dict]:
        """
        Strategy 3: Lotto Strategy (Extreme Mispricing)
        Buy low-probability bets (<15 cents) when there's directional evidence

        Favorable asymmetry:
        - Buy at $0.10 → Win $0.90 profit (9x) vs Lose $0.10 (1x)
        - Only need 10.2% win rate (including fees) to profit

        Example: BTC spot moving up fast, YES=$0.12
        If momentum suggests >20% chance of continuing up → Buy YES
        """
        if not self.enable_lotto:
            return None

        self._sync_prices()
        if coin not in self.exchange_prices:
            return None

        current_spot = self.exchange_prices[coin]['price']
        pct_diff = ((current_spot - strike_price) / strike_price) * 100

        # Only consider in snipe window
        if time_remaining > self.snipe_window_seconds:
            return None

        direction = None
        actual_price = None

        # Check if YES is lotto-priced and spot suggests UP
        if yes_price <= self.lotto_max_price and pct_diff > 0:
            direction = "UP"
            actual_price = yes_price

        # Check if NO is lotto-priced and spot suggests DOWN
        elif no_price <= self.lotto_max_price and pct_diff < 0:
            direction = "DOWN"
            actual_price = no_price

        if direction and actual_price:
            # Calculate if edge exists
            # Implied probability from price
            implied_prob = actual_price * 100

            # Rough estimate: if spot is moving in our direction, add probability
            prob_boost = min(abs(pct_diff) * 2, 20)  # Up to 20% boost
            estimated_true_prob = implied_prob + prob_boost

            # EV-based edge: P(win) × payout_after_fee - P(loss)
            est_prob = estimated_true_prob / 100.0
            fee_rate = self.max_fee_pct / 100.0
            ev_pct = (est_prob * (1.0 / actual_price - 1.0) * (1.0 - fee_rate)
                      - (1.0 - est_prob)) * 100.0

            is_opportunity = ev_pct > self.lotto_min_edge_pct

            if is_opportunity:
                logger.info(f"[LOTTO] {coin}: {direction} at ${actual_price:.3f} (<${self.lotto_max_price:.2f})")
                logger.info(f"  Spot: ${current_spot:,.2f} vs Strike: ${strike_price:,.2f} ({pct_diff:+.2f}%)")
                logger.info(f"  Implied: {implied_prob:.1f}%, Estimated: {estimated_true_prob:.1f}%")
                logger.info(f"  EV: {ev_pct:+.1f}% (threshold: {self.lotto_min_edge_pct}%)")
            else:
                logger.debug(f"[LOTTO] {coin}: {direction} at ${actual_price:.3f} - EV {ev_pct:+.1f}% below threshold {self.lotto_min_edge_pct}%")

            return {
                'strategy': 'lotto',
                'opportunity': is_opportunity,
                'direction': direction,
                'edge_pct': ev_pct,
                'diff': ev_pct,  # Alias for bot compatibility
                'price': actual_price,
                'current_spot': current_spot,
                'strike_price': strike_price,
                'pct_from_strike': pct_diff
            }

        return None

    def check_arbitrage(self, coin: str, polymarket_price: float,
                       strike_price: float, time_remaining: float,
                       market_15m=None) -> Optional[Dict]:
        """
        Main arbitrage checker - runs all enabled strategies
        Returns best opportunity found (highest edge)

        Note: polymarket_price parameter is ignored - we fetch both YES/NO prices directly
        This maintains compatibility with existing bot interface
        """
        self._sync_prices()

        # Get YES and NO prices (need both for complement arbitrage)
        yes_price = polymarket_price  # Default fallback
        no_price = 1.0 - polymarket_price  # Theoretical complement

        # If market_15m is provided, get actual YES/NO prices
        if market_15m:
            try:
                tokens = market_15m.get_token_ids_for_coin(coin)
                if tokens:
                    yes_id = tokens.get('yes')
                    no_id = tokens.get('no')
                    if yes_id and no_id:
                        yes_price = market_15m.client.get_midpoint_price(yes_id) or polymarket_price
                        no_price = market_15m.client.get_midpoint_price(no_id) or (1.0 - polymarket_price)
            except Exception as e:
                logger.warning(f"Failed to get YES/NO prices for {coin}: {e}")

        opportunities = []
        info_results = []  # Non-opportunity results for dashboard display

        # Strategy 1: Complement arbitrage (YES+NO<$1)
        comp = self.check_complement_arbitrage(yes_price, no_price)
        if comp:
            if comp.get('opportunity'):
                opportunities.append(comp)
            else:
                info_results.append(comp)

        # Strategy 2: Spot price arbitrage
        spot = self.check_spot_arbitrage(coin, strike_price, yes_price, no_price, time_remaining)
        if spot:
            if spot.get('opportunity'):
                opportunities.append(spot)
            else:
                info_results.append(spot)

        # Strategy 3: Lotto strategy
        lotto = self.check_lotto_strategy(coin, strike_price, yes_price, no_price, time_remaining)
        if lotto:
            if lotto.get('opportunity'):
                opportunities.append(lotto)
            else:
                info_results.append(lotto)

        # Return best opportunity (highest edge)
        if opportunities:
            best = max(opportunities, key=lambda x: x['edge_pct'])
            logger.info(f"[BEST OPPORTUNITY] Strategy: {best['strategy']}, Edge: {best['edge_pct']:.2f}%")
            return best

        # Return best below-threshold result so dashboard shows real EV
        if info_results:
            best_info = max(info_results, key=lambda x: x['edge_pct'])
            return best_info

        # No opportunities found - compute raw informational edge for dashboard
        # Shows spot-vs-strike distance so user always sees market direction
        spot_price = self.exchange_prices.get(coin, {}).get('price', 0)
        raw_diff = 0.0
        raw_direction = None
        if spot_price and spot_price > 0 and strike_price and strike_price > 0:
            pct_diff = ((spot_price - strike_price) / strike_price) * 100
            raw_diff = pct_diff  # Signed: positive = above strike, negative = below
            if pct_diff > 0:
                raw_direction = "UP"
            elif pct_diff < 0:
                raw_direction = "DOWN"

        logger.debug(f"[EDGE INFO] {coin}: spot=${spot_price:,.2f} strike=${strike_price:,.2f} "
                     f"diff={raw_diff:+.2f}% dir={raw_direction} time={time_remaining:.0f}s "
                     f"exchange_prices_keys={list(self.exchange_prices.keys())}")

        return {
            'opportunity': False,
            'direction': raw_direction,
            'edge_pct': abs(raw_diff),
            'diff': raw_diff,  # Signed % like PriceArbitrageDetector for dashboard consistency
            'yes_price': yes_price,
            'no_price': no_price,
            'total': yes_price + no_price,
            'current_spot': spot_price,
            'strike_price': strike_price,
            'time_remaining': time_remaining,
            'reason': 'No arbitrage edge found above fee threshold'
        }
