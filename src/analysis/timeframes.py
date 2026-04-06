"""
Multi-Timeframe Analyzer - Analyzes 7 timeframes simultaneously
Aggregates 1-second ticks into all higher timeframes
"""

import numpy as np
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List

class MultiTimeframeAnalyzer:
    """
    Analyzes 7 timeframes: 1s, 1m, 15m, 1h, 4h, 1d, 1w

    Key innovation: Aggregates from 1s ticks up to weekly candles
    Provides context from micro (1s) to macro (1w) scales
    """

    def __init__(self, config: dict = None):
        """
        Initialize multi-timeframe analyzer

        Args:
            config: Timeframe configuration
        """
        if config and 'timeframes' in config:
            # Load from config
            self.timeframes = {}
            for tf_config in config['timeframes']:
                name = tf_config['name']
                self.timeframes[name] = {
                    'period': tf_config['period'],
                    'data': deque(maxlen=tf_config['max_data']),
                    'current_candle': None,
                    'candle_start_time': None
                }
        else:
            # Default configuration
            self.timeframes = {
                '1s': {
                    'period': 1,
                    'data': deque(maxlen=3600),  # 1 hour
                    'current_candle': None,
                    'candle_start_time': None
                },
                '1m': {
                    'period': 60,
                    'data': deque(maxlen=1440),  # 24 hours
                    'current_candle': None,
                    'candle_start_time': None
                },
                '15m': {
                    'period': 900,
                    'data': deque(maxlen=672),  # 7 days
                    'current_candle': None,
                    'candle_start_time': None
                },
                '1h': {
                    'period': 3600,
                    'data': deque(maxlen=720),  # 30 days
                    'current_candle': None,
                    'candle_start_time': None
                },
                '4h': {
                    'period': 14400,
                    'data': deque(maxlen=360),  # 60 days
                    'current_candle': None,
                    'candle_start_time': None
                },
                '1d': {
                    'period': 86400,
                    'data': deque(maxlen=365),  # 1 year
                    'current_candle': None,
                    'candle_start_time': None
                },
                '1w': {
                    'period': 604800,
                    'data': deque(maxlen=104),  # 2 years
                    'current_candle': None,
                    'candle_start_time': None
                }
            }

    def add_tick(self, timestamp: float, price: float, volume: float = 0):
        """
        Add 1-second price tick and aggregate into all timeframes

        This is the core aggregation logic!

        Args:
            timestamp: Unix timestamp
            price: Current price
            volume: Trade volume
        """
        # Add to 1s timeframe directly
        tick_data = {
            'timestamp': timestamp,
            'open': price,
            'high': price,
            'low': price,
            'close': price,
            'volume': volume
        }

        self.timeframes['1s']['data'].append(tick_data)

        # Aggregate into higher timeframes
        dt = datetime.fromtimestamp(timestamp)

        for tf_name, tf_data in self.timeframes.items():
            if tf_name == '1s':
                continue  # Already added

            period = tf_data['period']

            # Determine candle start time
            if tf_name == '1m':
                candle_start = dt.replace(second=0, microsecond=0)
            elif tf_name == '15m':
                minute = (dt.minute // 15) * 15
                candle_start = dt.replace(minute=minute, second=0, microsecond=0)
            elif tf_name == '1h':
                candle_start = dt.replace(minute=0, second=0, microsecond=0)
            elif tf_name == '4h':
                hour = (dt.hour // 4) * 4
                candle_start = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
            elif tf_name == '1d':
                candle_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
            elif tf_name == '1w':
                # Start of week (Monday)
                days_since_monday = dt.weekday()
                candle_start = (dt - timedelta(days=days_since_monday)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )

            candle_start_ts = candle_start.timestamp()

            # Check if we need a new candle
            if (tf_data['candle_start_time'] is None or
                candle_start_ts != tf_data['candle_start_time']):

                # Save previous candle if exists
                if tf_data['current_candle'] is not None:
                    tf_data['data'].append(tf_data['current_candle'])

                # Start new candle
                tf_data['current_candle'] = {
                    'timestamp': candle_start_ts,
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': volume
                }
                tf_data['candle_start_time'] = candle_start_ts
            else:
                # Update current candle
                candle = tf_data['current_candle']
                candle['high'] = max(candle['high'], price)
                candle['low'] = min(candle['low'], price)
                candle['close'] = price
                candle['volume'] += volume

    def get_trend_features(self) -> np.ndarray:
        """
        Extract trend features from all timeframes

        Returns 21 features (3 per timeframe):
        - Trend direction (1=UP, 0=DOWN)
        - Trend strength (distance between MAs)
        - Momentum (rate of change)

        Returns:
            Array of 21 features
        """
        features = []

        for tf_name in ['1s', '1m', '15m', '1h', '4h', '1d', '1w']:
            tf_data = self.timeframes[tf_name]
            data = list(tf_data['data'])

            if len(data) >= 3:
                # Get closing prices
                closes = np.array([d['close'] for d in data])

                # Calculate moving averages (adapt windows to available data)
                sma_short = np.mean(closes[-5:]) if len(closes) >= 5 else np.mean(closes)
                sma_long = np.mean(closes[-20:]) if len(closes) >= 20 else np.mean(closes)

                # Trend direction
                trend_direction = 1 if sma_short > sma_long else 0

                # Trend strength
                trend_strength = abs(sma_short - sma_long) / sma_long if sma_long > 0 else 0

                # Momentum
                lookback = min(10, len(closes))
                momentum = (closes[-1] - closes[-lookback]) / closes[-lookback] if closes[-lookback] > 0 else 0

                # VWAP features
                vwap_data = self.calculate_vwap(tf_name)

                features.extend([
                    trend_direction,
                    trend_strength,
                    momentum,
                    vwap_data['vwap'],
                    vwap_data['price_vs_vwap'],
                    vwap_data['distance_pct']
                ])
            else:
                # Not enough data - return zeros for all 6 features (was 3, now 6)
                features.extend([0, 0, 0, 0, 0, 0])

        return np.array(features)

    def calculate_vwap(self, timeframe_key: str) -> dict:
        """
        Calculate Volume Weighted Average Price (VWAP) for a timeframe.

        VWAP = Σ(Price × Volume) / Σ(Volume)

        Returns:
            dict with:
                'vwap': VWAP value
                'price_vs_vwap': (current - vwap) / vwap (positive = above VWAP)
                'distance_pct': abs(price_vs_vwap) (momentum strength)
        """
        if timeframe_key not in self.timeframes:
            return {'vwap': 0, 'price_vs_vwap': 0, 'distance_pct': 0}

        data = list(self.timeframes[timeframe_key]['data'])

        if len(data) < 2:
            return {'vwap': 0, 'price_vs_vwap': 0, 'distance_pct': 0}

        # Get price and volume arrays (use close price for VWAP)
        prices = np.array([float(c['close']) for c in data])
        volumes = np.array([float(c.get('volume', 0)) for c in data])

        # Calculate VWAP
        total_volume = volumes.sum()
        if total_volume == 0:
            # No volume data, fallback to simple average
            vwap = float(prices.mean())
        else:
            vwap = float((prices * volumes).sum() / total_volume)

        current_price = float(prices[-1])

        # Calculate metrics
        if vwap > 0:
            price_vs_vwap = (current_price - vwap) / vwap
            distance_pct = abs(price_vs_vwap)
        else:
            price_vs_vwap = 0
            distance_pct = 0

        return {
            'vwap': vwap,
            'price_vs_vwap': price_vs_vwap,
            'distance_pct': distance_pct
        }

    def get_timeframe_data(self, timeframe: str) -> List[Dict]:
        """Get data for specific timeframe with explicit float types for TA-Lib compatibility"""
        if timeframe not in self.timeframes:
            return []

        # Convert all values to explicit float types to prevent TA-Lib errors
        data = []
        for candle in self.timeframes[timeframe]['data']:
            data.append({
                'timestamp': float(candle['timestamp']),
                'open': float(candle['open']),
                'high': float(candle['high']),
                'low': float(candle['low']),
                'close': float(candle['close']),
                'volume': float(candle.get('volume', 0))
            })
        return data
