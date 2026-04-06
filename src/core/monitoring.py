"""
Real-Time Monitor - Tracks 15-minute candle and triggers continuous learning
"""

import time
from collections import deque
from threading import Lock
import numpy as np

class RealTimeMonitor:
    """
    Monitors prices in real-time during the 15-minute period
    Continuously updates predictions as new data comes in
    """

    def __init__(self, learning_engine):
        """
        Initialize monitor

        Args:
            learning_engine: ContinuousLearningEngine instance
        """
        self.learning_engine = learning_engine
        self.current_predictions = {}
        self.prediction_lock = Lock()

        # Store price history for current candle (900 seconds = 15 minutes)
        self.price_history_this_candle = {
            'BTC': deque(maxlen=900),
            'ETH': deque(maxlen=900),
            'SOL': deque(maxlen=900)
        }

        self.candle_start_price = {}
        self.candle_start_time = {}

    def start_monitoring_candle(self, coin, start_price, start_time):
        """
        Start monitoring a new 15-minute candle

        Args:
            coin: Cryptocurrency symbol
            start_price: Starting price of candle
            start_time: Start timestamp
        """
        self.candle_start_price[coin] = start_price
        self.candle_start_time[coin] = start_time
        self.price_history_this_candle[coin].clear()

        print(f"    [{coin}] Monitoring started")
        print(f"       Start Price: ${start_price:.2f}")
        print(f"       Start Time: {start_time.strftime('%H:%M:%S')}")

    def update_price(self, coin, current_price, features, timestamp):
        """
        Update with new price tick

        This is called every second during the 15-minute period
        Triggers continuous learning!

        Args:
            coin: Cryptocurrency symbol
            current_price: Current price
            features: Extracted features array
            timestamp: Current timestamp
        """
        # Add to price history
        self.price_history_this_candle[coin].append(current_price)

        # Learn from CANDLE DIRECTION (opening price vs current price)
        # This matches the actual market question: "Will price be higher at end than at start?"
        if len(self.price_history_this_candle[coin]) >= 10:  # Need at least 10 observations
            opening_price = self.candle_start_price[coin]

            # Direction: 1 if price is above opening, 0 if below
            # This is what the market ACTUALLY resolves on!
            direction = 1 if current_price > opening_price else 0

            # THIS IS WHERE CONTINUOUS LEARNING HAPPENS!
            self.learning_engine.add_observation(coin, features, direction)

        # Update current prediction
        prob_up = self.learning_engine.predict(coin, features)

        with self.prediction_lock:
            self.current_predictions[coin] = {
                'prob_up': prob_up,
                'current_price': current_price,
                'start_price': self.candle_start_price[coin],
                'current_trend': 'UP' if current_price > self.candle_start_price[coin] else 'DOWN',
                'timestamp': timestamp,
                'price_change_pct': ((current_price - self.candle_start_price[coin]) / self.candle_start_price[coin]) * 100
            }

    def get_current_prediction(self, coin):
        """Get current prediction (thread-safe)"""
        with self.prediction_lock:
            if coin in self.current_predictions:
                return self.current_predictions[coin].copy()
            return {'prob_up': 0.5, 'current_trend': 'UNKNOWN'}

    def get_final_prediction(self, coin):
        """
        Get final prediction at 14:59
        This is what we use to place the bet
        """
        return self.get_current_prediction(coin)

    def get_candle_statistics(self, coin):
        """
        Get statistics for current candle

        Returns:
            Dict with volatility, range, etc.
        """
        prices = list(self.price_history_this_candle[coin])

        if len(prices) < 10:
            return None

        prices_array = np.array(prices)

        return {
            'high': float(np.max(prices_array)),
            'low': float(np.min(prices_array)),
            'range': float(np.max(prices_array) - np.min(prices_array)),
            'volatility': float(np.std(prices_array)),
            'mean': float(np.mean(prices_array)),
            'current': prices[-1],
            'ticks': len(prices)
        }
