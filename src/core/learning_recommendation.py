"""
Learning Recommendation System - Analyzes when to switch to live trading
Recommends transitioning from learning mode to live based on performance
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("LearningRecommendation")


class LearningRecommendation:
    """
    Analyzes learning mode performance and recommends when to go live

    Criteria for recommending live mode:
    - Minimum sample size (200+ trades recommended)
    - Win rate threshold (>52% for profitability)
    - Consistency (last 50 trades performance)
    - ROI positive
    """

    def __init__(self, min_samples: int = 200, min_win_rate: float = 52.0,
                 consistency_window: int = 50):
        """
        Initialize recommendation system

        Args:
            min_samples: Minimum trades before recommending live
            min_win_rate: Minimum win rate % for recommendation
            consistency_window: Number of recent trades to check consistency
        """
        self.min_samples = min_samples
        self.min_win_rate = min_win_rate
        self.consistency_window = consistency_window

        logger.info(f"Learning Recommendation initialized (min: {min_samples} samples, {min_win_rate}% WR)")

    def analyze(self, trades: List[Dict], simulator_stats: Dict) -> Dict:
        """
        Analyze learning mode performance and generate recommendation

        Args:
            trades: List of all learning trades
            simulator_stats: Stats from LearningSimulator

        Returns:
            Dict with recommendation and reasoning
        """
        if not trades:
            return {
                'ready_for_live': False,
                'confidence': 0.0,
                'reason': 'No training data yet',
                'progress': 0.0,
                'recommendations': ['Continue collecting data in learning mode']
            }

        total_trades = len(trades)
        win_rate = simulator_stats.get('win_rate', 0.0)
        total_pnl = simulator_stats.get('total_pnl', 0.0)

        # Progress toward minimum samples
        progress = min(100.0, (total_trades / self.min_samples) * 100)

        # Check criteria
        criteria = self._evaluate_criteria(trades, simulator_stats)

        # Generate recommendation
        ready = all(criteria.values())
        confidence = self._calculate_confidence(criteria, total_trades, win_rate)

        reason = self._generate_reason(criteria, total_trades, win_rate, total_pnl)
        recommendations = self._generate_recommendations(criteria, total_trades, win_rate)

        return {
            'ready_for_live': ready,
            'confidence': confidence,
            'reason': reason,
            'progress': progress,
            'criteria': criteria,
            'recommendations': recommendations,
            'stats': {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'samples_needed': max(0, self.min_samples - total_trades)
            }
        }

    def _evaluate_criteria(self, trades: List[Dict], simulator_stats: Dict) -> Dict[str, bool]:
        """Evaluate all criteria for live mode readiness"""
        total_trades = len(trades)
        win_rate = simulator_stats.get('win_rate', 0.0)
        total_pnl = simulator_stats.get('total_pnl', 0.0)

        criteria = {
            'sufficient_samples': total_trades >= self.min_samples,
            'win_rate_threshold': win_rate >= self.min_win_rate,
            'positive_roi': total_pnl > 0,
            'consistent_performance': self._check_consistency(trades)
        }

        return criteria

    def _check_consistency(self, trades: List[Dict]) -> bool:
        """Check if recent performance is consistent"""
        if len(trades) < self.consistency_window:
            return False

        # Check last N trades
        recent_trades = trades[-self.consistency_window:]
        recent_wins = sum(1 for t in recent_trades if t.get('won', False))
        recent_win_rate = (recent_wins / len(recent_trades)) * 100

        # Recent win rate should be >= threshold
        return recent_win_rate >= self.min_win_rate

    def _calculate_confidence(self, criteria: Dict[str, bool],
                             total_trades: int, win_rate: float) -> float:
        """Calculate confidence level (0-100)"""
        # Base confidence from criteria met
        criteria_met = sum(1 for v in criteria.values() if v)
        base_confidence = (criteria_met / len(criteria)) * 100

        # Bonus for exceeding minimums
        sample_bonus = min(20, (total_trades - self.min_samples) / 10) if total_trades > self.min_samples else 0
        win_rate_bonus = min(20, (win_rate - self.min_win_rate) * 2) if win_rate > self.min_win_rate else 0

        confidence = min(100.0, base_confidence + sample_bonus + win_rate_bonus)
        return round(confidence, 1)

    def _generate_reason(self, criteria: Dict[str, bool],
                        total_trades: int, win_rate: float, total_pnl: float) -> str:
        """Generate human-readable reason for recommendation"""
        if all(criteria.values()):
            return (f"All criteria met: {total_trades} samples, {win_rate:.1f}% win rate, "
                   f"${total_pnl:+.2f} virtual P&L. Ready for live trading!")

        issues = []
        if not criteria['sufficient_samples']:
            needed = self.min_samples - total_trades
            issues.append(f"need {needed} more samples")

        if not criteria['win_rate_threshold']:
            gap = self.min_win_rate - win_rate
            issues.append(f"win rate {gap:.1f}% below threshold")

        if not criteria['positive_roi']:
            issues.append(f"negative virtual P&L (${total_pnl:.2f})")

        if not criteria['consistent_performance']:
            issues.append("recent performance inconsistent")

        return "Not ready: " + ", ".join(issues)

    def _generate_recommendations(self, criteria: Dict[str, bool],
                                 total_trades: int, win_rate: float) -> List[str]:
        """Generate actionable recommendations"""
        recs = []

        if not criteria['sufficient_samples']:
            needed = self.min_samples - total_trades
            recs.append(f"Collect {needed} more samples in learning mode")

        if not criteria['win_rate_threshold']:
            recs.append("Review ML features and model performance")
            recs.append("Consider adjusting risk profile or entry timing")

        if not criteria['positive_roi']:
            recs.append("Analyze losing trades for patterns")
            recs.append("Consider bet sizing adjustments")

        if not criteria['consistent_performance']:
            recs.append(f"Continue trading until last {self.consistency_window} trades are consistent")

        if all(criteria.values()):
            recs.append("Switch to live mode with small initial bets")
            recs.append("Monitor performance closely for first 20 live trades")
            recs.append("Can increase bet sizes if live performance matches learning")

        return recs

    def get_progress_display(self, trades: List[Dict], simulator_stats: Dict) -> str:
        """
        Generate progress bar display for CLI

        Returns:
            String with progress bar and stats
        """
        total_trades = len(trades)
        progress = min(100.0, (total_trades / self.min_samples) * 100)
        win_rate = simulator_stats.get('win_rate', 0.0)

        # Progress bar (20 chars)
        filled = int(progress / 5)
        bar = "█" * filled + "░" * (20 - filled)

        status = "READY" if progress >= 100 and win_rate >= self.min_win_rate else "TRAINING"

        return f"[{bar}] {progress:.0f}% | {total_trades}/{self.min_samples} samples | {status}"
