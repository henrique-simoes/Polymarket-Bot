"""
Startup Recommendations - Analyzes historical performance and recommends best strategies
Shows which mode/strategy has been most profitable
"""

import logging
from typing import Dict, List
from datetime import datetime, timedelta

logger = logging.getLogger("StartupRecommendations")


class StartupRecommendationEngine:
    """
    Analyzes historical trading performance and recommends optimal strategies

    Analyzes:
    - Trading mode performance (Arbitrage vs ML vs Lotto)
    - Strategy performance (Early exit vs Hold to expiry)
    - Time-based patterns (Best hours, days of week)
    """

    def __init__(self, history_manager, learning_persistence):
        """
        Initialize recommendation engine

        Args:
            history_manager: TradeHistoryManager instance
            learning_persistence: LearningPersistence instance
        """
        self.history = history_manager
        self.learning = learning_persistence

        logger.info("Startup Recommendation Engine initialized")

    def analyze_and_recommend(self, min_trades: int = 20) -> Dict:
        """
        Analyze all available data and generate recommendations

        Args:
            min_trades: Minimum trades required for reliable recommendations

        Returns:
            Dict with recommendations, analysis, and reasoning
        """
        # Load all trades (real + learning)
        real_trades = self.history.get_all_trades()
        learning_trades = self.learning.load_trades()

        all_trades = real_trades + learning_trades

        if len(all_trades) < min_trades:
            return {
                'has_recommendations': False,
                'reason': f'Need {min_trades - len(all_trades)} more trades for reliable recommendations',
                'total_trades': len(all_trades)
            }

        # Analyze different dimensions
        mode_analysis = self._analyze_by_mode(all_trades)
        time_analysis = self._analyze_by_time(all_trades)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            mode_analysis,
            time_analysis
        )

        return {
            'has_recommendations': True,
            'total_trades': len(all_trades),
            'recommendations': recommendations,
            'mode_analysis': mode_analysis,
            'time_analysis': time_analysis
        }

    def _analyze_by_mode(self, trades: List[Dict]) -> Dict:
        """Analyze performance by trading mode"""
        modes = {
            'real': [t for t in trades if t.get('mode') != 'learning'],
            'learning': [t for t in trades if t.get('mode') == 'learning']
        }

        analysis = {}

        for mode_name, mode_trades in modes.items():
            if not mode_trades:
                continue

            wins = sum(1 for t in mode_trades if t.get('won', False))
            losses = len(mode_trades) - wins
            win_rate = (wins / len(mode_trades) * 100) if mode_trades else 0
            # Handle both 'profit' (new) and 'pnl' (old) field names
            total_pnl = sum(t.get('profit') or t.get('pnl', 0) for t in mode_trades)
            avg_pnl = total_pnl / len(mode_trades) if mode_trades else 0

            analysis[mode_name] = {
                'trades': len(mode_trades),
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'sharpe': self._calculate_sharpe(mode_trades)
            }

        return analysis

    def _analyze_by_time(self, trades: List[Dict]) -> Dict:
        """Analyze performance by time patterns"""
        try:
            # Analyze by hour of day
            hour_performance = {}

            for trade in trades:
                timestamp_str = trade.get('timestamp')
                if not timestamp_str:
                    continue

                try:
                    dt = datetime.fromisoformat(timestamp_str)
                    hour = dt.hour

                    if hour not in hour_performance:
                        hour_performance[hour] = []

                    hour_performance[hour].append(trade)
                except:
                    continue

            # Calculate win rate by hour
            hour_analysis = {}
            for hour, hour_trades in hour_performance.items():
                if len(hour_trades) < 5:  # Need minimum sample
                    continue

                wins = sum(1 for t in hour_trades if t.get('won', False))
                win_rate = (wins / len(hour_trades) * 100) if hour_trades else 0

                hour_analysis[hour] = {
                    'trades': len(hour_trades),
                    'win_rate': win_rate
                }

            return hour_analysis

        except Exception as e:
            logger.error(f"Failed to analyze time patterns: {e}")
            return {}

    def _calculate_sharpe(self, trades: List[Dict]) -> float:
        """Calculate Sharpe ratio (return / volatility)"""
        if len(trades) < 10:
            return 0.0

        try:
            import numpy as np

            # Handle both 'profit' (new) and 'pnl' (old) field names
            returns = [t.get('profit') or t.get('pnl', 0) for t in trades]
            mean_return = np.mean(returns)
            std_return = np.std(returns)

            if std_return == 0:
                return 0.0

            sharpe = mean_return / std_return
            return sharpe

        except:
            return 0.0

    def analyze_volatility(self, historical_data) -> Dict:
        """Analyze current vs historical volatility to suggest trading mode."""
        try:
            import numpy as np
            results = {}

            for coin in ['BTC', 'ETH', 'SOL']:
                # Get last 24h of hourly candles
                recent_closes = historical_data.get_recent_closes(coin, '1h', 24)
                # Get last 7d of hourly candles (for baseline)
                baseline_closes = historical_data.get_recent_closes(coin, '1h', 168)

                if len(recent_closes) < 6 or len(baseline_closes) < 24:
                    continue

                recent_returns = np.diff(np.log(recent_closes))
                baseline_returns = np.diff(np.log(baseline_closes))

                recent_vol = float(np.std(recent_returns) * np.sqrt(24 * 365))
                baseline_vol = float(np.std(baseline_returns) * np.sqrt(24 * 365))
                assumed_vol = {'BTC': 0.80, 'ETH': 0.90, 'SOL': 1.10}.get(coin, 0.8)

                results[coin] = {
                    'recent_vol': recent_vol,
                    'baseline_vol': baseline_vol,
                    'assumed_vol': assumed_vol,
                    'vol_ratio': assumed_vol / max(recent_vol, 0.01),
                    'is_low_vol': recent_vol < baseline_vol * 0.7  # 30%+ below baseline
                }

            # Generate suggestion
            low_vol_coins = [c for c, v in results.items() if v.get('is_low_vol')]
            avg_vol_ratio = float(np.mean([v['vol_ratio'] for v in results.values()])) if results else 1.0

            return {
                'results': results,
                'low_vol_coins': low_vol_coins,
                'avg_vol_ratio': avg_vol_ratio,
                'suggest_low_vol_lotto': avg_vol_ratio >= 1.5,
                'suggest_wider_distance': avg_vol_ratio >= 1.3
            }
        except Exception as e:
            logger.error(f"Volatility analysis failed: {e}")
            return {}

    def _generate_recommendations(self, mode_analysis: Dict,
                                 time_analysis: Dict,
                                 vol_analysis: Dict = None) -> List[str]:
        """Generate human-readable recommendations"""
        recommendations = []

        # Mode recommendation
        if mode_analysis:
            best_mode = max(mode_analysis.items(),
                          key=lambda x: x[1].get('sharpe', 0))

            mode_name = best_mode[0]
            stats = best_mode[1]

            recommendations.append(
                f"Best Mode: {mode_name.upper()} "
                f"({stats['win_rate']:.1f}% WR, ${stats['total_pnl']:+.2f} P&L, Sharpe: {stats['sharpe']:.2f})"
            )

        # Time recommendation
        if time_analysis:
            best_hours = sorted(time_analysis.items(),
                              key=lambda x: x[1]['win_rate'],
                              reverse=True)[:3]

            if best_hours:
                hour_list = ", ".join([f"{h}:00" for h, _ in best_hours])
                recommendations.append(f"Best Trading Hours (UTC): {hour_list}")

        # Volatility-based suggestion
        if vol_analysis and vol_analysis.get('suggest_low_vol_lotto'):
            ratio = vol_analysis['avg_vol_ratio']
            recommendations.append(
                f"Low volatility detected (ratio={ratio:.1f}x) — Consider Mode F (Low-Vol Lotto)"
            )
        elif vol_analysis and vol_analysis.get('suggest_wider_distance'):
            ratio = vol_analysis['avg_vol_ratio']
            recommendations.append(
                f"Below-average volatility (ratio={ratio:.1f}x) — Vol-scaled distance guard active"
            )

        return recommendations

    def format_for_display(self, analysis: Dict) -> str:
        """Format analysis for CLI display"""
        if not analysis.get('has_recommendations'):
            return analysis.get('reason', 'No recommendations available')

        output = []
        output.append("=" * 70)
        output.append("HISTORICAL PERFORMANCE ANALYSIS")
        output.append("=" * 70)
        output.append("")
        output.append(f"Total Trades Analyzed: {analysis['total_trades']}")
        output.append("")

        # Recommendations
        output.append("RECOMMENDATIONS:")
        for i, rec in enumerate(analysis['recommendations'], 1):
            output.append(f"  {i}. {rec}")

        output.append("")
        output.append("=" * 70)

        return "\n".join(output)

    def analyze_recent_mode_performance(self, hours: int = 12) -> Dict:
        """
        Analyze recent resolved markets to recommend the best trading mode.

        Fetches last N hours of Gamma API + Binance data and simulates modes A/D/F.
        Returns result dict from ModeAnalyzer.run_analysis() or empty dict on error.
        """
        try:
            from scripts.analyze_best_mode import ModeAnalyzer
            analyzer = ModeAnalyzer(hours=hours, coin_slug='btc')
            return analyzer.run_analysis()
        except Exception as e:
            logger.debug(f"Mode performance analysis failed: {e}")
            return {}
