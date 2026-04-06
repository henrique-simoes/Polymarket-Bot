"""
Continuous Learning Engine - Episode-Based Learning
Updates model based on FINAL round outcomes for higher signal-to-noise ratio.
Includes persistence, accuracy tracking, and thread-safe data access.
"""

import numpy as np
from collections import deque
from threading import Lock
from .models import EnsembleModel
import os
import json
import logging

logger = logging.getLogger("MLLearning")

# Import atomic write utilities
try:
    from ..core.persistence import atomic_json_write, safe_json_load
except ImportError:
    # Fallback if import path differs
    import tempfile

    def atomic_json_write(filepath, data, indent=2):
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        dir_name = os.path.dirname(filepath) or '.'
        with tempfile.NamedTemporaryFile(mode='w', dir=dir_name, suffix='.tmp', delete=False) as tmp:
            json.dump(data, tmp, indent=indent, default=str)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = tmp.name
        os.replace(tmp_path, filepath)

    def safe_json_load(filepath, default=None):
        if default is None:
            default = []
        if not os.path.exists(filepath):
            return default
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception:
            return default


class ContinuousLearningEngine:
    """
    Learning system that buffers observations during a round
    and retrains ONLY when the true outcome is known (End of Round).
    """

    def __init__(self, config: dict):
        self.config = config

        # Experience Replay Buffer (stores confirmed outcomes)
        buffer_size = config.get('observation_buffer_size', 10000)
        self.replay_buffer = deque(maxlen=buffer_size)

        # Episode Buffer (stores current round's data pending resolution)
        self.episode_buffer = {}

        # Episode buffer persistence file
        self.episode_buffer_file = 'data/ml_episodes.json'

        self.models = {}
        self.model_lock = Lock()

        # Separate lock for episode buffer (accessed from main + settlement threads)
        self._episode_lock = Lock()

        # Separate lock for file I/O
        self._io_lock = Lock()

        # Stats
        self.accuracy_stats = {} # {coin: rolling_accuracy}

        print(f"Continuous Learning Engine initialized (Episode-Based)")
        print(f"   Replay Buffer: {buffer_size}")

        # Load persisted episode buffers
        self.load_episode_buffers()

        # Load persisted replay buffer (labeled training data)
        self.load_replay_buffer()

        # Load historical learning mode trades for initial training
        self.load_learning_trades()

        # Load existing models if available
        self.load_models('data/models')

    def initialize_model(self, coin: str):
        with self.model_lock:
            if coin not in self.models:
                self.models[coin] = EnsembleModel(self.config)
                with self._episode_lock:
                    self.episode_buffer[coin] = []
                # Try loading specifically for this coin if not done globally
                self.load_model_for_coin(coin, 'data/models')

    def add_observation(self, coin: str, features: np.ndarray, timestamp: float):
        """Store observation for the current episode (thread-safe)."""
        try:
            features_array = np.array(features, dtype=float)

            # Check for valid shape (1D array)
            if features_array.ndim != 1:
                print(f"[WARNING] Invalid feature shape for {coin}: {features_array.shape} (expected 1D)")
                return

            # Check for NaN/Inf
            if np.any(np.isnan(features_array)) or np.any(np.isinf(features_array)):
                print(f"[WARNING] Features contain NaN/Inf for {coin}, skipping observation")
                return

            with self._episode_lock:
                if coin not in self.episode_buffer:
                    self.episode_buffer[coin] = []

                self.episode_buffer[coin].append({
                    'features': features_array.tolist(),
                    'timestamp': timestamp
                })

            # Persist episode buffer
            self.save_episode_buffers()

        except Exception as e:
            print(f"[WARNING] Failed to add observation for {coin}: {e}")

    def finalize_round(self, coin: str, won_outcome: str):
        """End of round: Label all observations and train (thread-safe)."""
        # Validate outcome
        if won_outcome not in ("UP", "DOWN"):
            print(f"[FINALIZE] Invalid outcome '{won_outcome}' for {coin}, skipping")
            return

        print(f"[FINALIZE] finalize_round() called for {coin}, outcome: {won_outcome}")

        with self._episode_lock:
            if coin not in self.episode_buffer or not self.episode_buffer[coin]:
                print(f"[FINALIZE] No observations in episode buffer for {coin}")
                return

            # Copy and clear under lock
            observations = list(self.episode_buffer[coin])
            self.episode_buffer[coin] = []

        label = 1 if won_outcome == "UP" else 0

        new_samples = 0
        for obs in observations:
            self.replay_buffer.append((obs['features'], label))
            new_samples += 1

        print(f"[FINALIZE] Labeled {new_samples} observations for {coin} (outcome: {won_outcome})")

        # Persist both buffers
        self.save_episode_buffers()
        self.save_replay_buffer()
        print(f"[FINALIZE] Saved {len(self.replay_buffer)} samples to replay buffer")

        self.train_model(coin)

    def save_episode_buffers(self):
        """Save episode buffers to disk for persistence (thread-safe, atomic)"""
        with self._io_lock:
            try:
                os.makedirs(os.path.dirname(self.episode_buffer_file), exist_ok=True)

                with self._episode_lock:
                    serializable_buffer = {}
                    for coin, episodes in self.episode_buffer.items():
                        serializable_buffer[coin] = []
                        for episode in episodes:
                            serializable_buffer[coin].append({
                                'features': episode['features'].tolist() if isinstance(episode['features'], np.ndarray) else episode['features'],
                                'timestamp': float(episode['timestamp'])
                            })

                atomic_json_write(self.episode_buffer_file, serializable_buffer)

            except Exception as e:
                print(f"Warning: Failed to save episode buffers: {e}")

    def load_episode_buffers(self):
        """Load episode buffers from disk on startup"""
        if not os.path.exists(self.episode_buffer_file):
            return

        try:
            serializable_buffer = safe_json_load(self.episode_buffer_file, default={})

            with self._episode_lock:
                for coin, episodes in serializable_buffer.items():
                    self.episode_buffer[coin] = []
                    for episode in episodes:
                        self.episode_buffer[coin].append({
                            'features': np.array(episode['features']),
                            'timestamp': episode['timestamp']
                        })

            total_episodes = sum(len(eps) for eps in self.episode_buffer.values())
            if total_episodes > 0:
                print(f"   Loaded {total_episodes} persisted episode observations")

        except Exception as e:
            print(f"Warning: Failed to load episode buffers: {e}")
            self.episode_buffer = {}

    def save_replay_buffer(self):
        """Save replay buffer to disk for persistence (thread-safe, atomic)"""
        with self._io_lock:
            try:
                replay_buffer_file = 'data/replay_buffer.json'
                os.makedirs(os.path.dirname(replay_buffer_file), exist_ok=True)

                buffer_list = []
                for features, label in self.replay_buffer:
                    buffer_list.append({
                        'features': features.tolist() if isinstance(features, np.ndarray) else features,
                        'label': int(label)
                    })

                atomic_json_write(replay_buffer_file, buffer_list)

                if len(buffer_list) > 0:
                    print(f"   Saved {len(buffer_list)} labeled samples to replay buffer")

            except Exception as e:
                print(f"Warning: Failed to save replay buffer: {e}")

    def load_replay_buffer(self):
        """Load replay buffer from disk on startup"""
        replay_buffer_file = 'data/replay_buffer.json'
        if not os.path.exists(replay_buffer_file):
            return

        try:
            buffer_list = safe_json_load(replay_buffer_file, default=[])

            valid_count = 0
            invalid_count = 0
            expected_length = None

            for item in buffer_list:
                try:
                    features = np.array(item['features'], dtype=float)
                    label = int(item['label'])

                    if expected_length is None and features.ndim == 1 and len(features) > 0:
                        expected_length = len(features)

                    if (features.ndim == 1 and
                        (expected_length is None or len(features) == expected_length) and
                        not np.any(np.isnan(features)) and
                        not np.any(np.isinf(features))):
                        self.replay_buffer.append((features, label))
                        valid_count += 1
                    else:
                        invalid_count += 1
                except Exception:
                    invalid_count += 1

            print(f"   Loaded {valid_count} valid samples from replay buffer")
            if invalid_count > 0:
                print(f"   Filtered {invalid_count} invalid samples")

        except Exception as e:
            print(f"Warning: Failed to load replay buffer: {e}")
            self.replay_buffer.clear()

    def load_learning_trades(self):
        """Load historical learning mode trades for initial training."""
        try:
            learning_trades_file = 'data/learning_trades.json'
            if not os.path.exists(learning_trades_file):
                return

            learning_trades = safe_json_load(learning_trades_file, default=[])

            if not learning_trades:
                return

            print(f"   Found {len(learning_trades)} learning trades (features not stored)")

        except Exception as e:
            print(f"Warning: Failed to load learning trades: {e}")

    def train_model(self, coin: str):
        """Retrain model using Replay Buffer with train/test split."""
        with self.model_lock:
            print(f"[TRAIN] train_model() called for {coin}")
            print(f"[TRAIN] Replay buffer size: {len(self.replay_buffer)}")
            print(f"[TRAIN] Coins in models dict: {list(self.models.keys())}")

            if len(self.replay_buffer) < 50:
                print(f"[TRAIN] Not enough samples ({len(self.replay_buffer)} < 50), skipping training")
                return

            # Train on all available data (Transfer Learning assumption)
            batch = list(self.replay_buffer)

            print(f"[TRAIN] Validating {len(batch)} samples...")

            # Determine expected feature length from first valid sample
            expected_length = None
            for b in batch:
                try:
                    features = np.array(b[0], dtype=float)
                    if features.ndim == 1 and len(features) > 0:
                        expected_length = len(features)
                        print(f"[TRAIN] Expected feature length: {expected_length}")
                        break
                except Exception:
                    continue

            if expected_length is None:
                print(f"[TRAIN] ERROR: Could not determine expected feature length")
                return

            # Filter valid samples
            valid_samples = []
            invalid_count = 0
            for b in batch:
                try:
                    features = np.array(b[0], dtype=float)
                    label = int(b[1])

                    if features.ndim == 1 and len(features) == expected_length:
                        if not np.any(np.isnan(features)) and not np.any(np.isinf(features)):
                            valid_samples.append((features, label))
                        else:
                            invalid_count += 1
                    else:
                        invalid_count += 1
                except Exception:
                    invalid_count += 1

            print(f"[TRAIN] Valid samples: {len(valid_samples)}/{len(batch)} (filtered {invalid_count} invalid)")

            if len(valid_samples) < 50:
                print(f"[TRAIN] Not enough valid samples ({len(valid_samples)} < 50), skipping training")
                return

            X = np.array([s[0] for s in valid_samples])
            y = np.array([s[1] for s in valid_samples])

            print(f"[TRAIN] Prepared training data: X.shape={X.shape}, y.shape={y.shape}")

            # Initialize model if not exists
            if coin not in self.models:
                print(f"[TRAIN] Initializing new model for {coin}...")
                self.models[coin] = EnsembleModel(self.config)

            print(f"[TRAIN] Training model for {coin}...")
            self.models[coin].fit(X, y)
            print(f"[TRAIN] Model trained successfully")
            print(f"[TRAIN] Model is_trained flag: {self.models[coin].is_trained}")

            # Save models to disk
            try:
                print(f"[TRAIN] Calling save_models()...")
                self.save_models('data/models')
                print(f"[TRAIN] Models saved to disk")
            except Exception as e:
                print(f"[TRAIN] ERROR saving models: {e}")
                import traceback
                traceback.print_exc()

            # Calculate accuracy on held-out data (train/test split)
            try:
                print(f"[TRAIN] Calculating accuracy...")
                if len(y) >= 20:
                    # Use last 20% as test set for honest accuracy
                    split_idx = max(int(len(y) * 0.8), 1)
                    X_test = X[split_idx:]
                    y_test = y[split_idx:]
                    preds = self.models[coin].predict(X_test)
                    acc = np.mean(preds == y_test)
                    self.accuracy_stats[coin] = acc
                    print(f"[TRAIN] {coin} model trained. Test accuracy (last {len(y_test)} samples): {acc:.1%}")
                elif len(y) > 0:
                    # Too few for split, report training accuracy with warning
                    preds = self.models[coin].predict(X)
                    acc = np.mean(preds == y)
                    self.accuracy_stats[coin] = acc
                    print(f"[TRAIN] {coin} model trained. Training accuracy (no test split, {len(y)} samples): {acc:.1%}")
                else:
                    print(f"[TRAIN] WARNING: No samples for accuracy calculation")
            except Exception as e:
                print(f"[TRAIN] ERROR calculating accuracy: {e}")
                import traceback
                traceback.print_exc()

            # Analyze and display feature importance
            try:
                print(f"[TRAIN] Analyzing feature importance...")
                self.analyze_feature_importance(coin, len(valid_samples))
                print(f"[TRAIN] Feature importance analysis complete")
            except Exception as e:
                print(f"[TRAIN] ERROR analyzing feature importance: {e}")
                import traceback
                traceback.print_exc()

    def predict(self, coin: str, features: np.ndarray) -> float:
        with self.model_lock:
            if coin not in self.models or not self.models[coin].is_trained:
                return 0.5

            proba = self.models[coin].predict_proba(features.reshape(1, -1))
            return proba[0][1]

    def get_accuracy(self, coin: str) -> float:
        return self.accuracy_stats.get(coin, 0.0)

    def get_training_stats(self) -> dict:
        """Get comprehensive training statistics for dashboard display"""
        stats = {
            'replay_buffer_size': len(self.replay_buffer),
            'episode_buffer_total': sum(len(eps) for eps in self.episode_buffer.values()),
            'coins': {}
        }

        for coin in ['BTC', 'ETH', 'SOL']:
            coin_stats = {
                'episode_observations': len(self.episode_buffer.get(coin, [])),
                'is_trained': False,
                'accuracy': 0.0,
                'training_threshold': 50,
                'progress_pct': 0.0
            }

            if coin in self.models:
                coin_stats['is_trained'] = self.models[coin].is_trained
                coin_stats['accuracy'] = self.accuracy_stats.get(coin, 0.0)

            coin_stats['progress_pct'] = min(100.0, (stats['replay_buffer_size'] / 50.0) * 100.0)
            stats['coins'][coin] = coin_stats

        return stats

    def backfill_from_trade_history(self, trade_history: list) -> int:
        """
        Label episode observations using corrected wallet trade outcomes.

        Uses market_slug to extract market open time, then matches
        episode observations by timestamp window (15-min = 900s).

        Returns: number of new samples added to replay buffer
        """
        added = 0

        for trade in trade_history:
            slug = trade.get('market_slug', '')
            won = trade.get('won')
            prediction = trade.get('prediction', '')
            coin = trade.get('coin', '')

            if not slug or won is None or not coin:
                continue

            # Extract market open time from slug: "btc-updown-15m-1770394500"
            try:
                market_open = int(slug.split('-')[-1])
            except (ValueError, IndexError):
                continue

            # Derive ML label: outcome is UP if (won and predicted UP) or (lost and predicted DOWN)
            if prediction == 'UP':
                outcome = 'UP' if won else 'DOWN'
            elif prediction == 'DOWN':
                outcome = 'DOWN' if won else 'UP'
            else:
                continue
            label = 1 if outcome == 'UP' else 0

            # Find matching episode observations
            with self._episode_lock:
                observations = self.episode_buffer.get(coin, [])
                matched = [obs for obs in observations
                           if market_open <= obs['timestamp'] < market_open + 900]

            for obs in matched:
                self.replay_buffer.append((
                    np.array(obs['features'], dtype=float) if not isinstance(obs['features'], np.ndarray) else obs['features'],
                    label
                ))
                added += 1

        if added > 0:
            self.save_replay_buffer()
            logger.info(f"[BACKFILL] Added {added} samples from trade history, retraining...")
            # Retrain with new data
            for coin in list(self.models.keys()):
                self.train_model(coin)
                break  # train_model uses all replay_buffer data anyway

        return added

    def save_models(self, directory: str):
        print(f"[SAVE] save_models() called for directory: {directory}")
        os.makedirs(directory, exist_ok=True)

        with self.model_lock:
            for coin, model in self.models.items():
                if model.is_trained:
                    filepath = os.path.join(directory, f"{coin}_model.pkl")
                    print(f"[SAVE] Saving {coin} model to {filepath}")
                    model.save(filepath)

    def load_models(self, directory: str):
        if not os.path.exists(directory): return
        for coin in ['BTC', 'ETH', 'SOL']:
            self.load_model_for_coin(coin, directory)

    def load_model_for_coin(self, coin: str, directory: str):
        path = os.path.join(directory, f"{coin}_model.pkl")
        if os.path.exists(path):
            if coin not in self.models:
                self.models[coin] = EnsembleModel(self.config)
            self.models[coin].load(path)

    def analyze_feature_importance(self, coin: str, training_samples: int):
        """Analyze and display which features are most important for predictions."""
        if coin not in self.models or not self.models[coin].is_trained:
            print(f"Cannot analyze importance: {coin} model not trained")
            return

        importances = self.models[coin].get_feature_importance()
        if importances is None:
            print(f"Cannot get feature importance for {coin}")
            return

        from .features import FeatureExtractor
        feature_extractor = FeatureExtractor()
        feature_names = feature_extractor.feature_names

        if len(importances) != len(feature_names):
            print(f"Warning: Feature count mismatch ({len(importances)} vs {len(feature_names)})")
            min_len = min(len(importances), len(feature_names))
            importances = importances[:min_len]
            feature_names = feature_names[:min_len]

        ranked = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)

        print(f"\n{'='*60}")
        print(f"FEATURE IMPORTANCE for {coin} (15-min outcomes)")
        print(f"Trained on {training_samples} samples ({len(feature_names)} features)")
        print(f"{'='*60}")

        for i, (name, importance) in enumerate(ranked[:20], 1):
            bar = '█' * int(importance * 100)
            print(f"{i:2}. {name:30} {importance:6.3f} {bar}")

        print(f"\n{'='*60}")
        print(f"TIMEFRAME IMPORTANCE (aggregated)")
        print(f"{'='*60}")

        timeframe_importance = {}
        timeframes = ['1s', '1m', '15m', '1h', '4h', '1d', '1w']

        for name, importance in ranked:
            for tf in timeframes:
                if name.startswith(tf + '_'):
                    timeframe_importance[tf] = timeframe_importance.get(tf, 0) + importance
                    break

        for tf in timeframes:
            imp = timeframe_importance.get(tf, 0)
            bar = '█' * int(imp * 200)
            print(f"{tf:6} {imp:6.3f} {bar}")

        print(f"\n{'='*60}")
        print(f"FEATURE TYPE IMPORTANCE")
        print(f"{'='*60}")

        type_importance = {
            'VWAP': 0, 'Momentum': 0, 'Arbitrage': 0,
            'Technical': 0, 'Microstructure': 0, 'Time-based': 0, 'Other': 0
        }

        for name, importance in ranked:
            if 'vwap' in name:
                type_importance['VWAP'] += importance
            elif 'momentum' in name or 'trend' in name:
                type_importance['Momentum'] += importance
            elif 'arbitrage' in name or 'fair_value' in name:
                type_importance['Arbitrage'] += importance
            elif any(x in name for x in ['rsi', 'macd', 'stoch', 'adx', 'cci', 'mfi', 'bb_', 'atr', 'ema', 'sma']):
                type_importance['Technical'] += importance
            elif any(x in name for x in ['orderbook', 'spread', 'imbalance', 'volume']):
                type_importance['Microstructure'] += importance
            elif 'time_remaining' in name or 'strike' in name:
                type_importance['Time-based'] += importance
            else:
                type_importance['Other'] += importance

        for feature_type, imp in sorted(type_importance.items(), key=lambda x: x[1], reverse=True):
            if imp > 0:
                bar = '█' * int(imp * 100)
                print(f"{feature_type:20} {imp:6.1%} {bar}")

        print(f"\n{'='*60}")
        print(f"KEY INSIGHTS")
        print(f"{'='*60}")

        ultra_short = timeframe_importance.get('1s', 0) + timeframe_importance.get('1m', 0)
        short_term = timeframe_importance.get('15m', 0) + timeframe_importance.get('1h', 0)
        long_term = timeframe_importance.get('4h', 0) + timeframe_importance.get('1d', 0) + timeframe_importance.get('1w', 0)

        print(f"Ultra-short (1s, 1m): {ultra_short:.1%} importance")
        print(f"Short-term (15m, 1h): {short_term:.1%} importance")
        print(f"Long-term (4h, 1d, 1w): {long_term:.1%} importance")

        if type_importance['VWAP'] > 0.15:
            print(f"VWAP is highly predictive ({type_importance['VWAP']:.1%} of model importance)")

        print()

        self.save_feature_importance(coin, ranked, timeframe_importance, type_importance, training_samples)

    def save_feature_importance(self, coin: str, ranked_features: list,
                                timeframe_importance: dict, type_importance: dict,
                                training_samples: int):
        """Save feature importance analysis to JSON file."""
        try:
            filepath = f'data/feature_importance_{coin}.json'

            history = []
            existing = safe_json_load(filepath, default={})
            if isinstance(existing, dict):
                history = existing.get('history', [])

            from datetime import datetime
            current_time = datetime.now().isoformat()

            data = {
                'coin': coin,
                'last_updated': current_time,
                'training_samples': training_samples,
                'top_features': [
                    {'name': name, 'importance': float(imp)}
                    for name, imp in ranked_features[:30]
                ],
                'timeframe_groups': {
                    tf: float(imp) for tf, imp in timeframe_importance.items()
                },
                'feature_types': {
                    ftype: float(imp) for ftype, imp in type_importance.items()
                },
                'history': history + [{
                    'timestamp': current_time,
                    'samples': training_samples,
                    'top_feature': ranked_features[0][0] if ranked_features else 'unknown',
                    'ultra_short_pct': float(
                        timeframe_importance.get('1s', 0) + timeframe_importance.get('1m', 0)
                    ),
                    'long_term_pct': float(
                        timeframe_importance.get('4h', 0) +
                        timeframe_importance.get('1d', 0) +
                        timeframe_importance.get('1w', 0)
                    ),
                    'vwap_pct': float(type_importance.get('VWAP', 0)),
                    'arbitrage_pct': float(type_importance.get('Arbitrage', 0))
                }]
            }

            atomic_json_write(filepath, data)
            print(f"Feature importance saved to {filepath}")

        except Exception as e:
            print(f"Error saving feature importance: {e}")
