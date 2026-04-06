"""
Profit-Taking Engine - Orchestrates position monitoring and exit decisions
Evaluates positions every 5 seconds and executes early exits when profitable
"""

import logging
import time
from typing import Dict, Optional
from threading import Thread

logger = logging.getLogger("ProfitTakingEngine")


class ProfitTakingEngine:
    """
    Manages profit-taking decisions for all open positions

    Features:
    - Monitor positions every 5 seconds
    - Evaluate exit signals from Exit Timing Learner
    - Execute market sell orders for early exits
    - Learn from outcomes (early exit vs hold to expiry)
    """

    def __init__(self, position_tracker, exit_timing_learner, market_15m):
        """
        Initialize profit-taking engine

        Args:
            position_tracker: PositionTracker instance
            exit_timing_learner: ExitTimingLearner instance
            market_15m: Market15M instance for executing sells
        """
        self.position_tracker = position_tracker
        self.exit_learner = exit_timing_learner
        self.market_15m = market_15m

        self.running = False
        self.check_interval = 5  # Check every 5 seconds
        self.positions_exited = []  # Track early exits

        logger.info("Profit-Taking Engine initialized")

    def start(self):
        """Start background monitoring thread"""
        if self.running:
            logger.warning("Profit-taking engine already running")
            return

        self.running = True
        Thread(target=self._monitoring_loop, daemon=True).start()
        logger.info("Profit-taking engine started")

    def stop(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Profit-taking engine stopped")

    def _monitoring_loop(self):
        """Background loop that monitors positions"""
        while self.running:
            try:
                self.evaluate_all_positions()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.check_interval)

    def evaluate_all_positions(self):
        """Evaluate all active positions for exit signals"""
        current_time = time.time()

        # Update all positions with current prices/P&L
        self.position_tracker.update_positions(current_time)

        # Get active positions
        positions = self.position_tracker.get_active_positions()

        if not positions:
            return

        for position in positions:
            self._evaluate_position(position, current_time)

    def _evaluate_position(self, position: Dict, current_time: float):
        """
        Evaluate single position for exit

        Args:
            position: Position dict
            current_time: Current timestamp
        """
        try:
            position_id = position['position_id']
            coin = position['coin']
            direction = position['direction']

            # Check if enough time has passed since entry (don't exit immediately)
            entry_time = position.get('entry_time', 0)
            if current_time - entry_time < 60:  # Wait at least 1 minute
                return

            # Get exit signal from ML model
            exit_signal = self.exit_learner.should_exit(position, current_time)

            if exit_signal['decision'] == 'exit':
                logger.info(f"EXIT SIGNAL: {coin} {direction} | {exit_signal['reason']}")

                # Execute early exit
                success = self._execute_early_exit(position, exit_signal)

                if success:
                    self.positions_exited.append({
                        'position_id': position_id,
                        'coin': coin,
                        'direction': direction,
                        'exit_time': current_time,
                        'reason': exit_signal['reason'],
                        'confidence': exit_signal['confidence']
                    })

        except Exception as e:
            logger.error(f"Failed to evaluate position: {e}")

    def _execute_early_exit(self, position: Dict, exit_signal: Dict) -> bool:
        """
        Execute market sell order to exit position early

        Args:
            position: Position dict
            exit_signal: Exit signal from learner

        Returns:
            True if exit successful
        """
        try:
            coin = position['coin']
            token_id = position['token_id']
            shares = position.get('shares', 0)

            logger.info(f"Executing early exit: {coin} | {shares:.2f} shares")

            # Use py-clob-client to create market sell order
            # Reference: examples/market_sell_order.py
            from py_clob_client.order_builder.constants import SELL

            sell_order = self.market_15m.client.create_market_order({
                'token_id': token_id,
                'amount': shares,
                'side': SELL
            })

            # Post order (FOK - Fill or Kill for immediate execution)
            from py_clob_client.constants import OrderType
            response = self.market_15m.client.post_order(sell_order, OrderType.FOK)

            if response and response.get('status') != 'error':
                logger.info(f"Early exit successful: {coin} | Sold {shares:.2f} shares")

                # Get exit price
                exit_price = position.get('current_token_price', 0)

                # Close position in tracker
                self.position_tracker.close_position(
                    position['position_id'],
                    exit_price,
                    exit_type='early_exit'
                )

                return True
            else:
                logger.error(f"Early exit failed: {response}")
                return False

        except Exception as e:
            logger.error(f"Failed to execute early exit: {e}")
            return False

    def learn_from_position(self, completed_position: Dict):
        """
        Learn from completed position (called after market settlement)

        Args:
            completed_position: Completed position dict from position_tracker
        """
        try:
            # Generate training samples from this trade
            self.exit_learner.learn_from_completed_trade(completed_position)

            # Train model if enough samples collected
            if len(self.exit_learner.training_samples) >= 50:
                self.exit_learner.train()

            logger.debug(f"Learned from position: {completed_position['coin']}")

        except Exception as e:
            logger.error(f"Failed to learn from position: {e}")

    def get_statistics(self) -> Dict:
        """Get profit-taking statistics"""
        total_exits = len(self.positions_exited)

        return {
            'total_early_exits': total_exits,
            'exit_learner_stats': self.exit_learner.get_statistics(),
            'running': self.running
        }

    def get_recent_exits(self, limit: int = 10) -> list:
        """Get recent early exits"""
        return self.positions_exited[-limit:]
