"""
Exchange Data Manager - CCXT Integration
Fetches OHLCV and Order Book depth from Binance for advanced ML signals.
"""

import ccxt
import pandas as pd
import numpy as np
import time
import logging
from threading import Thread, Lock
from datetime import datetime, timezone

logger = logging.getLogger("ExchangeData")

class ExchangeDataManager:
    def __init__(self, exchange_id='binance'):
        self.exchange_id = exchange_id
        self.exchange = getattr(ccxt, exchange_id)({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'} # Use futures for more volume/signal? or spot. Spot is safer ref.
        })
        # Switch to spot for Polymarket correlation (usually tracks spot)
        self.exchange = getattr(ccxt, exchange_id)({'enableRateLimit': True})
        
        self.symbols = {
            'BTC': 'BTC/USDT',
            'ETH': 'ETH/USDT',
            'SOL': 'SOL/USDT'
        }
        
        # Data Store
        self.data_lock = Lock()
        self.latest_data = {
            'BTC': {'ohlcv': None, 'depth': None},
            'ETH': {'ohlcv': None, 'depth': None},
            'SOL': {'ohlcv': None, 'depth': None}
        }
        self.running = False

    def start(self):
        """Start background data fetching"""
        self.running = True
        Thread(target=self._update_loop, daemon=True).start()
        logger.info(f"Started Exchange Data Manager ({self.exchange_id})")

    def stop(self):
        self.running = False

    def _update_loop(self):
        while self.running:
            for coin, symbol in self.symbols.items():
                try:
                    # 1. Fetch OHLCV (1m candles, last 5)
                    ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe='1m', limit=5)
                    
                    # 2. Fetch Order Book (Depth)
                    # Limit 20 is enough for immediate pressure
                    depth = self.exchange.fetch_order_book(symbol, limit=20)
                    
                    with self.data_lock:
                        self.latest_data[coin]['ohlcv'] = ohlcv
                        self.latest_data[coin]['depth'] = depth
                        
                except Exception as e:
                    logger.debug(f"Fetch error for {coin}: {e}")
                    
            time.sleep(2) # Poll every 2s

    def get_features(self, coin: str) -> dict:
        """
        Return derived features for ML:
        - binance_rsi_1m
        - binance_book_imbalance
        - binance_spread_pct
        """
        with self.data_lock:
            data = self.latest_data.get(coin)
            
        if not data or not data['ohlcv'] or not data['depth']:
            return {
                'bin_rsi': 0.5,
                'bin_imbalance': 0.0,
                'bin_spread': 0.0
            }

        # 1. Calculate RSI from OHLCV
        try:
            closes = [x[4] for x in data['ohlcv']]
            # Simple RSI approximation for last 5 candles if TA-Lib overhead unwanted here
            # Or just return trend
            trend = (closes[-1] - closes[0]) / closes[0]
        except: trend = 0

        # 2. Calculate Order Book Imbalance
        # Imbalance = (Bids - Asks) / (Bids + Asks)
        try:
            bids = data['depth']['bids']
            asks = data['depth']['asks']
            
            bid_vol = sum([x[1] for x in bids])
            ask_vol = sum([x[1] for x in asks])
            
            if bid_vol + ask_vol > 0:
                imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)
            else:
                imbalance = 0.0
                
            # Spread
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            spread = (best_ask - best_bid) / best_bid
            
        except:
            imbalance = 0.0
            spread = 0.0

        return {
            'bin_trend_5m': trend,
            'bin_imbalance': imbalance,
            'bin_spread': spread
        }

    def fetch_historical_ohlcv(self, coin: str, timeframe: str, limit: int = 500) -> list:
        """
        Fetch historical OHLCV data from exchange

        Args:
            coin: Coin symbol (BTC, ETH, SOL)
            timeframe: Timeframe (1h, 4h, 1d, 1w)
            limit: Number of candles to fetch

        Returns:
            List of OHLCV candles [timestamp, open, high, low, close, volume]
        """
        try:
            symbol = self.symbols.get(coin)
            if not symbol:
                logger.error(f"Unknown coin: {coin}")
                return []

            logger.info(f"Fetching {limit} {timeframe} candles for {coin}...")
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

            logger.info(f"Fetched {len(ohlcv)} {timeframe} candles for {coin}")
            return ohlcv

        except Exception as e:
            logger.error(f"Failed to fetch historical data for {coin} {timeframe}: {e}")
            return []

    def fetch_historical_range(self, coin: str, timeframe: str,
                              since_timestamp: int, limit: int = 1000) -> list:
        """
        Fetch historical data starting from specific timestamp

        Args:
            coin: Coin symbol
            timeframe: Timeframe
            since_timestamp: Start timestamp in milliseconds
            limit: Max candles per request (exchange limit usually 1000)

        Returns:
            List of OHLCV candles
        """
        try:
            symbol = self.symbols.get(coin)
            if not symbol:
                return []

            ohlcv = self.exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                since=since_timestamp,
                limit=limit
            )

            return ohlcv

        except Exception as e:
            logger.error(f"Failed to fetch historical range for {coin}: {e}")
            return []

    def backfill_historical_data(self, coin: str, timeframe: str,
                                days_back: int = 180) -> list:
        """
        Backfill multiple months of historical data (handles pagination)

        Args:
            coin: Coin symbol
            timeframe: Timeframe
            days_back: Number of days to fetch (default 180 = 6 months)

        Returns:
            Complete list of OHLCV candles
        """
        try:
            from datetime import timedelta

            # Calculate start timestamp
            start_date = datetime.now() - timedelta(days=days_back)
            since_ms = int(start_date.timestamp() * 1000)

            all_candles = []
            current_since = since_ms

            logger.info(f"Backfilling {days_back} days of {timeframe} data for {coin}...")

            while True:
                batch = self.fetch_historical_range(coin, timeframe, current_since, limit=1000)

                if not batch:
                    break

                all_candles.extend(batch)

                # Move to next batch (last candle timestamp + 1ms)
                current_since = batch[-1][0] + 1

                # Stop if we've reached current time
                if current_since >= int(datetime.now().timestamp() * 1000):
                    break

                # Rate limiting
                time.sleep(self.exchange.rateLimit / 1000)

                logger.info(f"  Fetched {len(all_candles)} {timeframe} candles so far...")

            logger.info(f"Backfill complete: {len(all_candles)} {timeframe} candles for {coin}")
            return all_candles

        except Exception as e:
            logger.error(f"Backfill failed for {coin} {timeframe}: {e}")
            return []

    def update_latest_candles(self, coin: str, timeframe: str, historical_manager) -> int:
        """
        Fetch latest candles and store to historical database
        Used for continuous updates to keep database current

        Args:
            coin: Coin symbol (BTC, ETH, SOL)
            timeframe: Timeframe (1h, 4h, 1d, 1w)
            historical_manager: HistoricalDataManager instance to store candles

        Returns:
            Number of new candles stored
        """
        try:
            # Fetch last 100 candles to ensure we don't miss any
            candles = self.fetch_historical_ohlcv(coin, timeframe, limit=100)

            if not candles:
                logger.debug(f"No new candles to update for {coin} {timeframe}")
                return 0

            # Convert to dict format expected by historical_manager
            candle_dicts = []
            for candle in candles:
                candle_dicts.append({
                    'timestamp': candle[0] // 1000,  # Convert ms to seconds
                    'open': candle[1],
                    'high': candle[2],
                    'low': candle[3],
                    'close': candle[4],
                    'volume': candle[5]
                })

            # Store to database (INSERT OR REPLACE handles duplicates)
            stored = historical_manager.store_candles(coin, timeframe, candle_dicts)

            if stored > 0:
                logger.debug(f"Updated {stored} {timeframe} candles for {coin}")

            return stored

        except Exception as e:
            logger.error(f"Failed to update latest candles for {coin} {timeframe}: {e}")
            return 0
