"""
Exit Timing Learner - ML model predicting optimal exit timing
Learns when to sell positions early vs hold to expiry
"""

import numpy as np
import logging
from typing import Dict, Optional, List
from sklearn.ensemble import RandomForestClassifier
import pickle
import os

logger = logging.getLogger("ExitTimingLearner")


class ExitTimingLearner:
    """
    Learns optimal exit timing for positions

    Training Data:
    - For each completed trade, generate samples at different minutes
    - Label: 1 if holding to expiry was better, 0 if exiting early was better
    - Features: Price momentum, P&L%, time remaining, volatility, ML confidence

    Decision:
    - Predict: Should hold (1) or should exit now (0)?
    - Only exit if confidence > threshold (e.g., 70%)
    """

    def __init__(self, model_path: str = 'data/models/exit_timing_model.pkl'):
        """
        Initialize exit timing learner

        Args:
            model_path: Path to save/load model
        """
        self.model_path = model_path
        self.model = RandomForestClassifier(
            n_estimators=50,
            max_depth=8,
            min_samples_split=5,
            random_state=42
        )
        self.is_trained = False
        self.training_samples = []  # Buffer for training samples

        # Load existing model if available
        self.load_model()

        logger.info("Exit Timing Learner initialized")

    def add_training_sample(self, features: np.ndarray, label: int, ev_gain: float):
        """
        Add training sample

        Args:
            features: Feature vector
            label: 1 if should have held, 0 if should have exited
            ev_gain: Expected value gain from correct decision
        """
        self.training_samples.append({
            'features': features,
            'label': label,
            'ev_gain': ev_gain
        })

    def learn_from_completed_trade(self, position: Dict):
        """
        Generate training samples from completed trade

        For each minute during the trade, ask: "Should I have exited here?"
        Label based on whether final P&L was better than P&L at that minute

        Args:
            position: Completed position dict with price_history and pnl_history
        """
        try:
            # Need price and P&L history
            if 'pnl_history' not in position or len(position['pnl_history']) < 5:
                return

            final_pnl = position.get('realized_pnl', 0)
            pnl_history = position['pnl_history']

            # For each point in history (except last few)
            for i in range(len(pnl_history) - 2):
                pnl_at_time = pnl_history[i]['pnl']
                pnl_pct_at_time = pnl_history[i]['pnl_pct']

                # Decision: Was it better to exit at this point or hold?
                ev_gain = final_pnl - pnl_at_time
                label = 1 if final_pnl > pnl_at_time else 0  # 1 = should hold, 0 = should exit

                # Calculate features at this point
                features = self._extract_exit_features(position, i)

                if features is not None:
                    self.add_training_sample(features, label, ev_gain)

            logger.debug(f"Generated {len(pnl_history) - 2} training samples from completed trade")

        except Exception as e:
            logger.error(f"Failed to learn from completed trade: {e}")

    def _extract_exit_features(self, position: Dict, time_index: int) -> Optional[np.ndarray]:
        """
        Extract features for exit decision at specific time point

        Features:
        - Current P&L %
        - P&L momentum (rate of change)
        - Time remaining %
        - Volatility (std of recent P&L)
        - Original ML confidence
        - Current price vs entry price
        """
        try:
            pnl_history = position['pnl_history']
            price_history = position['price_history']

            if time_index >= len(pnl_history) or time_index >= len(price_history):
                return None

            # Current P&L
            current_pnl_pct = pnl_history[time_index]['pnl_pct']

            # P&L momentum (last 5 samples)
            if time_index >= 5:
                recent_pnl = [pnl_history[j]['pnl_pct'] for j in range(time_index - 5, time_index)]
                pnl_momentum = (recent_pnl[-1] - recent_pnl[0]) / 5  # Average change per sample
                pnl_volatility = np.std(recent_pnl)
            else:
                pnl_momentum = 0
                pnl_volatility = 0

            # Time remaining (normalized 0-1)
            entry_time = position.get('entry_time', 0)
            expiry_time = position.get('expiry_time', entry_time + 900)  # 15 min default
            current_time = pnl_history[time_index]['timestamp']
            time_remaining_pct = max(0, (expiry_time - current_time) / (expiry_time - entry_time))

            # Price movement
            entry_price = position.get('entry_price', 0.5)
            current_price = price_history[time_index]['price']
            price_change_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0

            # Original confidence
            ml_confidence = position.get('confidence', 0.5)

            features = np.array([
                current_pnl_pct / 100,  # Normalize
                pnl_momentum / 100,
                pnl_volatility / 100,
                time_remaining_pct,
                price_change_pct,
                ml_confidence
            ])

            return features

        except Exception as e:
            logger.error(f"Failed to extract exit features: {e}")
            return None

    def train(self):
        """Train model on collected samples"""
        if len(self.training_samples) < 50:
            logger.info(f"Not enough samples to train ({len(self.training_samples)}/50)")
            return False

        try:
            # Prepare training data
            X = np.array([s['features'] for s in self.training_samples])
            y = np.array([s['label'] for s in self.training_samples])

            # Train model
            self.model.fit(X, y)
            self.is_trained = True

            # Calculate accuracy
            predictions = self.model.predict(X)
            accuracy = np.mean(predictions == y)

            logger.info(f"Exit timing model trained on {len(self.training_samples)} samples | Accuracy: {accuracy:.1%}")

            # Save model
            self.save_model()

            return True

        except Exception as e:
            logger.error(f"Failed to train exit timing model: {e}")
            return False

    def should_exit(self, position: Dict, current_time: float) -> Dict:
        """
        Predict whether to exit position now

        Args:
            position: Current position dict
            current_time: Current timestamp

        Returns:
            Dict with decision, confidence, ev_hold, ev_exit
        """
        if not self.is_trained:
            return {
                'decision': 'hold',  # Default to hold if not trained
                'confidence': 0.0,
                'reason': 'Model not trained yet'
            }

        try:
            # Extract current features
            # Simulate pnl_history for current state
            features = self._extract_current_features(position, current_time)

            if features is None:
                return {'decision': 'hold', 'confidence': 0.0, 'reason': 'Insufficient data'}

            # Predict
            prediction = self.model.predict([features])[0]
            probabilities = self.model.predict_proba([features])[0]

            # prediction: 0 = exit, 1 = hold
            decision = 'hold' if prediction == 1 else 'exit'
            confidence = probabilities[prediction]

            # Only exit if confidence is high
            EXIT_CONFIDENCE_THRESHOLD = 0.70

            if decision == 'exit' and confidence < EXIT_CONFIDENCE_THRESHOLD:
                decision = 'hold'
                reason = f"Exit confidence too low ({confidence:.1%} < {EXIT_CONFIDENCE_THRESHOLD:.0%})"
            else:
                reason = f"Model prediction: {decision} ({confidence:.1%} confidence)"

            return {
                'decision': decision,
                'confidence': confidence,
                'reason': reason
            }

        except Exception as e:
            logger.error(f"Failed to predict exit decision: {e}")
            return {'decision': 'hold', 'confidence': 0.0, 'reason': f'Error: {e}'}

    def _extract_current_features(self, position: Dict, current_time: float) -> Optional[np.ndarray]:
        """Extract features for current position state"""
        try:
            # Use position's current values
            current_pnl_pct = position.get('pnl_pct', 0)

            # P&L momentum and volatility from history
            pnl_history = position.get('pnl_history', [])
            if len(pnl_history) >= 5:
                recent_pnl = [p['pnl_pct'] for p in pnl_history[-5:]]
                pnl_momentum = (recent_pnl[-1] - recent_pnl[0]) / 5
                pnl_volatility = np.std(recent_pnl)
            else:
                pnl_momentum = 0
                pnl_volatility = 0

            # Time remaining
            entry_time = position.get('entry_time', 0)
            expiry_time = position.get('expiry_time', entry_time + 900)
            time_remaining_pct = max(0, (expiry_time - current_time) / (expiry_time - entry_time))

            # Price change
            entry_price = position.get('entry_price', 0.5)
            current_price = position.get('current_token_price', entry_price)
            price_change_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0

            # ML confidence
            ml_confidence = position.get('confidence', 0.5)

            features = np.array([
                current_pnl_pct / 100,
                pnl_momentum / 100,
                pnl_volatility / 100,
                time_remaining_pct,
                price_change_pct,
                ml_confidence
            ])

            return features

        except Exception as e:
            logger.error(f"Failed to extract current features: {e}")
            return None

    def save_model(self):
        """Save model to disk"""
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'is_trained': self.is_trained,
                    'training_samples_count': len(self.training_samples)
                }, f)
            logger.info(f"Exit timing model saved to {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    def load_model(self):
        """Load model from disk"""
        if not os.path.exists(self.model_path):
            return

        try:
            with open(self.model_path, 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.is_trained = data['is_trained']
                logger.info(f"Exit timing model loaded from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")

    def get_statistics(self) -> Dict:
        """Get learning statistics"""
        return {
            'is_trained': self.is_trained,
            'training_samples': len(self.training_samples),
            'model_path': self.model_path
        }
