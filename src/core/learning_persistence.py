"""
Learning Mode Persistence - Manages learning trade storage
Thread-safe with atomic writes to prevent data corruption.
"""

import json
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
from threading import Lock

from .persistence import atomic_json_write, safe_json_load

logger = logging.getLogger("LearningPersistence")


class LearningPersistence:
    """
    Manages storage and retrieval of learning mode trades.
    Thread-safe: all file operations are protected by locks.
    """

    def __init__(self, learning_trades_file: str = 'data/learning_trades.json',
                 learning_state_file: str = 'data/learning_state.json'):
        self.learning_trades_file = learning_trades_file
        self.learning_state_file = learning_state_file
        self._lock = Lock()

        # Ensure data directory exists
        os.makedirs(os.path.dirname(learning_trades_file), exist_ok=True)

        # Initialize files if they don't exist
        self._initialize_files()

        logger.info("Learning Persistence initialized")

    def _initialize_files(self):
        """Create empty files if they don't exist"""
        if not os.path.exists(self.learning_trades_file):
            atomic_json_write(self.learning_trades_file, [])

        if not os.path.exists(self.learning_state_file):
            initial_state = {
                'created_at': datetime.now().isoformat(),
                'total_sessions': 0,
                'total_virtual_trades': 0,
                'cumulative_virtual_pnl': 0.0
            }
            atomic_json_write(self.learning_state_file, initial_state)

    def save_trade(self, trade_record: Dict) -> None:
        """Save simulated trade to learning trades file (thread-safe)."""
        with self._lock:
            try:
                trades = safe_json_load(self.learning_trades_file, default=[])
                trades.append(trade_record)
                atomic_json_write(self.learning_trades_file, trades)
                logger.info(f"Saved learning trade: {trade_record.get('coin')} {'WON' if trade_record.get('won') else 'LOST'}")
            except Exception as e:
                logger.error(f"Failed to save learning trade: {e}")

    def load_trades(self, limit: Optional[int] = None) -> List[Dict]:
        """Load learning trades from file."""
        trades = safe_json_load(self.learning_trades_file, default=[])
        if limit:
            return trades[-limit:]
        return trades

    def get_trade_count(self) -> int:
        """Get total number of learning trades"""
        return len(self.load_trades())

    def get_statistics(self) -> Dict:
        """Calculate statistics from learning trades."""
        trades = self.load_trades()

        if not trades:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0
            }

        wins = sum(1 for t in trades if t.get('won', False))
        losses = len(trades) - wins
        win_rate = (wins / len(trades) * 100) if trades else 0.0

        # Handle both 'profit' (new) and 'pnl' (old) field names
        total_pnl = sum(t.get('profit') or t.get('pnl', 0) for t in trades)

        winning_trades = [t for t in trades if t.get('won', False)]
        losing_trades = [t for t in trades if not t.get('won', False)]

        avg_win = sum(t.get('profit') or t.get('pnl', 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0.0
        avg_loss = sum(t.get('profit') or t.get('pnl', 0) for t in losing_trades) / len(losing_trades) if losing_trades else 0.0

        return {
            'total_trades': len(trades),
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss
        }

    def save_state(self, simulator_stats: Dict) -> None:
        """Save current learning session state (thread-safe)."""
        with self._lock:
            try:
                state = safe_json_load(self.learning_state_file, default={})
                state['last_updated'] = datetime.now().isoformat()
                state['total_sessions'] = state.get('total_sessions', 0) + 1
                state['current_virtual_balance'] = simulator_stats.get('virtual_balance', 0)
                state['total_virtual_trades'] = simulator_stats.get('total_trades', 0)
                state['cumulative_virtual_pnl'] = simulator_stats.get('total_pnl', 0)
                atomic_json_write(self.learning_state_file, state)
            except Exception as e:
                logger.error(f"Failed to save learning state: {e}")

    def load_state(self) -> Dict:
        """Load learning session state"""
        return safe_json_load(self.learning_state_file, default={})

    def clear_all_data(self, confirm: bool = False) -> bool:
        """Clear all learning data (USE WITH CAUTION)."""
        if not confirm:
            logger.warning("Clear request ignored - confirm parameter must be True")
            return False

        with self._lock:
            try:
                atomic_json_write(self.learning_trades_file, [])
                initial_state = {
                    'created_at': datetime.now().isoformat(),
                    'total_sessions': 0,
                    'total_virtual_trades': 0,
                    'cumulative_virtual_pnl': 0.0
                }
                atomic_json_write(self.learning_state_file, initial_state)
                logger.warning("All learning data cleared")
                return True
            except Exception as e:
                logger.error(f"Failed to clear learning data: {e}")
                return False
