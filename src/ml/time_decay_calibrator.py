"""
Time-Decay Strategy ML Calibrator

Purpose: Learn when Black-Scholes is accurate vs overconfident in 15-minute markets.

Problem:
  Black-Scholes assumes constant volatility and log-normal returns,
  but crypto markets have:
  - Volatility clustering (high vol follows high vol)
  - Fat tails (black swan events)
  - Momentum/mean-reversion patterns

Solution:
  ML model learns: "Given BS edge, actual win probability"

Example:
  BS says: 95% probability, market shows 70% → 25% edge
  ML learns: "Under these conditions, BS 95% actually wins 88%"
  Adjusted edge: 88% - 70% = 18% (still strong, but calibrated)
"""

import numpy as np
import json
import os
import logging
from datetime import datetime
from typing import Dict, Optional, List
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score

logger = logging.getLogger("TimeDecay")  # Use dedicated Time-Decay log file


class TimeDecayCalibrator:
    """
    Calibrates Black-Scholes predictions for 15-minute crypto markets.

    Learns:
    1. When BS overestimates certainty (predicts 99% but actual is 85%)
    2. Price-level patterns (70¢ vs 80¢ vs 90¢ behavior)
    3. Time-to-expiry optimal windows (3min vs 5min)
    4. Volatility impact (low vol vs high vol periods)
    5. Orderbook and VWAP patterns
    """

    def __init__(self, data_file: str = "data/time_decay_calibration.json", analytics=None):
        self.data_file = data_file
        self.trades = []
        self.model = None
        self.is_trained = False
        self.training_count = 0  # Track how many times trained
        self.last_accuracy = 0.0  # Last training accuracy
        self.analytics = analytics  # Analytics tracker (optional)

        # Feature names for display (14 features: 10 original + 3 dynamic window + 1 fallback)
        self.feature_names = [
            'bs_edge',
            'token_price',
            'time_remaining_norm',
            'price_distance_pct',
            'vol_ratio',
            'orderbook_imbalance',
            'bs_confidence',
            'vwap_deviation_pct',
            'price_above_vwap',
            'vwap_trend',
            # Dynamic Entry Window features for learning optimal timing
            'entry_timing_ratio',      # How early in round (0=expiry, 1=start)
            'dynamic_window_norm',     # Allowed window normalized (window/900)
            'edge_at_entry',           # Edge size at entry time
            # Late-Game Fallback feature
            'is_fallback'              # 1 if momentum-following fallback trade, 0 if BS-based
        ]

        self.load_data()

        logger.info(f"Time-Decay Calibrator initialized ({len(self.trades)} trades, {self.training_count} training runs)")

    def load_data(self):
        """Load historical time-decay trades"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.trades = data.get('trades', [])
                    logger.info(f"Loaded {len(self.trades)} time-decay trades")
        except Exception as e:
            logger.error(f"Failed to load calibration data: {e}")
            self.trades = []

    def save_data(self):
        """Save calibration data"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'w') as f:
                json.dump({
                    'trades': self.trades,
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save calibration data: {e}")

    def add_trade(self, trade_data: Dict):
        """
        Record a time-decay trade for calibration learning.

        Required fields:
        - bs_probability: Black-Scholes predicted probability (0-1)
        - market_price: Polymarket token price (0-1)
        - bs_edge: bs_probability - market_price
        - token_price: Actual token price bought (40-90¢)
        - time_remaining: Seconds to expiry when bought
        - price_distance_pct: abs(spot - strike) / strike
        - volatility_realized: Actual volatility during trade
        - volatility_assumed: BS volatility parameter used
        - orderbook_imbalance: Buy pressure at time of entry
        - vwap_deviation_pct: (price - vwap) / vwap
        - price_above_vwap: 1 if above, 0 if below
        - vwap_trend: VWAP trend direction
        - entry_timing_ratio: How early in round (0=expiry, 1=start)
        - dynamic_window_norm: Allowed window normalized (window/900)
        - edge_at_entry: Edge size at entry time
        - won: True/False (actual outcome)
        - coin: BTC/ETH/SOL
        """
        self.trades.append({
            **trade_data,
            'timestamp': datetime.now().isoformat()
        })
        self.save_data()

        # Log progress
        coin = trade_data.get('coin', 'UNKNOWN')
        won = trade_data.get('won', False)
        token_price = trade_data.get('token_price', 0)
        bs_edge = trade_data.get('bs_edge', 0)

        result = "✓ WON" if won else "✗ LOST"
        logger.info(f"[TRADE #{len(self.trades)}] {coin} @ {token_price*100:.0f}¢ | BS Edge: {bs_edge*100:.1f}% | {result}")

        # Show progress to training threshold
        if len(self.trades) < 50:
            remaining = 50 - len(self.trades)
            logger.info(f"  Progress to ML training: {len(self.trades)}/50 ({remaining} more trades needed)")

        # Train at 50 trades (first time)
        if len(self.trades) == 50:
            logger.info(f"\n{'='*70}")
            logger.info(f"THRESHOLD REACHED: 50 trades collected - Starting ML training!")
            logger.info(f"{'='*70}\n")
            self.train()

        # Retrain every 10 trades after initial training
        elif len(self.trades) > 50 and len(self.trades) % 10 == 0:
            logger.info(f"\n[RETRAIN] {len(self.trades)} trades reached - Retraining ML model...")
            self.train()

    def _get_feature_description(self, feature_name: str) -> str:
        """Get human-readable description for a feature"""
        descriptions = {
            'bs_edge': 'Black-Scholes edge magnitude (fair_value - market_price)',
            'token_price': 'Token price bought (60-90¢ range)',
            'time_remaining_norm': 'Time to expiry normalized (0-1, where 1=300s)',
            'price_distance_pct': 'Distance from strike price (% move)',
            'vol_ratio': 'Realized volatility / Assumed volatility ratio',
            'orderbook_imbalance': 'Order flow imbalance (-1=sell pressure, +1=buy pressure)',
            'bs_confidence': 'How extreme BS prediction is (distance from 50%)',
            'vwap_deviation_pct': 'VWAP: Price deviation from volume-weighted average (%)',
            'price_above_vwap': 'VWAP: Binary flag - 1 if price above VWAP, 0 if below',
            'vwap_trend': 'VWAP: Trend direction (5min vs 10min VWAP slope)',
            # Dynamic Entry Window features
            'entry_timing_ratio': 'Entry timing: How early in round (0=near expiry, 1=round start)',
            'dynamic_window_norm': 'Dynamic window: Allowed entry window normalized (0-1)',
            'edge_at_entry': 'Edge at entry: BS edge size when trade was placed',
            # Late-Game Fallback feature
            'is_fallback': 'Late-game fallback: 1 if momentum-following (80-85¢), 0 if BS-based'
        }
        return descriptions.get(feature_name, 'Unknown feature')

    def extract_features(self, trade: Dict) -> np.ndarray:
        """
        Extract features for calibration model.

        Features (14 total):
        1. bs_edge: Black-Scholes edge (0-0.50)
        2. token_price: Token price bought (0.40-0.90)
        3. time_remaining_norm: Time remaining normalized (0-1, where 1=300s legacy)
        4. price_distance_pct: Distance from strike (0-0.05)
        5. vol_ratio: realized_vol / assumed_vol (0.5-2.0)
        6. orderbook_imbalance: -1 to +1
        7. bs_confidence: How extreme BS prediction is (distance from 0.5)
        8. vwap_deviation_pct: Price deviation from VWAP (%)
        9. price_above_vwap: 1 if above VWAP, 0 if below
        10. vwap_trend: VWAP trend direction
        11. entry_timing_ratio: How early in round (0=expiry, 1=start of 15min)
        12. dynamic_window_norm: Allowed window normalized by 900s
        13. edge_at_entry: Edge size at entry time
        14. is_fallback: 1 if late-game fallback trade, 0 if BS-based trade
        """
        features = [
            trade.get('bs_edge', 0.0),
            trade.get('token_price', 0.75),
            min(trade.get('time_remaining', 300) / 300.0, 1.0),
            trade.get('price_distance_pct', 0.01),
            trade.get('volatility_realized', 0.8) / max(trade.get('volatility_assumed', 0.8), 0.1),
            trade.get('orderbook_imbalance', 0.0),
            abs(trade.get('bs_probability', 0.75) - 0.5),
            trade.get('vwap_deviation_pct', 0.0),
            trade.get('price_above_vwap', 0.5),
            trade.get('vwap_trend', 0.0),
            # Dynamic Entry Window features
            trade.get('entry_timing_ratio', 0.33),  # Default ~5min/15min
            trade.get('dynamic_window_norm', 0.33),  # Default 300s/900s
            trade.get('edge_at_entry', 0.05),        # Default 5% edge
            # Late-Game Fallback feature
            1.0 if trade.get('is_fallback', False) else 0.0
        ]

        return np.array(features)

    def train(self) -> bool:
        """
        Train calibration model.

        Model: Random Forest Classifier (robust to non-linear patterns)
        Target: Won/Lost (binary)
        Output: Calibrated probability of winning

        Returns True if training successful
        """
        if len(self.trades) < 50:
            logger.warning(f"Not enough trades to train calibrator (have {len(self.trades)}, need 50)")
            return False

        try:
            # Extract features and labels
            X = np.array([self.extract_features(t) for t in self.trades])
            y = np.array([1 if t.get('won', False) else 0 for t in self.trades])

            # Train ensemble of models
            logger.info(f"Training Time-Decay Calibrator on {len(self.trades)} trades...")

            # Random Forest (primary model)
            rf = RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                min_samples_split=10,
                min_samples_leaf=5,
                random_state=42
            )
            rf.fit(X, y)

            # Cross-validation score
            cv_scores = cross_val_score(rf, X, y, cv=5, scoring='accuracy')

            self.model = rf
            self.is_trained = True
            self.training_count += 1
            self.last_accuracy = cv_scores.mean()

            logger.info(f"=" * 70)
            logger.info(f"✓ TIME-DECAY ML TRAINING COMPLETE (Run #{self.training_count})")
            logger.info(f"=" * 70)
            logger.info(f"  Training Samples:    {len(self.trades)} trades")
            logger.info(f"  Accuracy:            {cv_scores.mean()*100:.1f}% ± {cv_scores.std()*100:.1f}%")
            logger.info(f"  Win Rate (data):     {y.mean()*100:.1f}%")

            # Feature importance analysis
            importances = rf.feature_importances_

            logger.info(f"\n  Top 5 Predictive Features:")
            for i, idx in enumerate(np.argsort(importances)[-5:][::-1], 1):
                logger.info(f"    {i}. {self.feature_names[idx]:25s} {importances[idx]*100:.1f}%")

            # On first training, list ALL features
            if self.training_count == 1:
                logger.info(f"\n  All Features Used by ML Model:")
                for i, (name, importance) in enumerate(zip(self.feature_names, importances), 1):
                    description = self._get_feature_description(name)
                    logger.info(f"    {i:2d}. {name:25s} {importance*100:5.1f}% - {description}")

            # Record feature importance for analytics
            if self.analytics:
                feature_importance_dict = {
                    name: float(importance) for name, importance in zip(self.feature_names, importances)
                }
                self.analytics.record_feature_importance(feature_importance_dict)

            logger.info(f"=" * 70)

            return True

        except Exception as e:
            logger.error(f"Failed to train Time-Decay Calibrator: {e}")
            return False

    def calibrate_edge(self, bs_probability: float, market_price: float,
                       token_price: float, time_remaining: float,
                       price_distance_pct: float,
                       volatility_realized: float, volatility_assumed: float,
                       orderbook_imbalance: float,
                       vwap_deviation_pct: float = 0.0,
                       price_above_vwap: float = 0.5,
                       vwap_trend: float = 0.0,
                       # NEW: Dynamic Entry Window parameters
                       entry_timing_ratio: float = 0.33,
                       dynamic_window_used: float = 300.0,
                       edge_at_entry: float = 0.05) -> Dict:
        """
        Calibrate Black-Scholes edge using learned patterns.

        Args:
            bs_probability: Black-Scholes calculated probability
            market_price: Current Polymarket token price
            token_price: Token price being bought
            time_remaining: Seconds until expiry
            price_distance_pct: Distance from strike as percentage
            volatility_realized: Actual observed volatility
            volatility_assumed: BS model assumed volatility
            orderbook_imbalance: Order book buy/sell imbalance
            vwap_deviation_pct: Price deviation from VWAP
            price_above_vwap: 1 if price above VWAP, 0 if below
            vwap_trend: VWAP trend direction
            entry_timing_ratio: How early in round (0=expiry, 1=start)
            dynamic_window_used: The window allowed for this edge (seconds)
            edge_at_entry: Edge size at time of entry

        Returns:
            {
                'calibrated_probability': float,  # ML-adjusted probability
                'calibrated_edge': float,          # Adjusted edge
                'bs_edge': float,                  # Original BS edge
                'confidence': float,               # Model confidence (0-1)
                'adjustment_factor': float         # How much ML adjusted (0.8-1.2)
            }
        """
        bs_edge = bs_probability - market_price

        # If not trained, return BS edge unchanged
        if not self.is_trained or self.model is None:
            return {
                'calibrated_probability': bs_probability,
                'calibrated_edge': bs_edge,
                'bs_edge': bs_edge,
                'confidence': 0.0,
                'adjustment_factor': 1.0,
                'note': 'Not calibrated (model not trained yet)'
            }

        try:
            # Build feature vector (13 features)
            features = np.array([[
                bs_edge,
                token_price,
                min(time_remaining / 300.0, 1.0),
                price_distance_pct,
                volatility_realized / max(volatility_assumed, 0.1),
                orderbook_imbalance,
                abs(bs_probability - 0.5),
                vwap_deviation_pct,
                price_above_vwap,
                vwap_trend,
                # NEW: Dynamic Entry Window features
                entry_timing_ratio,
                dynamic_window_used / 900.0,  # Normalize by max possible (15 min)
                edge_at_entry
            ]])

            # Get calibrated probability
            calibrated_prob = self.model.predict_proba(features)[0][1]  # Probability of class 1 (win)

            # Calculate calibrated edge
            calibrated_edge = calibrated_prob - market_price

            # Adjustment factor (how much ML changed BS prediction)
            adjustment_factor = calibrated_prob / max(bs_probability, 0.01)

            # Model confidence (based on tree agreement in Random Forest)
            # Higher confidence when trees agree more
            tree_predictions = [tree.predict(features)[0] for tree in self.model.estimators_]
            confidence = abs(np.mean(tree_predictions) - 0.5) * 2  # Scale to 0-1

            # Record calibration adjustment for analytics
            if self.analytics:
                self.analytics.record_calibration(bs_edge, calibrated_edge, adjustment_factor)

            return {
                'calibrated_probability': calibrated_prob,
                'calibrated_edge': calibrated_edge,
                'bs_edge': bs_edge,
                'confidence': confidence,
                'adjustment_factor': adjustment_factor,
                'note': f'Calibrated: BS {bs_probability:.1%} → ML {calibrated_prob:.1%}'
            }

        except Exception as e:
            logger.error(f"Calibration failed: {e}")
            return {
                'calibrated_probability': bs_probability,
                'calibrated_edge': bs_edge,
                'bs_edge': bs_edge,
                'confidence': 0.0,
                'adjustment_factor': 1.0,
                'note': f'Calibration error: {e}'
            }

    def get_statistics(self) -> Dict:
        """Get calibration statistics"""
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_bs_edge': 0.0,
                'avg_calibration_adjustment': 0.0,
                'is_trained': False,
                'training_count': 0,
                'last_accuracy': 0.0
            }

        wins = sum(1 for t in self.trades if t.get('won', False))
        total = len(self.trades)

        avg_bs_edge = np.mean([t.get('bs_edge', 0.0) for t in self.trades])

        # Calculate average BS overconfidence
        bs_avg_prob = np.mean([t.get('bs_probability', 0.75) for t in self.trades])
        actual_win_rate = wins / total
        overconfidence = bs_avg_prob - actual_win_rate

        return {
            'total_trades': total,
            'win_rate': actual_win_rate,
            'avg_bs_edge': avg_bs_edge,
            'bs_avg_probability': bs_avg_prob,
            'bs_overconfidence': overconfidence,
            'is_trained': self.is_trained,
            'training_count': self.training_count,
            'last_accuracy': self.last_accuracy
        }

    def print_statistics(self):
        """Print calibration statistics"""
        stats = self.get_statistics()

        logger.info("=" * 60)
        logger.info("TIME-DECAY CALIBRATION STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total Trades: {stats['total_trades']}")
        logger.info(f"Win Rate: {stats['win_rate']:.1%}")
        logger.info(f"Avg BS Edge: {stats['avg_bs_edge']:.1%}")

        if stats['total_trades'] > 0:
            logger.info(f"BS Avg Probability: {stats['bs_avg_probability']:.1%}")
            logger.info(f"BS Overconfidence: {stats['bs_overconfidence']:+.1%}")

            if stats['bs_overconfidence'] > 0.05:
                logger.info(f"  → BS is overconfident (predicts higher than actual)")
            elif stats['bs_overconfidence'] < -0.05:
                logger.info(f"  → BS is underconfident (predicts lower than actual)")
            else:
                logger.info(f"  → BS is well-calibrated")

        logger.info(f"Model Trained: {'Yes' if self.is_trained else 'No'}")
        logger.info("=" * 60)
