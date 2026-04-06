"""
Real-time Price Feed using WebSockets
Provides fast, real-time price updates without polling
"""

import json
import time
import logging
import threading
from typing import Dict, Optional
import websocket

logger = logging.getLogger("PriceFeed")

# Canonical symbol map — imported by arbitrage detectors instead of duplicating
BINANCE_SYMBOL_MAP = {
    'BTC': 'btcusdt',
    'ETH': 'ethusdt',
    'SOL': 'solusdt',
}


class RealtimePriceFeed:
    """
    WebSocket-based price feed for BTC, ETH, SOL

    Connects to Binance WebSocket for real-time prices
    Maintains in-memory cache with automatic updates
    """

    def __init__(self):
        """Initialize price feed with WebSocket connections"""
        self.prices = {
            'BTC': None,
            'ETH': None,
            'SOL': None
        }

        self.last_update = {
            'BTC': 0,
            'ETH': 0,
            'SOL': 0
        }

        # Binance WebSocket streams
        self.symbol_map = BINANCE_SYMBOL_MAP

        self.ws_threads = {}
        self.ws_connections = {}
        self.running = False

        logger.info("Real-time Price Feed initialized (WebSocket)")

    def start(self):
        """Start WebSocket connections for all coins"""
        if self.running:
            return

        self.running = True

        # Start WebSocket thread for each coin
        for coin in ['BTC', 'ETH', 'SOL']:
            thread = threading.Thread(target=self._run_websocket, args=(coin,), daemon=True)
            thread.start()
            self.ws_threads[coin] = thread

        logger.info("WebSocket price feeds started")

        # Wait for initial prices
        time.sleep(2)

    def stop(self):
        """Stop all WebSocket connections gracefully"""
        logger.info("Stopping WebSocket price feeds...")
        self.running = False

        # Close all WebSocket connections
        for coin, ws in self.ws_connections.items():
            try:
                ws.close()
            except Exception as e:
                logger.warning(f"Error closing {coin} WebSocket: {e}")

        # Give threads a moment to exit gracefully
        time.sleep(0.5)

        # Clear connections dict
        self.ws_connections.clear()

        logger.info("WebSocket price feeds stopped")

    def _run_websocket(self, coin: str):
        """Run WebSocket connection for a specific coin"""
        symbol = self.symbol_map[coin].lower()
        url = f"wss://stream.binance.com:9443/ws/{symbol}@trade"

        def on_message(ws, message):
            """Handle incoming price updates"""
            try:
                data = json.loads(message)
                price = float(data['p'])
                self.prices[coin] = price
                self.last_update[coin] = time.time()
            except Exception as e:
                pass  # Silent fail

        def on_error(ws, error):
            """Handle WebSocket errors"""
            pass  # Silent fail, will reconnect

        def on_close(ws, close_status_code, close_msg):
            """Handle WebSocket close"""
            # Reconnect if still running
            if self.running:
                time.sleep(1)
                self._run_websocket(coin)

        def on_open(ws):
            """Handle WebSocket open"""
            pass

        # Create WebSocket connection
        ws = websocket.WebSocketApp(
            url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )

        self.ws_connections[coin] = ws

        # Run WebSocket (blocking)
        ws.run_forever()

    def get_price(self, coin: str) -> Optional[float]:
        """
        Get current price for a coin

        Args:
            coin: Coin symbol (BTC, ETH, SOL)

        Returns:
            Current price or None if not available
        """
        price = self.prices.get(coin)

        # Check if price is stale (>30 seconds old)
        if price is not None:
            age = time.time() - self.last_update[coin]
            if age > 30:
                return None  # Stale price, fall back to API

        return price

    def is_connected(self, coin: str) -> bool:
        """Check if WebSocket is connected and receiving updates"""
        if coin not in self.last_update:
            return False

        age = time.time() - self.last_update[coin]
        return age < 5  # Connected if updated within 5 seconds

    def get_price_with_timestamp(self, coin: str) -> Optional[Dict]:
        """
        Get current price with timestamp for arbitrage detectors.

        Returns:
            {'price': float, 'timestamp': float} or None if unavailable/stale
        """
        price = self.prices.get(coin)
        if price is None:
            return None

        ts = self.last_update.get(coin, 0)
        age = time.time() - ts
        if age > 30:
            return None  # Stale

        return {'price': price, 'timestamp': ts}

    def get_all_prices(self) -> Dict[str, float]:
        """Get all current prices"""
        return {
            coin: self.get_price(coin)
            for coin in ['BTC', 'ETH', 'SOL']
        }
