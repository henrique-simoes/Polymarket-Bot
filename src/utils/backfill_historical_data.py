"""
Historical Data Backfill Utility
Populates SQLite database with 6 months of historical price data
Run this once to initialize the historical database
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import logging
from src.core.historical_data import HistoricalDataManager
from src.core.exchange_data import ExchangeDataManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("Backfill")


def backfill_all_data():
    """Backfill historical data for all coins and timeframes"""

    print("=" * 70)
    print("HISTORICAL DATA BACKFILL UTILITY")
    print("=" * 70)
    print("\nThis will fetch 6 months of historical data from Binance")
    print("and store it in the SQLite database for correlation analysis.")
    print("\nCoins: BTC, ETH, SOL")
    print("Timeframes: 1h, 4h, 1d, 1w")
    print("\nThis may take 5-10 minutes due to exchange rate limits.")
    print("\n" + "=" * 70)

    response = input("\nContinue? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Backfill cancelled.")
        return

    # Initialize managers
    historical = HistoricalDataManager()
    exchange = ExchangeDataManager()

    coins = ['BTC', 'ETH', 'SOL']
    timeframes = ['1h', '4h', '1d', '1w']
    days_back = 180  # 6 months

    print("\n" + "=" * 70)
    print("STARTING BACKFILL")
    print("=" * 70)

    total_candles = 0

    for coin in coins:
        for timeframe in timeframes:
            print(f"\n[{coin} {timeframe}] Fetching data...")

            # Check existing data
            existing_range = historical.get_data_range(coin, timeframe)
            if existing_range.get('count', 0) > 0:
                print(f"  Found existing data: {existing_range['count']} candles")
                print(f"  Range: {existing_range['first_date']} to {existing_range['last_date']}")

                response = input(f"  Overwrite? (yes/no): ").strip().lower()
                if response != 'yes':
                    print("  Skipping...")
                    continue

            # Fetch historical data
            candles = exchange.backfill_historical_data(coin, timeframe, days_back)

            if not candles:
                print(f"  [ERROR] No data fetched for {coin} {timeframe}")
                continue

            # Convert to database format
            db_candles = []
            for candle in candles:
                db_candles.append({
                    'timestamp': candle[0] / 1000,  # Convert ms to seconds
                    'open': candle[1],
                    'high': candle[2],
                    'low': candle[3],
                    'close': candle[4],
                    'volume': candle[5]
                })

            # Store to database
            stored = historical.store_candles(coin, timeframe, db_candles)
            total_candles += stored

            print(f"  [SUCCESS] Stored {stored} candles")

    print("\n" + "=" * 70)
    print("BACKFILL COMPLETE")
    print("=" * 70)
    print(f"\nTotal candles stored: {total_candles}")

    # Show database statistics
    print("\nDatabase Statistics:")
    stats = historical.get_statistics()
    for key, info in stats.items():
        print(f"  {info['symbol']} {info['timeframe']}: {info['count']} candles ({info['first_date']} to {info['last_date']})")

    print("\n" + "=" * 70)
    print("Historical database ready for correlation analysis!")
    print("=" * 70)


if __name__ == "__main__":
    backfill_all_data()
