"""
Phantom Trade Tracker

Tracks opportunities that were REJECTED (not bet on) and records what would have
happened if we had taken them. This allows:
1. Validation of filtering rules (are we rejecting good opportunities?)
2. Strategy optimization (which thresholds work best?)
3. ML training on "missed" opportunities

Example: "BTC at 22¢ rejected (price too low) → Would have WON → Maybe 22¢ is viable?"
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict
from threading import Lock

from .persistence import atomic_json_write, safe_json_load

logger = logging.getLogger("PhantomTracker")


class PhantomTracker:
    """
    Tracks rejected opportunities and their outcomes.

    Use cases:
    - Analyze which filters reject winning opportunities
    - Optimize thresholds (price, edge, confidence, etc.)
    - Train ML on broader dataset
    """

    def __init__(self, data_file: str = "data/phantom_trades.json"):
        self.data_file = data_file
        self._lock = Lock()
        self.phantom_trades = []  # List of all phantom trades
        self.current_round_rejections = {}  # {coin: rejection_data}
        self.load_data()

    def load_data(self):
        """Load phantom trades from disk"""
        self.phantom_trades = safe_json_load(self.data_file, default=[])
        if self.phantom_trades:
            logger.info(f"Loaded {len(self.phantom_trades)} phantom trades from disk")

    def save_data(self):
        """Save phantom trades to disk (thread-safe, atomic)"""
        with self._lock:
            try:
                atomic_json_write(self.data_file, self.phantom_trades)
            except Exception as e:
                logger.error(f"Failed to save phantom trades: {e}")

    def record_rejection(self, coin: str, opportunity_data: Dict):
        """
        Record an opportunity that was rejected.

        Args:
            coin: BTC/ETH/SOL
            opportunity_data: {
                'price': float,
                'direction': 'UP' or 'DOWN',
                'edge': float,
                'ml_confidence': float (optional),
                'rejection_reason': str,
                'timestamp': str (ISO format)
            }
        """
        self.current_round_rejections[coin] = {
            **opportunity_data,
            'coin': coin,
            'timestamp': opportunity_data.get('timestamp', datetime.now().isoformat())
        }
        logger.debug(f"Recorded rejection for {coin}: {opportunity_data['rejection_reason']}")

    def finalize_round(self, outcomes: Dict[str, str]):
        """
        At round settlement, record what would have happened for rejected opportunities.

        Args:
            outcomes: {coin: 'UP' or 'DOWN'} actual market outcomes
        """
        for coin, rejection_data in self.current_round_rejections.items():
            actual_outcome = outcomes.get(coin)

            if actual_outcome:
                predicted_direction = rejection_data.get('direction')
                would_have_won = (predicted_direction == actual_outcome)

                phantom_trade = {
                    **rejection_data,
                    'actual_outcome': actual_outcome,
                    'would_have_won': would_have_won,
                    'settlement_timestamp': datetime.now().isoformat()
                }

                self.phantom_trades.append(phantom_trade)

                result = "WON" if would_have_won else "LOST"
                logger.info(f"[PHANTOM] {coin}: Rejected but would have {result} | "
                          f"Reason: {rejection_data['rejection_reason']}")

        # Clear for next round
        self.current_round_rejections = {}

        # Save to disk
        self.save_data()

    def get_statistics(self) -> Dict:
        """Get phantom trade statistics"""
        if not self.phantom_trades:
            return {
                'total_phantom_trades': 0,
                'would_have_won': 0,
                'would_have_lost': 0,
                'phantom_win_rate': 0.0,
                'by_rejection_reason': {}
            }

        wins = sum(1 for t in self.phantom_trades if t['would_have_won'])
        losses = len(self.phantom_trades) - wins

        # Group by rejection reason
        by_reason = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total': 0})
        for trade in self.phantom_trades:
            reason = trade.get('rejection_reason', 'Unknown')
            if trade['would_have_won']:
                by_reason[reason]['wins'] += 1
            else:
                by_reason[reason]['losses'] += 1
            by_reason[reason]['total'] += 1

        # Calculate win rates per reason
        reason_stats = {}
        for reason, data in by_reason.items():
            reason_stats[reason] = {
                **data,
                'win_rate': data['wins'] / data['total'] if data['total'] > 0 else 0.0
            }

        return {
            'total_phantom_trades': len(self.phantom_trades),
            'would_have_won': wins,
            'would_have_lost': losses,
            'phantom_win_rate': wins / len(self.phantom_trades) if self.phantom_trades else 0.0,
            'by_rejection_reason': reason_stats
        }

    def analyze_filter_impact(self, filter_name: str) -> Dict:
        """
        Analyze impact of a specific filter.

        Args:
            filter_name: Part of rejection reason to search for

        Returns:
            Statistics for trades rejected by this filter
        """
        filtered_trades = [
            t for t in self.phantom_trades
            if filter_name.lower() in t.get('rejection_reason', '').lower()
        ]

        if not filtered_trades:
            return {
                'filter_name': filter_name,
                'trades_rejected': 0,
                'message': f"No trades rejected by '{filter_name}'"
            }

        wins = sum(1 for t in filtered_trades if t['would_have_won'])
        losses = len(filtered_trades) - wins

        return {
            'filter_name': filter_name,
            'trades_rejected': len(filtered_trades),
            'would_have_won': wins,
            'would_have_lost': losses,
            'win_rate': wins / len(filtered_trades),
            'verdict': 'GOOD FILTER' if wins / len(filtered_trades) < 0.50 else 'BAD FILTER (rejects winners!)'
        }

    def get_top_regrets(self, top_n: int = 10) -> List[Dict]:
        """
        Get top N rejected trades that would have won.

        These are "regrets" - opportunities we should have taken.
        """
        winners = [t for t in self.phantom_trades if t['would_have_won']]

        # Sort by edge (highest missed edge = biggest regret)
        winners.sort(key=lambda x: x.get('edge', 0), reverse=True)

        return winners[:top_n]

    def clear_old_data(self, days_to_keep: int = 30):
        """Remove phantom trades older than N days"""
        cutoff_date = datetime.now().timestamp() - (days_to_keep * 86400)

        original_count = len(self.phantom_trades)
        self.phantom_trades = [
            t for t in self.phantom_trades
            if datetime.fromisoformat(t['timestamp']).timestamp() > cutoff_date
        ]

        removed = original_count - len(self.phantom_trades)
        if removed > 0:
            logger.info(f"Cleared {removed} phantom trades older than {days_to_keep} days")
            self.save_data()
