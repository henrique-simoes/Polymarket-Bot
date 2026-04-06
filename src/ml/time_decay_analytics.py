"""
Time-Decay Strategy Analytics

Tracks and analyzes Time-Decay trading performance to surface insights:
- ML training progress and feature importance
- Black-Scholes edge accuracy
- Best times of day for trading
- Optimal price ranges per coin
- Win rate by various factors
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import numpy as np

logger = logging.getLogger("TimeDecay")


class TimeDecayAnalytics:
    """
    Analytics engine for Time-Decay Sniper strategy.

    Tracks:
    - Feature importance evolution
    - BS edge vs actual outcomes
    - Time-of-day patterns
    - Price range performance
    - Per-coin statistics
    """

    def __init__(self, data_file: str = "data/time_decay_analytics.json"):
        self.data_file = data_file
        self.analytics_data = {
            'trades_by_hour': defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_edge': 0.0}),
            'trades_by_price_range': defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_edge': 0.0}),
            'trades_by_coin': defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_edge': 0.0, 'avg_price': 0.0}),
            'bs_edge_accuracy': [],  # [(predicted_edge, actual_won)]
            'feature_importance_history': [],  # [{timestamp, features: {name: importance}}]
            'calibration_adjustments': [],  # [(bs_edge, ml_edge, adjustment_factor)]
        }
        self.load_data()

    def load_data(self):
        """Load analytics data from disk"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    loaded = json.load(f)
                    # Convert defaultdicts
                    self.analytics_data['trades_by_hour'] = defaultdict(
                        lambda: {'wins': 0, 'losses': 0, 'total_edge': 0.0},
                        loaded.get('trades_by_hour', {})
                    )
                    self.analytics_data['trades_by_price_range'] = defaultdict(
                        lambda: {'wins': 0, 'losses': 0, 'total_edge': 0.0},
                        loaded.get('trades_by_price_range', {})
                    )
                    self.analytics_data['trades_by_coin'] = defaultdict(
                        lambda: {'wins': 0, 'losses': 0, 'total_edge': 0.0, 'avg_price': 0.0},
                        loaded.get('trades_by_coin', {})
                    )
                    self.analytics_data['bs_edge_accuracy'] = loaded.get('bs_edge_accuracy', [])
                    self.analytics_data['feature_importance_history'] = loaded.get('feature_importance_history', [])
                    self.analytics_data['calibration_adjustments'] = loaded.get('calibration_adjustments', [])
        except Exception as e:
            logger.error(f"Failed to load analytics data: {e}")

    def save_data(self):
        """Save analytics data to disk"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            # Convert defaultdicts to regular dicts for JSON
            save_data = {
                'trades_by_hour': dict(self.analytics_data['trades_by_hour']),
                'trades_by_price_range': dict(self.analytics_data['trades_by_price_range']),
                'trades_by_coin': dict(self.analytics_data['trades_by_coin']),
                'bs_edge_accuracy': self.analytics_data['bs_edge_accuracy'],
                'feature_importance_history': self.analytics_data['feature_importance_history'],
                'calibration_adjustments': self.analytics_data['calibration_adjustments']
            }
            with open(self.data_file, 'w') as f:
                json.dump(save_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save analytics data: {e}")

    def record_trade(self, trade_data: Dict):
        """
        Record a completed trade for analytics.

        Args:
            trade_data: {
                'coin': str,
                'token_price': float,
                'bs_edge': float,
                'won': bool,
                'timestamp': str (ISO format),
                'time_remaining': int (optional, seconds when trade placed)
            }
        """
        coin = trade_data.get('coin', 'UNKNOWN')
        token_price = trade_data.get('token_price', 0.75)
        bs_edge = trade_data.get('bs_edge', 0.0)
        won = trade_data.get('won', False)
        timestamp_str = trade_data.get('timestamp', datetime.now().isoformat())
        time_remaining = trade_data.get('time_remaining', 300)  # Entry time (seconds)

        # Parse timestamp
        try:
            dt = datetime.fromisoformat(timestamp_str)
        except:
            dt = datetime.now()

        # Track by hour of day (0-23)
        hour = dt.hour
        hour_key = str(hour)
        if won:
            self.analytics_data['trades_by_hour'][hour_key]['wins'] += 1
        else:
            self.analytics_data['trades_by_hour'][hour_key]['losses'] += 1
        self.analytics_data['trades_by_hour'][hour_key]['total_edge'] += bs_edge

        # Track by price range (60-65, 65-70, 70-75, 75-80, 80-85, 85-90)
        price_cents = int(token_price * 100)
        if price_cents < 65:
            range_key = '60-65¢'
        elif price_cents < 70:
            range_key = '65-70¢'
        elif price_cents < 75:
            range_key = '70-75¢'
        elif price_cents < 80:
            range_key = '75-80¢'
        elif price_cents < 85:
            range_key = '80-85¢'
        else:
            range_key = '85-90¢'

        if won:
            self.analytics_data['trades_by_price_range'][range_key]['wins'] += 1
        else:
            self.analytics_data['trades_by_price_range'][range_key]['losses'] += 1
        self.analytics_data['trades_by_price_range'][range_key]['total_edge'] += bs_edge

        # Track by coin
        if won:
            self.analytics_data['trades_by_coin'][coin]['wins'] += 1
        else:
            self.analytics_data['trades_by_coin'][coin]['losses'] += 1
        self.analytics_data['trades_by_coin'][coin]['total_edge'] += bs_edge

        # Update average price for coin
        total_trades = (self.analytics_data['trades_by_coin'][coin]['wins'] +
                       self.analytics_data['trades_by_coin'][coin]['losses'])
        current_avg = self.analytics_data['trades_by_coin'][coin]['avg_price']
        self.analytics_data['trades_by_coin'][coin]['avg_price'] = (
            (current_avg * (total_trades - 1) + token_price) / total_trades
        )

        # Track BS edge accuracy (including entry time for window analysis)
        self.analytics_data['bs_edge_accuracy'].append({
            'bs_edge': bs_edge,
            'won': won,
            'timestamp': timestamp_str,
            'time_remaining': time_remaining  # When trade was placed (for window optimization)
        })

        self.save_data()

    def record_calibration(self, bs_edge: float, ml_edge: float, adjustment_factor: float):
        """Record ML calibration adjustment"""
        self.analytics_data['calibration_adjustments'].append({
            'bs_edge': bs_edge,
            'ml_edge': ml_edge,
            'adjustment_factor': adjustment_factor,
            'timestamp': datetime.now().isoformat()
        })

        # Keep only last 100 adjustments
        if len(self.analytics_data['calibration_adjustments']) > 100:
            self.analytics_data['calibration_adjustments'] = self.analytics_data['calibration_adjustments'][-100:]

        self.save_data()

    def record_feature_importance(self, features: Dict[str, float]):
        """
        Record feature importance from training.

        Args:
            features: {feature_name: importance_percentage}
        """
        self.analytics_data['feature_importance_history'].append({
            'timestamp': datetime.now().isoformat(),
            'features': features
        })

        # Keep only last 20 training runs
        if len(self.analytics_data['feature_importance_history']) > 20:
            self.analytics_data['feature_importance_history'] = self.analytics_data['feature_importance_history'][-20:]

        self.save_data()

    def get_best_hours(self, top_n: int = 3) -> List[tuple]:
        """
        Get best performing hours of day.

        Returns:
            [(hour, win_rate, trades_count), ...]
        """
        hours_performance = []
        for hour_str, data in self.analytics_data['trades_by_hour'].items():
            total = data['wins'] + data['losses']
            if total >= 3:  # Minimum 3 trades for reliability
                win_rate = data['wins'] / total
                hours_performance.append((int(hour_str), win_rate, total))

        # Sort by win rate descending
        hours_performance.sort(key=lambda x: x[1], reverse=True)
        return hours_performance[:top_n]

    def get_best_price_ranges(self) -> List[tuple]:
        """
        Get price range performance.

        Returns:
            [(range_key, win_rate, trades_count, avg_edge), ...]
        """
        ranges_performance = []
        for range_key, data in self.analytics_data['trades_by_price_range'].items():
            total = data['wins'] + data['losses']
            if total > 0:
                win_rate = data['wins'] / total
                avg_edge = data['total_edge'] / total
                ranges_performance.append((range_key, win_rate, total, avg_edge))

        # Sort by win rate descending
        ranges_performance.sort(key=lambda x: x[1], reverse=True)
        return ranges_performance

    def get_coin_performance(self) -> List[tuple]:
        """
        Get per-coin performance.

        Returns:
            [(coin, win_rate, trades_count, avg_price, avg_edge), ...]
        """
        coin_performance = []
        for coin, data in self.analytics_data['trades_by_coin'].items():
            total = data['wins'] + data['losses']
            if total > 0:
                win_rate = data['wins'] / total
                avg_edge = data['total_edge'] / total
                avg_price = data['avg_price']
                coin_performance.append((coin, win_rate, total, avg_price, avg_edge))

        # Sort by trades count descending
        coin_performance.sort(key=lambda x: x[2], reverse=True)
        return coin_performance

    def get_bs_accuracy_stats(self) -> Dict:
        """
        Get Black-Scholes edge accuracy statistics.

        Returns:
            {
                'total_trades': int,
                'avg_edge_winners': float,
                'avg_edge_losers': float,
                'edge_accuracy': float  # correlation between edge and outcome
            }
        """
        if not self.analytics_data['bs_edge_accuracy']:
            return {
                'total_trades': 0,
                'avg_edge_winners': 0.0,
                'avg_edge_losers': 0.0,
                'edge_accuracy': 0.0
            }

        winners = [t['bs_edge'] for t in self.analytics_data['bs_edge_accuracy'] if t['won']]
        losers = [t['bs_edge'] for t in self.analytics_data['bs_edge_accuracy'] if not t['won']]

        avg_edge_winners = np.mean(winners) if winners else 0.0
        avg_edge_losers = np.mean(losers) if losers else 0.0

        # Calculate correlation (higher edge should = higher win rate)
        # Simple metric: (avg_edge_winners - avg_edge_losers) / avg_edge_winners
        if avg_edge_winners > 0:
            edge_accuracy = (avg_edge_winners - avg_edge_losers) / avg_edge_winners
        else:
            edge_accuracy = 0.0

        return {
            'total_trades': len(self.analytics_data['bs_edge_accuracy']),
            'avg_edge_winners': avg_edge_winners,
            'avg_edge_losers': avg_edge_losers,
            'edge_accuracy': edge_accuracy
        }

    def get_calibration_stats(self) -> Dict:
        """Get ML calibration statistics"""
        if not self.analytics_data['calibration_adjustments']:
            return {
                'total_calibrations': 0,
                'avg_adjustment_factor': 1.0,
                'avg_reduction': 0.0
            }

        adjustments = self.analytics_data['calibration_adjustments']
        avg_adjustment = np.mean([a['adjustment_factor'] for a in adjustments])

        # Average edge reduction
        reductions = []
        for a in adjustments:
            if a['bs_edge'] > 0:
                reduction = (a['bs_edge'] - a['ml_edge']) / a['bs_edge']
                reductions.append(reduction)

        avg_reduction = np.mean(reductions) if reductions else 0.0

        return {
            'total_calibrations': len(adjustments),
            'avg_adjustment_factor': avg_adjustment,
            'avg_reduction': avg_reduction
        }

    def get_latest_feature_importance(self) -> Optional[Dict[str, float]]:
        """Get most recent feature importance from training"""
        if not self.analytics_data['feature_importance_history']:
            return None

        return self.analytics_data['feature_importance_history'][-1]['features']

    def get_feature_importance_trend(self, feature_name: str) -> List[float]:
        """Get historical trend for specific feature importance"""
        return [
            entry['features'].get(feature_name, 0.0)
            for entry in self.analytics_data['feature_importance_history']
        ]

    def get_best_entry_windows(self, bucket_size_sec: int = 60) -> List[tuple]:
        """
        Analyze which entry times (time remaining when trade placed) have best performance.

        Args:
            bucket_size_sec: Group entry times into buckets (default 60s)

        Returns:
            [(window_seconds, win_rate, trades_count, avg_edge), ...]
            Sorted by win rate descending
        """
        entry_windows = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_edge': 0.0})

        # Analyze trades by their entry time (time_remaining when placed)
        for trade in self.analytics_data['bs_edge_accuracy']:
            # Get time_remaining from trade metadata (stored during placement)
            time_remaining = trade.get('time_remaining', 300)  # Default 300s if missing

            # Bucket by interval (e.g., 60s, 120s, 180s, ...)
            bucket = (time_remaining // bucket_size_sec) * bucket_size_sec

            # Record outcome
            if trade.get('won', False):
                entry_windows[bucket]['wins'] += 1
            else:
                entry_windows[bucket]['losses'] += 1

            entry_windows[bucket]['total_edge'] += trade.get('bs_edge', 0.0)

        # Convert to list with calculated stats
        windows_performance = []
        for window_sec, data in entry_windows.items():
            total = data['wins'] + data['losses']
            if total > 0:
                win_rate = data['wins'] / total
                avg_edge = data['total_edge'] / total
                windows_performance.append((window_sec, win_rate, total, avg_edge))

        # Sort by win rate descending
        windows_performance.sort(key=lambda x: x[1], reverse=True)
        return windows_performance

    def get_optimal_entry_window(self, min_trades: int = 5, default_window: int = 300) -> int:
        """
        Get ML-learned optimal entry window based on historical performance.

        Args:
            min_trades: Minimum trades required for a window to be considered
            default_window: Default window if insufficient data

        Returns:
            Optimal window in seconds (e.g., 180 for 3 minutes)
        """
        windows = self.get_best_entry_windows()

        if not windows:
            return default_window

        # Find window with best win rate (requiring minimum trade count)
        for window_sec, win_rate, count, avg_edge in windows:
            if count >= min_trades:
                return window_sec

        # If no window has enough trades, return default
        return default_window
