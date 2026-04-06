"""
Trading Strategy - Orchestrates bet placement and money management
"""

import json
from decimal import Decimal
from pathlib import Path
from datetime import datetime

class TradingStrategy:
    """
    Money management and bet sizing strategy:
    - Profits saved immediately (100%)
    - Bet increases by X% of profit after win
    - Reset to default on ANY loss
    """

    def __init__(self, initial_bet_usdt: float, profit_increase_pct: float, max_bet_multiplier: float = 5.0):
        """
        Initialize trading strategy

        Args:
            initial_bet_usdt: Default bet size (returns here on loss)
            profit_increase_pct: % to increase BET after win (NOT % of profit!)
            max_bet_multiplier: Maximum bet = initial_bet * this value
        """
        self.initial_bet_usdt = Decimal(str(initial_bet_usdt))
        self.current_bet = Decimal(str(initial_bet_usdt))
        self.profit_increase_pct = Decimal(str(profit_increase_pct))
        self.max_bet_multiplier = Decimal(str(max_bet_multiplier))
        self.max_bet = self.initial_bet_usdt * self.max_bet_multiplier

        # P&L tracking
        self.saved_profits = Decimal('0')
        self.total_earned = Decimal('0')

        # Stats
        self.consecutive_wins = 0
        self.wins = 0
        self.losses = 0

        # Persistent state tracking
        self.state_file = Path("data/strategy_state.json")
        self.trade_log_file = Path("data/trade_log.jsonl")

        print(f"Trading Strategy initialized")
        print(f"   Initial bet: {self.initial_bet_usdt} USDT")
        print(f"   Profit increase: {self.profit_increase_pct}%")

        # Load persistent state if available
        self._load_state()

    def _load_state(self):
        """Load persistent state from disk"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)

                # Load state values
                self.wins = state.get('wins', 0)
                self.losses = state.get('losses', 0)
                self.consecutive_wins = state.get('consecutive_wins', 0)
                self.saved_profits = Decimal(str(state.get('saved_profits', '0')))
                self.total_earned = Decimal(str(state.get('total_earned', '0')))
                self.current_bet = Decimal(str(state.get('current_bet', str(self.initial_bet_usdt))))

                print(f"\n[LOADED STATE] Resuming from previous session:")
                print(f"   Wins: {self.wins}, Losses: {self.losses}")
                print(f"   Saved Profits: {float(self.saved_profits):.2f} USDC")
                print(f"   Total Earned: {float(self.total_earned):+.2f} USDC")
                print(f"   Current Bet: {float(self.current_bet):.2f} USDC")
            else:
                print(f"   No previous state found, starting fresh")
        except Exception as e:
            print(f"   [WARNING] Could not load state: {e}")
            print(f"   Starting with fresh state")

    def _save_state(self):
        """Save persistent state to disk"""
        try:
            # Create data directory if it doesn't exist
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Prepare state dictionary
            state = {
                'wins': self.wins,
                'losses': self.losses,
                'consecutive_wins': self.consecutive_wins,
                'saved_profits': str(self.saved_profits),
                'total_earned': str(self.total_earned),
                'current_bet': str(self.current_bet),
                'initial_bet': str(self.initial_bet_usdt),
                'last_updated': datetime.utcnow().isoformat()
            }

            # Write to file
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            print(f"   [WARNING] Could not save state: {e}")

    def _log_trade(self, trade_data: dict):
        """Append trade to log file (JSONL format)"""
        try:
            # Create data directory if it doesn't exist
            self.trade_log_file.parent.mkdir(parents=True, exist_ok=True)

            # Add timestamp
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                **trade_data
            }

            # Append to JSONL file (one JSON object per line)
            with open(self.trade_log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')

        except Exception as e:
            print(f"   [WARNING] Could not log trade: {e}")

    def process_win(self, profit: float) -> dict:
        """
        Process winning trade

        Args:
            profit: Profit amount in USDT

        Returns:
            Dict with updated state
        """
        profit_dec = Decimal(str(profit))

        # Save 100% of profit
        self.saved_profits += profit_dec
        self.total_earned += profit_dec

        # Update stats
        self.wins += 1
        self.consecutive_wins += 1

        # Increase bet by X% (of current bet, NOT profit!)
        # Example: 0.5 * 1.10 = 0.55
        old_bet = self.current_bet
        multiplier = Decimal('1') + (self.profit_increase_pct / Decimal('100'))
        self.current_bet = self.current_bet * multiplier

        # CRITICAL: Never exceed max bet
        if self.current_bet > self.max_bet:
            print(f"   [LIMIT] Bet capped at {float(self.max_bet):.2f} USDC (max {float(self.max_bet_multiplier)}x)")
            self.current_bet = self.max_bet

        bet_increase = self.current_bet - old_bet

        # Prepare result
        result = {
            'profit': float(profit_dec),
            'saved_total': float(self.saved_profits),
            'bet_increase': float(bet_increase),
            'old_bet': float(old_bet),
            'new_bet': float(self.current_bet),
            'consecutive_wins': self.consecutive_wins
        }

        # Persist state and log trade
        self._save_state()
        self._log_trade({
            'outcome': 'win',
            'profit': float(profit_dec),
            'new_bet': float(self.current_bet),
            'total_wins': self.wins,
            'total_losses': self.losses,
            'saved_profits': float(self.saved_profits),
            'total_earned': float(self.total_earned)
        })

        return result

    def process_loss(self, loss: float) -> dict:
        """
        Process losing trade

        Args:
            loss: Loss amount (negative)

        Returns:
            Dict with updated state
        """
        loss_dec = Decimal(str(loss))

        # Update totals (saved profits NEVER touched!)
        self.total_earned += loss_dec

        # Update stats
        self.losses += 1
        self.consecutive_wins = 0

        # RESET to default bet on ANY loss
        old_bet = self.current_bet
        self.current_bet = self.initial_bet_usdt

        # Prepare result
        result = {
            'loss': float(loss_dec),
            'saved_total': float(self.saved_profits),  # Unchanged!
            'old_bet': float(old_bet),
            'new_bet': float(self.current_bet),
            'reset': True
        }

        # Persist state and log trade
        self._save_state()
        self._log_trade({
            'outcome': 'loss',
            'loss': float(loss_dec),
            'new_bet': float(self.current_bet),
            'total_wins': self.wins,
            'total_losses': self.losses,
            'saved_profits': float(self.saved_profits),
            'total_earned': float(self.total_earned)
        })

        return result

    def get_current_bet(self) -> float:
        """Get current bet size"""
        return float(self.current_bet)

    def calculate_dynamic_bet(self, ml_confidence: float, market_depth: float,
                             dynamic_sizing_enabled: bool = True,
                             max_bet_multiplier: float = 5.0) -> float:
        """
        Calculate dynamic bet size based on ML confidence and market depth

        Args:
            ml_confidence: ML prediction probability (0.0 to 1.0)
            market_depth: Total orderbook depth (shares)
            dynamic_sizing_enabled: Enable dynamic sizing
            max_bet_multiplier: Maximum bet multiplier from initial bet

        Returns:
            Recommended bet size in USDC
        """
        if not dynamic_sizing_enabled:
            return self.get_current_bet()

        base_bet = float(self.current_bet)

        # Confidence multiplier: Scale by how far from 50% (uncertain)
        # prob_up = 0.5 → 0% away → 1.0x multiplier
        # prob_up = 0.7 → 20% away → 1.4x multiplier
        # prob_up = 1.0 → 50% away → 2.0x multiplier
        confidence_distance = abs(ml_confidence - 0.5)  # 0.0 to 0.5
        confidence_multiplier = 1.0 + (confidence_distance * 2)  # 1.0x to 2.0x

        # Depth multiplier: Scale by market liquidity
        # depth < 500: 0.5x (thin market)
        # depth = 1000: 1.0x (normal)
        # depth = 2000: 2.0x (deep market, max)
        depth_multiplier = min(market_depth / 1000, 2.0)
        depth_multiplier = max(depth_multiplier, 0.5)  # Minimum 0.5x

        # Calculate dynamic bet
        dynamic_bet = base_bet * confidence_multiplier * depth_multiplier

        # Apply maximum bet constraint
        max_bet = float(self.initial_bet_usdt) * max_bet_multiplier
        final_bet = min(dynamic_bet, max_bet)

        # Round to 2 decimals
        return round(final_bet, 2)

    def get_statistics(self) -> dict:
        """Get trading statistics"""
        total_trades = self.wins + self.losses
        win_rate = (self.wins / total_trades * 100) if total_trades > 0 else 0

        return {
            'total_trades': total_trades,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': win_rate,
            'consecutive_wins': self.consecutive_wins,
            'saved_profits': float(self.saved_profits),
            'total_earned': float(self.total_earned),
            'current_bet': float(self.current_bet),
            'roi': (float(self.total_earned) / float(self.initial_bet_usdt) * 100) if float(self.initial_bet_usdt) > 0 else 0
        }
