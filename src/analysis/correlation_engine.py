"""
Correlation Engine - Tracks BTC→ETH/SOL correlation and lead-lag relationships
Calculates rolling correlation, beta, and lead-lag timing
"""

import numpy as np
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger("CorrelationEngine")


class CorrelationEngine:
    """
    Tracks correlation between crypto assets

    Features:
    - 30-day rolling correlation (BTC-ETH, BTC-SOL, ETH-SOL)
    - Beta calculation (expected Δ% for asset given BTC move)
    - Lead-lag detection (BTC typically leads by 30-300 seconds)
    - Correlation confidence for ML features
    """

    def __init__(self, historical_data_manager):
        """
        Initialize correlation engine

        Args:
            historical_data_manager: HistoricalDataManager instance
        """
        self.historical = historical_data_manager
        self.correlations = {}  # Cache current correlations

        # Correlation window (30 days for daily data)
        self.CORRELATION_WINDOW = 30

        logger.info("Correlation Engine initialized")

    def calculate_all_correlations(self) -> Dict:
        """
        Calculate all major correlations

        Returns:
            Dict with BTC-ETH, BTC-SOL, ETH-SOL correlations
        """
        try:
            correlations = {}

            # BTC-ETH
            btc_eth = self.calculate_correlation('BTC', 'ETH', '1d', self.CORRELATION_WINDOW)
            if btc_eth:
                correlations['BTC-ETH'] = btc_eth

            # BTC-SOL
            btc_sol = self.calculate_correlation('BTC', 'SOL', '1d', self.CORRELATION_WINDOW)
            if btc_sol:
                correlations['BTC-SOL'] = btc_sol

            # ETH-SOL
            eth_sol = self.calculate_correlation('ETH', 'SOL', '1d', self.CORRELATION_WINDOW)
            if eth_sol:
                correlations['ETH-SOL'] = eth_sol

            self.correlations = correlations

            logger.info(f"Correlations updated: BTC-ETH={correlations.get('BTC-ETH', {}).get('correlation', 0):.2f}")

            return correlations

        except Exception as e:
            logger.error(f"Failed to calculate correlations: {e}")
            return {}

    def calculate_correlation(self, symbol1: str, symbol2: str,
                            timeframe: str, window: int) -> Optional[Dict]:
        """
        Calculate correlation metrics between two symbols

        Args:
            symbol1: First symbol (typically BTC)
            symbol2: Second symbol (ETH, SOL)
            timeframe: Timeframe for analysis (1d recommended)
            window: Number of periods for rolling window

        Returns:
            Dict with correlation, beta, confidence
        """
        try:
            # Get price data
            closes1 = self.historical.get_recent_closes(symbol1, timeframe, window + 1)
            closes2 = self.historical.get_recent_closes(symbol2, timeframe, window + 1)

            if len(closes1) < window or len(closes2) < window:
                logger.warning(f"Insufficient data for {symbol1}-{symbol2} correlation")
                return None

            # Calculate returns (% change)
            returns1 = np.diff(closes1) / closes1[:-1]
            returns2 = np.diff(closes2) / closes2[:-1]

            # Correlation coefficient
            correlation = np.corrcoef(returns1, returns2)[0, 1]

            # Beta (sensitivity of symbol2 to symbol1)
            # Beta = Cov(returns1, returns2) / Var(returns1)
            covariance = np.cov(returns1, returns2)[0, 1]
            variance1 = np.var(returns1)
            beta = covariance / variance1 if variance1 > 0 else 0.0

            # Confidence (based on sample size and correlation strength)
            confidence = min(0.95, abs(correlation) * (len(returns1) / window))

            return {
                'pair': f"{symbol1}-{symbol2}",
                'correlation': float(correlation),
                'beta': float(beta),
                'confidence': float(confidence),
                'sample_size': len(returns1),
                'calculated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Correlation calculation error for {symbol1}-{symbol2}: {e}")
            return None

    def calculate_lead_lag(self, leader_symbol: str, follower_symbol: str,
                          max_lag_seconds: int = 300) -> Optional[Dict]:
        """
        Calculate lead-lag relationship (how long follower takes to react to leader)

        Args:
            leader_symbol: Leading asset (typically BTC)
            follower_symbol: Following asset (ETH, SOL)
            max_lag_seconds: Maximum lag to check (default 300s = 5 minutes)

        Returns:
            Dict with optimal_lag, correlation_at_lag
        """
        try:
            # Get 1-minute data for recent period
            candles_leader = self.historical.get_candles(leader_symbol, '1h', limit=100)
            candles_follower = self.historical.get_candles(follower_symbol, '1h', limit=100)

            if len(candles_leader) < 50 or len(candles_follower) < 50:
                return None

            # Calculate returns
            closes_leader = np.array([c['close'] for c in candles_leader])
            closes_follower = np.array([c['close'] for c in candles_follower])

            returns_leader = np.diff(closes_leader) / closes_leader[:-1]
            returns_follower = np.diff(closes_follower) / closes_follower[:-1]

            # Cross-correlation at different lags
            # Lag in hours (since using 1h data)
            max_lag_hours = max_lag_seconds // 3600  # Convert seconds to hours
            max_lag_hours = max(1, min(5, max_lag_hours))  # Limit to 1-5 hours

            best_correlation = 0
            best_lag = 0

            for lag in range(0, max_lag_hours + 1):
                if lag >= len(returns_leader):
                    break

                # Align returns with lag
                if lag == 0:
                    corr = np.corrcoef(returns_leader, returns_follower)[0, 1]
                else:
                    corr = np.corrcoef(returns_leader[:-lag], returns_follower[lag:])[0, 1]

                if abs(corr) > abs(best_correlation):
                    best_correlation = corr
                    best_lag = lag

            return {
                'leader': leader_symbol,
                'follower': follower_symbol,
                'optimal_lag_hours': best_lag,
                'correlation_at_lag': float(best_correlation),
                'calculated_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Lead-lag calculation error: {e}")
            return None

    def get_expected_move(self, base_symbol: str, target_symbol: str,
                         base_move_pct: float) -> Optional[float]:
        """
        Predict expected % move in target given % move in base

        Args:
            base_symbol: Base symbol (e.g., BTC)
            target_symbol: Target symbol (e.g., ETH)
            base_move_pct: Observed % move in base (e.g., 0.02 for +2%)

        Returns:
            Expected % move in target based on beta
        """
        pair_key = f"{base_symbol}-{target_symbol}"
        correlation_info = self.correlations.get(pair_key)

        if not correlation_info:
            # Try to calculate on the fly
            correlation_info = self.calculate_correlation(base_symbol, target_symbol, '1d', self.CORRELATION_WINDOW)

        if not correlation_info:
            return None

        beta = correlation_info['beta']
        expected_move = beta * base_move_pct

        return expected_move

    def get_correlation_features(self) -> Dict:
        """
        Get correlation features for ML model

        Returns:
            Dict with correlation values and betas for all pairs
        """
        features = {}

        for pair_key, corr_info in self.correlations.items():
            features[f"{pair_key}_corr"] = corr_info['correlation']
            features[f"{pair_key}_beta"] = corr_info['beta']
            features[f"{pair_key}_conf"] = corr_info['confidence']

        return features

    def get_summary(self) -> Dict:
        """Get summary of all current correlations"""
        summary = {}

        for pair_key, corr_info in self.correlations.items():
            summary[pair_key] = {
                'correlation': corr_info['correlation'],
                'beta': corr_info['beta'],
                'confidence': corr_info['confidence']
            }

        return summary

    def update_correlations(self):
        """Update all correlations (call periodically, e.g., every 15 minutes)"""
        self.calculate_all_correlations()
