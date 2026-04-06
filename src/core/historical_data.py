"""
Historical Data Storage - SQLite database for multi-month price history
Stores 1h, 4h, 1d, 1w candles for long-term trend analysis
"""

import sqlite3
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import os

logger = logging.getLogger("HistoricalData")


class HistoricalDataManager:
    """
    Manages historical price data storage and retrieval

    Features:
    - SQLite database for efficient storage
    - Multi-timeframe data (1h, 4h, 1d, 1w)
    - 6+ months of historical data
    - Fast querying by coin, timeframe, date range
    """

    def __init__(self, db_path: str = 'data/historical_data.db'):
        """
        Initialize historical data manager

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Initialize database
        self._init_database()

        logger.info(f"Historical Data Manager initialized (DB: {db_path})")

    def _get_connection(self):
        """Get a SQLite connection with WAL mode enabled."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_database(self):
        """Create database tables if they don't exist"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Price history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_history (
                    symbol TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    timeframe TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    PRIMARY KEY (symbol, timestamp, timeframe)
                )
            ''')

            # Create indexes for fast queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_price_symbol_time
                ON price_history (symbol, timeframe, timestamp)
            ''')

            conn.commit()
        finally:
            conn.close()

        logger.info("Historical database initialized")

    def store_candles(self, symbol: str, timeframe: str, candles: List[Dict]) -> int:
        """
        Store OHLCV candles to database

        Args:
            symbol: Coin symbol (BTC, ETH, SOL)
            timeframe: Timeframe (1h, 4h, 1d, 1w)
            candles: List of candle dicts with keys: timestamp, open, high, low, close, volume

        Returns:
            Number of candles stored
        """
        if not candles:
            return 0

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            stored = 0
            for candle in candles:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO price_history
                        (symbol, timestamp, timeframe, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        symbol,
                        int(candle['timestamp']),
                        timeframe,
                        float(candle['open']),
                        float(candle['high']),
                        float(candle['low']),
                        float(candle['close']),
                        float(candle.get('volume', 0))
                    ))
                    stored += 1
                except Exception as e:
                    logger.error(f"Failed to store candle for {symbol}: {e}")

            conn.commit()
        finally:
            conn.close()

        logger.info(f"Stored {stored} {timeframe} candles for {symbol}")
        return stored

    def get_candles(self, symbol: str, timeframe: str,
                   start_time: Optional[int] = None,
                   end_time: Optional[int] = None,
                   limit: Optional[int] = None) -> List[Dict]:
        """
        Retrieve candles from database

        Args:
            symbol: Coin symbol
            timeframe: Timeframe
            start_time: Start timestamp (optional)
            end_time: End timestamp (optional)
            limit: Maximum number of candles to return (most recent)

        Returns:
            List of candle dicts
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Build query
            query = '''
                SELECT timestamp, open, high, low, close, volume
                FROM price_history
                WHERE symbol = ? AND timeframe = ?
            '''
            params = [symbol, timeframe]

            if start_time:
                query += ' AND timestamp >= ?'
                params.append(start_time)

            if end_time:
                query += ' AND timestamp <= ?'
                params.append(end_time)

            query += ' ORDER BY timestamp DESC'

            if limit:
                query += ' LIMIT ?'
                params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
        finally:
            conn.close()

        # Convert to candle dicts (reverse to chronological order)
        candles = []
        for row in reversed(rows):
            candles.append({
                'timestamp': row[0],
                'open': row[1],
                'high': row[2],
                'low': row[3],
                'close': row[4],
                'volume': row[5]
            })

        return candles

    def get_latest_timestamp(self, symbol: str, timeframe: str) -> Optional[int]:
        """Get timestamp of most recent candle"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT MAX(timestamp) FROM price_history
                WHERE symbol = ? AND timeframe = ?
            ''', (symbol, timeframe))

            result = cursor.fetchone()
        finally:
            conn.close()

        return result[0] if result and result[0] else None

    def get_data_range(self, symbol: str, timeframe: str) -> Dict:
        """
        Get information about available data range

        Returns:
            Dict with first_timestamp, last_timestamp, count
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT MIN(timestamp), MAX(timestamp), COUNT(*)
                FROM price_history
                WHERE symbol = ? AND timeframe = ?
            ''', (symbol, timeframe))

            result = cursor.fetchone()
        finally:
            conn.close()

        if result and result[2] > 0:
            return {
                'first_timestamp': result[0],
                'last_timestamp': result[1],
                'count': result[2],
                'first_date': datetime.fromtimestamp(result[0]).isoformat(),
                'last_date': datetime.fromtimestamp(result[1]).isoformat()
            }

        return {'count': 0}

    def get_recent_closes(self, symbol: str, timeframe: str, count: int) -> List[float]:
        """
        Get recent closing prices (most efficient for indicator calculations)

        Args:
            symbol: Coin symbol
            timeframe: Timeframe
            count: Number of recent closes to return

        Returns:
            List of closing prices (chronological order)
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT close FROM price_history
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (symbol, timeframe, count))

            rows = cursor.fetchall()
        finally:
            conn.close()

        # Reverse to chronological order
        return [row[0] for row in reversed(rows)]

    def clear_old_data(self, days_to_keep: int = 180):
        """
        Clear data older than specified days

        Args:
            days_to_keep: Number of days to keep (default 180 = 6 months)
        """
        cutoff_time = int((datetime.now() - timedelta(days=days_to_keep)).timestamp())

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute('''
                DELETE FROM price_history WHERE timestamp < ?
            ''', (cutoff_time,))

            deleted = cursor.rowcount
            conn.commit()
        finally:
            conn.close()

        logger.info(f"Cleared {deleted} old candles (older than {days_to_keep} days)")

    def get_statistics(self) -> Dict:
        """Get database statistics"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Total candles by symbol and timeframe
            cursor.execute('''
                SELECT symbol, timeframe, COUNT(*), MIN(timestamp), MAX(timestamp)
                FROM price_history
                GROUP BY symbol, timeframe
            ''')

            rows = cursor.fetchall()
        finally:
            conn.close()

        stats = {}
        for row in rows:
            symbol, timeframe, count, first_ts, last_ts = row
            key = f"{symbol}_{timeframe}"
            stats[key] = {
                'symbol': symbol,
                'timeframe': timeframe,
                'count': count,
                'first_date': datetime.fromtimestamp(first_ts).strftime('%Y-%m-%d'),
                'last_date': datetime.fromtimestamp(last_ts).strftime('%Y-%m-%d')
            }

        return stats
