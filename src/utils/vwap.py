"""
VWAP (Volume-Weighted Average Price) Calculator

Calculates VWAP for short-term markets (15-minute binary options).

VWAP = Σ(Price × Volume) / Σ(Volume)

Used as:
- Fair value reference point
- Noise reduction (vs single-tick prices)
- Volume-weighted consensus
"""

import logging
from typing import List, Dict, Optional
from collections import deque
import time

logger = logging.getLogger("TimeDecay")


class VWAPCalculator:
    """
    Calculate Volume-Weighted Average Price for 15-minute markets.

    Maintains rolling window of price/volume data and calculates VWAP
    on demand. Used as experimental feature in Time-Decay ML calibration.
    """

    def __init__(self, window_seconds: int = 900):
        """
        Initialize VWAP calculator.

        Args:
            window_seconds: Rolling window size (default 900s = 15 minutes)
        """
        self.window_seconds = window_seconds
        self.price_volume_data = {
            'BTC': deque(maxlen=1000),  # (timestamp, price, volume)
            'ETH': deque(maxlen=1000),
            'SOL': deque(maxlen=1000)
        }

    def add_tick(self, coin: str, price: float, volume: float, timestamp: Optional[float] = None):
        """
        Add price/volume tick.

        Args:
            coin: BTC/ETH/SOL
            price: Trade price
            volume: Trade volume (can use 1.0 if volume unavailable)
            timestamp: Unix timestamp (default: current time)
        """
        if timestamp is None:
            timestamp = time.time()

        if coin not in self.price_volume_data:
            self.price_volume_data[coin] = deque(maxlen=1000)

        self.price_volume_data[coin].append((timestamp, price, volume))

    def calculate_vwap(self, coin: str, window_seconds: Optional[int] = None) -> Optional[float]:
        """
        Calculate VWAP for coin over rolling window.

        Args:
            coin: BTC/ETH/SOL
            window_seconds: Override default window (optional)

        Returns:
            VWAP price, or None if insufficient data
        """
        if coin not in self.price_volume_data:
            return None

        data = self.price_volume_data[coin]
        if not data:
            return None

        window = window_seconds if window_seconds is not None else self.window_seconds
        cutoff_time = time.time() - window

        # Filter data within window
        recent_data = [(ts, p, v) for ts, p, v in data if ts >= cutoff_time]

        if not recent_data:
            return None

        # Calculate VWAP: Σ(Price × Volume) / Σ(Volume)
        total_pv = sum(p * v for _, p, v in recent_data)
        total_volume = sum(v for _, _, v in recent_data)

        if total_volume == 0:
            return None

        vwap = total_pv / total_volume
        return vwap

    def get_vwap_features(self, coin: str, current_price: float) -> Dict:
        """
        Calculate VWAP-based features for ML.

        Args:
            coin: BTC/ETH/SOL
            current_price: Current spot price

        Returns:
            Dictionary of VWAP features:
            - vwap_price: VWAP value
            - vwap_deviation_pct: (price - vwap) / vwap
            - price_above_vwap: 1 if above, 0 if below
            - vwap_trend: Recent VWAP slope (up/down/flat)
        """
        vwap = self.calculate_vwap(coin)

        if vwap is None:
            # No VWAP data - return neutral values
            return {
                'vwap_price': current_price,  # Default to current price
                'vwap_deviation_pct': 0.0,
                'price_above_vwap': 0.5,  # Neutral
                'vwap_trend': 0.0
            }

        # Calculate deviation
        deviation_pct = (current_price - vwap) / vwap

        # Above/below VWAP
        above_vwap = 1.0 if current_price > vwap else 0.0

        # VWAP trend (compare recent VWAP to older VWAP)
        vwap_5min = self.calculate_vwap(coin, window_seconds=300)
        vwap_10min = self.calculate_vwap(coin, window_seconds=600)

        if vwap_5min and vwap_10min:
            vwap_trend = (vwap_5min - vwap_10min) / vwap_10min
        else:
            vwap_trend = 0.0

        return {
            'vwap_price': vwap,
            'vwap_deviation_pct': deviation_pct,
            'price_above_vwap': above_vwap,
            'vwap_trend': vwap_trend
        }

    def get_statistics(self, coin: str) -> Dict:
        """Get VWAP calculator statistics"""
        if coin not in self.price_volume_data:
            return {
                'ticks': 0,
                'window_seconds': self.window_seconds,
                'vwap': None
            }

        data = self.price_volume_data[coin]
        vwap = self.calculate_vwap(coin)

        return {
            'ticks': len(data),
            'window_seconds': self.window_seconds,
            'vwap': vwap,
            'oldest_tick_age': time.time() - data[0][0] if data else 0
        }

    def reset(self, coin: Optional[str] = None):
        """
        Reset VWAP data.

        Args:
            coin: Reset specific coin (default: all coins)
        """
        if coin:
            if coin in self.price_volume_data:
                self.price_volume_data[coin].clear()
        else:
            for c in self.price_volume_data:
                self.price_volume_data[c].clear()


# Global VWAP calculator instance (shared across bot)
_vwap_calculator = None


def get_vwap_calculator(window_seconds: int = 900) -> VWAPCalculator:
    """
    Get or create global VWAP calculator instance.

    Args:
        window_seconds: Rolling window size

    Returns:
        VWAPCalculator instance
    """
    global _vwap_calculator
    if _vwap_calculator is None:
        _vwap_calculator = VWAPCalculator(window_seconds)
    return _vwap_calculator
