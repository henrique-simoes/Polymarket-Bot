"""
Position Tracker - Tracks open positions with real-time P&L
Monitors all open positions for profit-taking decisions
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
import time

logger = logging.getLogger("PositionTracker")


class PositionTracker:
    """
    Tracks all open positions with real-time P&L monitoring

    Features:
    - Real-time position tracking
    - P&L calculation (current value vs entry cost)
    - Time tracking (entry time, time remaining)
    - Position history for learning
    """

    def __init__(self, market_15m, price_feed):
        """
        Initialize position tracker

        Args:
            market_15m: Market15M instance for price lookups
            price_feed: RealtimePriceFeed for current prices
        """
        self.market_15m = market_15m
        self.price_feed = price_feed
        self.active_positions = {}  # position_id -> position_data
        self.position_history = []  # Completed positions

        logger.info("Position Tracker initialized")

    def add_position(self, position_data: Dict) -> str:
        """
        Add new position for tracking

        Args:
            position_data: Dict with coin, direction, token_id, shares, entry_price, entry_time, expiry_time, start_price

        Returns:
            Position ID
        """
        position_id = f"{position_data['coin']}_{position_data['direction']}_{int(time.time())}"

        self.active_positions[position_id] = {
            **position_data,
            'position_id': position_id,
            'added_at': datetime.now().isoformat(),
            'price_history': [],  # Track price over time for learning
            'pnl_history': []  # Track P&L over time
        }

        logger.info(f"Added position: {position_id} | {position_data['coin']} {position_data['direction']} "
                   f"${position_data.get('amount', 0):.2f}")

        return position_id

    def update_positions(self, current_time: float = None):
        """
        Update all active positions with current prices and P&L

        Args:
            current_time: Current timestamp (for testing), uses time.time() if None
        """
        if current_time is None:
            current_time = time.time()

        for position_id, position in list(self.active_positions.items()):
            try:
                # Get current token price
                current_token_price = self._get_token_price(position['token_id'])

                if current_token_price is None:
                    continue

                # Calculate current value
                shares = position.get('shares', 0)
                entry_price = position.get('entry_price', 0)
                amount_spent = position.get('amount', shares * entry_price)

                current_value = shares * current_token_price
                unrealized_pnl = current_value - amount_spent
                pnl_pct = (unrealized_pnl / amount_spent * 100) if amount_spent > 0 else 0

                # Update position
                position['current_token_price'] = current_token_price
                position['current_value'] = current_value
                position['unrealized_pnl'] = unrealized_pnl
                position['pnl_pct'] = pnl_pct
                position['last_updated'] = datetime.now().isoformat()

                # Track price and P&L history
                position['price_history'].append({
                    'timestamp': current_time,
                    'price': current_token_price
                })
                position['pnl_history'].append({
                    'timestamp': current_time,
                    'pnl': unrealized_pnl,
                    'pnl_pct': pnl_pct
                })

                # Calculate time remaining
                expiry_time = position.get('expiry_time')
                if expiry_time:
                    time_remaining = max(0, expiry_time - current_time)
                    position['time_remaining'] = time_remaining

            except Exception as e:
                logger.error(f"Failed to update position {position_id}: {e}")

    def get_active_positions(self) -> List[Dict]:
        """Get all active positions"""
        return list(self.active_positions.values())

    def get_position(self, position_id: str) -> Optional[Dict]:
        """Get specific position by ID"""
        return self.active_positions.get(position_id)

    def close_position(self, position_id: str, exit_price: float,
                      exit_type: str = 'expiry') -> Optional[Dict]:
        """
        Close position and move to history

        Args:
            position_id: Position ID
            exit_price: Final exit price
            exit_type: 'expiry' (held to end) or 'early_exit' (sold early)

        Returns:
            Completed position dict
        """
        if position_id not in self.active_positions:
            logger.error(f"Position not found: {position_id}")
            return None

        position = self.active_positions[position_id]

        # Calculate final P&L
        shares = position.get('shares', 0)
        amount_spent = position.get('amount', 0)
        final_value = shares * exit_price
        realized_pnl = final_value - amount_spent

        # Complete position record
        completed_position = {
            **position,
            'exit_price': exit_price,
            'exit_type': exit_type,
            'final_value': final_value,
            'realized_pnl': realized_pnl,
            'closed_at': datetime.now().isoformat()
        }

        # Move to history
        self.position_history.append(completed_position)

        # Remove from active
        del self.active_positions[position_id]

        logger.info(f"Closed position: {position_id} | {exit_type} | P&L: ${realized_pnl:+.2f}")

        return completed_position

    def get_position_summary(self) -> Dict:
        """Get summary of all active positions"""
        if not self.active_positions:
            return {
                'total_positions': 0,
                'total_pnl': 0.0,
                'best_position': None,
                'worst_position': None
            }

        positions = list(self.active_positions.values())
        total_pnl = sum(p.get('unrealized_pnl', 0) for p in positions)

        # Find best and worst
        best = max(positions, key=lambda p: p.get('unrealized_pnl', 0))
        worst = min(positions, key=lambda p: p.get('unrealized_pnl', 0))

        return {
            'total_positions': len(positions),
            'total_pnl': total_pnl,
            'best_position': {
                'coin': best['coin'],
                'pnl': best.get('unrealized_pnl', 0),
                'pnl_pct': best.get('pnl_pct', 0)
            },
            'worst_position': {
                'coin': worst['coin'],
                'pnl': worst.get('unrealized_pnl', 0),
                'pnl_pct': worst.get('pnl_pct', 0)
            }
        }

    def _get_token_price(self, token_id: str) -> Optional[float]:
        """Get current price for token"""
        try:
            price = self.market_15m.client.get_midpoint_price(token_id)
            return price if price else None
        except Exception as e:
            logger.debug(f"Failed to get token price for {token_id}: {e}")
            return None

    def get_position_history(self, limit: int = 50) -> List[Dict]:
        """Get completed position history"""
        return self.position_history[-limit:]

    def clear_position_history(self):
        """Clear position history (for testing)"""
        self.position_history = []
        logger.info("Position history cleared")
