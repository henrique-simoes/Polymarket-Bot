"""
Machine Learning Models - Ensemble of RF + GB with online learning
"""

import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import os
from datetime import datetime

class EnsembleModel:
    """
    Ensemble of Random Forest + Gradient Boosting
    Supports online learning and model persistence
    """

    def __init__(self, config: dict):
        """
        Initialize ensemble model

        Args:
            config: Configuration dict with model parameters
        """
        self.config = config

        # Random Forest
        rf_config = config.get('random_forest', {})
        self.rf = RandomForestClassifier(
            n_estimators=rf_config.get('n_estimators', 50),
            max_depth=rf_config.get('max_depth', 10),
            min_samples_split=rf_config.get('min_samples_split', 2),
            min_samples_leaf=rf_config.get('min_samples_leaf', 1),
            random_state=42,
            n_jobs=-1  # Use all CPU cores
        )

        # Gradient Boosting
        gb_config = config.get('gradient_boosting', {})
        self.gb = GradientBoostingClassifier(
            n_estimators=gb_config.get('n_estimators', 50),
            max_depth=gb_config.get('max_depth', 5),
            learning_rate=gb_config.get('learning_rate', 0.1),
            min_samples_split=gb_config.get('min_samples_split', 2),
            min_samples_leaf=gb_config.get('min_samples_leaf', 1),
            random_state=42
        )

        # Scaler for feature normalization
        self.scaler = StandardScaler()

        # Training state
        self.is_trained = False
        self.training_samples = 0

    def fit(self, X, y):
        """
        Train both models

        Args:
            X: Features array (n_samples, n_features)
            y: Labels array (n_samples,)
        """
        if len(X) < 10:
            print("Not enough samples to train")
            return

        # Scale features (with zero-variance guard)
        # StandardScaler divides by std - if a feature has zero variance, std=0 → NaN/Inf
        variances = np.var(X, axis=0)
        zero_var_mask = variances < 1e-10
        if np.any(zero_var_mask):
            n_zero = int(np.sum(zero_var_mask))
            print(f"Warning: {n_zero} features have zero variance - adding noise to prevent NaN")
            X = X.copy()
            X[:, zero_var_mask] += np.random.normal(0, 1e-8, size=(X.shape[0], n_zero))

        X_scaled = self.scaler.fit_transform(X)

        # Check if we have at least 2 classes
        unique_classes = len(set(y))
        if unique_classes < 2:
            print(f"Skipping training - only {unique_classes} class in data (need 2)")
            return

        # Train both models with error handling
        try:
            self.rf.fit(X_scaled, y)
            self.gb.fit(X_scaled, y)
            self.is_trained = True
            self.training_samples = len(X)
            print(f"Models trained on {len(X)} samples")
        except ValueError as e:
            print(f"Training error (insufficient class diversity): {e}")
            # Keep using existing model if already trained
            if not self.is_trained:
                print("No existing model - will use fallback predictions")

    def predict_proba(self, X):
        """
        Predict probability using ensemble

        Args:
            X: Features array (n_samples, n_features)

        Returns:
            Array of probabilities [prob_down, prob_up]
        """
        if not self.is_trained:
            # Return 50/50 if not trained
            return np.array([[0.5, 0.5]] * len(X))

        # Scale features
        X_scaled = self.scaler.transform(X)

        # Get probabilities from both models
        rf_proba = self.rf.predict_proba(X_scaled)
        gb_proba = self.gb.predict_proba(X_scaled)

        # Ensemble: average the probabilities
        avg_proba = (rf_proba + gb_proba) / 2

        return avg_proba

    def predict(self, X):
        """
        Predict class (0=DOWN, 1=UP)

        Args:
            X: Features array

        Returns:
            Predicted classes
        """
        proba = self.predict_proba(X)
        return (proba[:, 1] > 0.5).astype(int)

    def save(self, filepath):
        """Save model to disk"""
        try:
            model_data = {
                'rf': self.rf,
                'gb': self.gb,
                'scaler': self.scaler,
                'is_trained': self.is_trained,
                'training_samples': self.training_samples,
                'config': self.config,
                'saved_at': datetime.now().isoformat()
            }

            joblib.dump(model_data, filepath)
            print(f"Model saved to {filepath}")
            return True
        except Exception as e:
            print(f"Error saving model: {e}")
            return False

    def load(self, filepath):
        """Load model from disk"""
        try:
            if not os.path.exists(filepath):
                print(f"Model file not found: {filepath}")
                return False

            model_data = joblib.load(filepath)

            self.rf = model_data['rf']
            self.gb = model_data['gb']
            self.scaler = model_data['scaler']
            self.is_trained = model_data['is_trained']
            self.training_samples = model_data['training_samples']

            print(f"Model loaded from {filepath}")
            print(f"  Trained on {self.training_samples} samples")
            print(f"  Saved at: {model_data.get('saved_at', 'unknown')}")
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False

    def get_feature_importance(self):
        """
        Extract feature importance from trained Random Forest model.

        Random Forest calculates feature importance based on how much each feature
        reduces impurity (Gini importance) across all decision trees.

        Returns:
            numpy.ndarray: Importance scores for each feature (sums to 1.0)
            Returns None if model not trained.
        """
        if not self.is_trained:
            return None

        # Use Random Forest feature importances
        # (Gradient Boosting also has feature_importances_, but RF is more interpretable)
        return self.rf.feature_importances_
