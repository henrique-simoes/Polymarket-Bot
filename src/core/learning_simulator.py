"""
Learning Mode Simulator - Paper Trading for ML Training
Simulates entire trading pipeline without placing real orders
Tracks virtual balance and P&L for risk-free data collection
"""

import logging
from datetime import datetime
from typing import Dict, Optional
import random

logger = logging.getLogger("LearningSimulator")


class LearningSimulator:
    """
    Simulates order placement and settlement for learning mode

    Features:
    - Virtual balance tracking
    - Simulated order placement (no real API calls)
    - Realistic settlement based on actual market outcomes
    - Identical data format to real trades for ML training
    """

    def __init__(self, initial_balance: float = 10.0):
        """
        Initialize learning simulator

        Args:
            initial_balance: Starting virtual balance in USDC
        """
        self.initial_balance = initial_balance
        self.virtual_balance = initial_balance
        self.virtual_positions = {}  # position_id -> position_data
        self.position_counter = 0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0

        logger.info(f"Learning Simulator initialized with ${initial_balance:.2f} virtual balance")

    def can_afford(self, amount: float) -> bool:
        """Check if virtual balance can afford bet"""
        return self.virtual_balance >= amount

    def simulate_order(self, coin: str, direction: str, amount: float,
                      token_id: str, start_price: float, current_price: float,
                      confidence: float, condition_id: str = None) -> Optional[Dict]:
        """
        Simulate order placement without calling real API

        Args:
            coin: Coin symbol (BTC, ETH, SOL)
            direction: UP or DOWN
            amount: Bet amount in USDC
            token_id: Token ID for YES or NO
            start_price: Strike price at market start
            current_price: Current market price
            confidence: ML confidence (0-1)
            condition_id: Market condition ID for resolution checking

        Returns:
            Simulated order dict or None if cannot afford
        """
        if not self.can_afford(amount):
            logger.warning(f"Insufficient virtual balance: ${self.virtual_balance:.2f} < ${amount:.2f}")
            return None

        # Deduct from virtual balance
        self.virtual_balance -= amount

        # Create simulated order
        self.position_counter += 1
        order_id = f"LEARNING_{self.position_counter}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Estimate shares based on current market price (simplified)
        # In reality, price varies, but for learning we use current price as entry
        estimated_price = random.uniform(0.45, 0.55)  # Realistic entry price range
        estimated_shares = amount / estimated_price

        position = {
            'order_id': order_id,
            'coin': coin,
            'prediction': direction,  # Standardized field name (was 'direction')
            'amount': amount,
            'cost': amount,  # Duplicate for compatibility with real mode
            'token_id': token_id,
            'condition_id': condition_id,
            'start_price': start_price,
            'current_price': current_price,
            'confidence': confidence,
            'price': estimated_price,  # Standardized field name (was 'entry_price')
            'shares': estimated_shares,
            'timestamp': datetime.now().isoformat(),
            'status': 'simulated_open'
        }

        self.virtual_positions[order_id] = position

        logger.info(f"SIMULATED: {coin} {direction} ${amount:.2f} @ {estimated_price:.3f} (ID: {order_id[:24]}...)")

        return position

    def settle_position(self, order_id: str, final_price: float, start_price: float,
                        official_outcome: str = None) -> Dict:
        """
        Settle simulated position based on actual market outcome

        Args:
            order_id: Position ID
            final_price: Final price at market close
            start_price: Strike price at market start
            official_outcome: Official CLOB resolution ("UP" or "DOWN") - REQUIRED for accurate settlement

        Returns:
            Trade record with outcome and P&L
        """
        if order_id not in self.virtual_positions:
            logger.error(f"Position not found: {order_id}")
            return {}

        position = self.virtual_positions[order_id]

        # Use official CLOB outcome if provided, otherwise fall back to price comparison (NOT recommended)
        if official_outcome:
            actual_outcome = official_outcome
            logger.info(f"Using OFFICIAL CLOB outcome: {actual_outcome}")
        else:
            # FALLBACK: Price comparison (deprecated, may give wrong results)
            actual_outcome = "UP" if final_price > start_price else "DOWN"
            logger.warning(f"Using PRICE COMPARISON outcome (not recommended): {actual_outcome}")

        won = (position['prediction'] == actual_outcome)  # Updated to use 'prediction'

        # Calculate P&L
        if won:
            # Win: Get shares back as $1 each
            pnl = position['shares'] - position['amount']
            self.virtual_balance += position['shares']
            self.wins += 1
        else:
            # Loss: Lose bet amount (already deducted)
            pnl = -position['amount']
            self.losses += 1

        self.total_trades += 1

        # Create trade record (identical format to real trades)
        trade_record = {
            **position,
            'status': 'settled',
            'final_price': final_price,
            'actual_outcome': actual_outcome,
            'won': won,
            'profit': pnl,  # Standardized field name (was 'pnl')
            'settled_at': datetime.now().isoformat(),
            'mode': 'learning',
            'virtual_balance_after': self.virtual_balance
        }

        # Remove from active positions
        del self.virtual_positions[order_id]

        result = "WON" if won else "LOST"
        logger.info(f"SETTLED: {position['coin']} {result} ${pnl:+.2f} | Virtual Balance: ${self.virtual_balance:.2f}")

        return trade_record

    def get_virtual_balance(self) -> float:
        """Get current virtual balance"""
        return self.virtual_balance

    def get_stats(self) -> Dict:
        """Get learning mode statistics"""
        win_rate = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0.0
        total_pnl = self.virtual_balance - self.initial_balance
        roi = (total_pnl / self.initial_balance * 100) if self.initial_balance > 0 else 0.0

        return {
            'virtual_balance': self.virtual_balance,
            'initial_balance': self.initial_balance,
            'total_pnl': total_pnl,
            'roi': roi,
            'total_trades': self.total_trades,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': win_rate,
            'active_positions': len(self.virtual_positions)
        }

    def cancel_position(self, order_id: str, reason: str = "unresolved") -> bool:
        """
        Cancel/remove a position without settling (for unresolved markets)
        Refunds the bet amount back to virtual balance

        Args:
            order_id: Position ID to cancel
            reason: Reason for cancellation

        Returns:
            True if position was cancelled, False if not found
        """
        if order_id not in self.virtual_positions:
            logger.warning(f"Cannot cancel - position not found: {order_id}")
            return False

        position = self.virtual_positions[order_id]
        amount = position.get('amount', 0)

        # Refund the bet amount
        self.virtual_balance += amount

        # Remove from active positions
        del self.virtual_positions[order_id]

        logger.warning(f"CANCELLED: {position['coin']} ${amount:.2f} ({reason}) | Refunded to virtual balance: ${self.virtual_balance:.2f}")

        return True

    def reset(self, new_balance: Optional[float] = None):
        """Reset simulator to initial state"""
        if new_balance is not None:
            self.initial_balance = new_balance

        self.virtual_balance = self.initial_balance
        self.virtual_positions = {}
        self.total_trades = 0
        self.wins = 0
        self.losses = 0

        logger.info(f"Learning Simulator reset to ${self.initial_balance:.2f}")
