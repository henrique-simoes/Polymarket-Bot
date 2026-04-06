"""
Persistence Module - Handles saving/loading trade history and stats
Thread-safe with atomic writes to prevent data corruption.
"""
import json
import os
import tempfile
import logging
from datetime import datetime, timedelta, timezone
from threading import Lock

logger = logging.getLogger("Persistence")

# Global file lock for all JSON persistence operations
_file_lock = Lock()


def atomic_json_write(filepath: str, data, indent: int = 2):
    """
    Write JSON data atomically using temp file + os.replace.
    Prevents corruption if the process crashes mid-write.
    """
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    dir_name = os.path.dirname(filepath) or '.'
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=dir_name, suffix='.tmp',
                                          delete=False) as tmp:
            json.dump(data, tmp, indent=indent, default=str)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = tmp.name
        os.replace(tmp_path, filepath)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except (OSError, UnboundLocalError):
            pass
        raise


def safe_json_load(filepath: str, default=None):
    """
    Load JSON with proper error handling. Returns default on failure.
    """
    if default is None:
        default = []
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted JSON in {filepath}: {e}")
        # Try to preserve corrupted file for recovery
        backup = filepath + '.corrupted'
        try:
            os.replace(filepath, backup)
            logger.warning(f"Corrupted file moved to {backup}")
        except OSError:
            pass
        return default
    except Exception as e:
        logger.error(f"Failed to load {filepath}: {e}")
        return default


class TradeHistoryManager:
    def __init__(self, filepath='data/trade_history.json'):
        self.filepath = filepath
        self._lock = Lock()
        self.history = self._load_history()

    def _load_history(self):
        return safe_json_load(self.filepath, default=[])

    def save_trade(self, trade_data: dict):
        if isinstance(trade_data.get('timestamp'), datetime):
            trade_data['timestamp'] = trade_data['timestamp'].isoformat()
        with self._lock:
            self.history.append(trade_data)
            logger.info(f"Trade saved: {trade_data.get('coin')} {trade_data.get('prediction')} - Won: {trade_data.get('won')} (total: {len(self.history)})")
            self._save_to_disk()

    def _save_to_disk(self):
        """Save with atomic write (caller must hold self._lock)."""
        atomic_json_write(self.filepath, self.history)

    def get_stats(self):
        """Calculate stats for All Time, 24h, 1h (Filtered for REAL trades only)"""
        # Filter out virtual trades if they accidentally leaked into real history
        real_history = [t for t in self.history if t.get('mode') != 'VIRTUAL']
        
        now = datetime.now()
        one_day = now - timedelta(days=1)
        one_hour = now - timedelta(hours=1)

        def calc(trades):
            if not trades: return {'pnl': 0.0, 'wr': 0.0, 'count': 0}
            settled = [t for t in trades if t.get('won') is not None]
            wins = sum(1 for t in settled if t.get('won'))
            pnl = sum((t.get('profit') or 0) for t in trades)
            return {
                'pnl': pnl,
                'wr': (wins / len(settled)) * 100 if settled else 0.0,
                'count': len(trades)
            }

        all_time = calc(real_history)

        # Filter by time (parsing isoformat)
        trades_24h = []
        trades_1h = []

        for t in real_history:
            try:
                ts_raw = t.get('timestamp', '')
                if isinstance(ts_raw, (int, float)):
                    # Epoch timestamp (e.g. from Data API wallet activity)
                    t_time = datetime.fromtimestamp(ts_raw)
                elif isinstance(ts_raw, str) and ts_raw:
                    ts_str = ts_raw.replace('Z', '+00:00')
                    if '+' not in ts_str and 'T' in ts_str:
                        t_time = datetime.fromisoformat(ts_str)
                    else:
                        t_time = datetime.fromisoformat(ts_str).replace(tzinfo=None)
                else:
                    continue
                if t_time > one_day: trades_24h.append(t)
                if t_time > one_hour: trades_1h.append(t)
            except (ValueError, TypeError, OSError) as e:
                logger.debug(f"Skipping trade with bad timestamp: {e}")

        stats_24h = calc(trades_24h)
        stats_1h = calc(trades_1h)

        # Calculate Current Streak (only from settled trades)
        streak = 0
        if self.history:
            try:
                sorted_trades = sorted(self.history, key=lambda x: x.get('timestamp', ''))
                settled_sorted = [t for t in sorted_trades if t.get('won') is not None]
                if settled_sorted:
                    last_res = settled_sorted[-1].get('won')
                    for t in reversed(settled_sorted):
                        if t.get('won') == last_res:
                            streak += 1 if last_res else -1
                        else:
                            break
            except (ValueError, TypeError) as e:
                logger.debug(f"Error calculating streak: {e}")

        return {
            'all': all_time,
            '24h': stats_24h,
            '1h': stats_1h,
            'win_rate': (all_time['wr'] / 100.0) if all_time['count'] > 0 else 0.5,
            'current_streak': streak
        }
