"""
Polymarket WebSocket Manager
Handles real-time updates for Market Resolution and User Positions
"""

import asyncio
import json
import logging
import websockets
import time
from threading import Thread, Lock
from typing import Dict, List, Callable, Optional

logger = logging.getLogger("PolymarketWS")

class PolymarketWebSocket:
    def __init__(self, ws_url: str = "wss://ws-subscriptions-clob.polymarket.com", 
                 api_key: str = None, api_secret: str = None, api_passphrase: str = None):
        self.ws_url = ws_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        
        self.running = False
        self.ws = None
        self.thread = None
        self.loop = None
        
        # Callbacks
        self.on_market_update = []
        self.on_order_update = []
        
        # State
        self.subscribed_markets = set()
        
    def start(self):
        """Start the WebSocket client in a background thread"""
        if self.running: return
        self.running = True
        self.thread = Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
            
    def subscribe_markets(self, asset_ids: List[str]):
        """Subscribe to market updates for specific assets (token IDs)"""
        if not self.ws or not self.running: 
            # Queue for later
            self.subscribed_markets.update(asset_ids)
            return

        # Polymarket expects string "asset_id"
        # Channel: "market"
        msg = {
            "type": "subscribe",
            "channel": "market",
            "assets_ids": asset_ids
        }
        asyncio.run_coroutine_threadsafe(self.ws.send(json.dumps(msg)), self.loop)
        self.subscribed_markets.update(asset_ids)
        logger.info(f"Subscribed to {len(asset_ids)} markets")

    def _run_event_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect())
        
    async def _connect(self):
        while self.running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    self.ws = ws
                    logger.info("Connected to Polymarket WebSocket")
                    
                    # Re-subscribe to pending
                    if self.subscribed_markets:
                        await self.subscribe_markets_async(list(self.subscribed_markets))
                    
                    # Auth if credentials provided (for user channel)
                    if self.api_key:
                        await self._authenticate()

                    while self.running:
                        msg = await ws.recv()
                        await self._handle_message(msg)
                        
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5) # Reconnect delay

    async def subscribe_markets_async(self, asset_ids: List[str]):
        msg = {
            "type": "subscribe",
            "channel": "market",
            "assets_ids": asset_ids
        }
        await self.ws.send(json.dumps(msg))

    async def _authenticate(self):
        # TODO: Implement CLOB auth signature generation
        # For now, we focus on public market data
        pass

    async def _handle_message(self, message: str):
        try:
            data = json.loads(message)
            
            # Market Update (Resolution)
            if isinstance(data, list):
                for item in data:
                    if item.get('event_type') == "market":
                        self._process_market_update(item)
            
        except Exception as e:
            logger.error(f"Message processing error: {e}")

    def _process_market_update(self, data: dict):
        # Check for UMA resolution
        # Usually data contains 'uma_resolution_status' or similar
        # Polymarket WS structure varies, need to be robust
        for callback in self.on_market_update:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def add_market_callback(self, callback: Callable):
        self.on_market_update.append(callback)
