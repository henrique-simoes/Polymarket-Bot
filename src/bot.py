"""
Main Bot - Orchestrates all components for automated trading.
Features: 
- REAL Market Orders (Low Minimums)
- Official Metadata Strike Sync
- Enhanced ML & Arbitrage
- Persistent History & Logging
- Rich CLI Dashboard (Non-Blocking)
- Binance Data Integration (CCXT)
- Detailed Trace Logging
- PARALLEL EXECUTION (Thread-Safe)
- SELF-DIAGNOSTIC (Doctor)
"""

import os
import time
import yaml
import logging
import numpy as np
import pandas as pd
import traceback
from typing import Optional
from datetime import datetime, timezone
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Rich UI Imports
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.console import Console
from rich.text import Text
from rich import box

# Import components
from .core.wallet import WalletManager
from .core.polymarket import PolymarketMechanics
from .core.market_15m import Market15M
from .core.monitoring import RealTimeMonitor
from .core.price_feed import RealtimePriceFeed
from .core.persistence import TradeHistoryManager
from .core.order_tracker import OrderTracker
from .core.websocket_manager import PolymarketWebSocket
from .core.exchange_data import ExchangeDataManager
from .core.historical_data import HistoricalDataManager
from .core.learning_simulator import LearningSimulator
from .core.learning_persistence import LearningPersistence
from .core.learning_recommendation import LearningRecommendation
from .core.phantom_tracker import PhantomTracker
from .ml.features import FeatureExtractor
from .ml.learning import ContinuousLearningEngine
from .ml.position_tracker import PositionTracker
from .ml.exit_timing_learner import ExitTimingLearner
from .ml.profit_taking_engine import ProfitTakingEngine
from .ml.time_decay_calibrator import TimeDecayCalibrator
from .ml.time_decay_analytics import TimeDecayAnalytics
from .analysis.arbitrage import PriceArbitrageDetector
from .analysis.pure_arbitrage import PureArbitrageDetector
from .analysis.timeframes import MultiTimeframeAnalyzer
# RegimeDetector removed - regime logic retired
from .analysis.correlation_engine import CorrelationEngine
from .trading.strategy import TradingStrategy
from .core.doctor import BotDoctor
from .utils.startup_recommendations import StartupRecommendationEngine
from .utils.vwap import get_vwap_calculator

# Setup Standard Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("bot.log")]
)
logger = logging.getLogger("PolymarketBot")
console = Console()

# Setup Trace Logger
trace_logger = logging.getLogger("BotTrace")
trace_logger.setLevel(logging.DEBUG)
fh = logging.FileHandler("bot_trace.log")
fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
trace_logger.addHandler(fh)

# Setup Time-Decay Logger (Separate file for Time-Decay Sniper mode)
td_logger = logging.getLogger("TimeDecay")
td_logger.setLevel(logging.INFO)
td_fh = logging.FileHandler("time_decay.log")
td_fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
td_logger.addHandler(td_fh)
td_logger.propagate = False  # Don't propagate to root logger

class AdvancedPolymarketBot:
    def __init__(self, config_path: str = 'config/config.yaml'):
        console.clear()
        console.print(Panel.fit("[bold blue]INITIALIZING ADVANCED POLYMARKET BOT[/bold blue]", border_style="blue"))
        load_dotenv()
        
        try:
            with open(config_path, 'r') as f: self.config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}"); raise

        self.coins = self.config['trading'].get('coins', ['BTC', 'ETH', 'SOL'])
        self.history_manager = TradeHistoryManager()
        self.balance = 0.0
        self.arb_only_mode = False
        self.learning_mode = False  # NEW: Learning mode flag
        self.pure_arbitrage_mode = self.config.get('pure_arbitrage', {}).get('enabled', False)  # NEW: Pure arbitrage mode
        self.time_decay_sniper_mode = False  # NEW: Time-Decay Sniper mode
        self.low_vol_lotto_mode = False  # Low-Vol Lotto mode
        self.market_making_mode = self.config.get('market_making', {}).get('enabled', False)  # NEW: Market making mode
        self.user_max_bet = 5.0
        self.risk_profile = "any"
        self.last_action_msg = "System Ready"
        self.current_status = "Standby"
        self.window_info = {'seconds_remaining': 0, 'seconds_elapsed': 0}
        self.predictions = {}
        self.active_coins = []
        self.start_prices = {}
        self.strike_types = {} # NEW: Track if official or approx
        self.round_state = "INIT"
        self.active_round_end = None
        self.spinner = ['|', '/', '-', '\\']
        self.spin_idx = 0
        self.last_ui_update = 0
        self.bet_lock = Lock()

        # Round budget tracking (CRITICAL FIX)
        self.round_budget_spent = 0.0  # Total spent in current round
        self.round_coins_bet = set()   # Coins already bet on this round
        self.current_round_bets = []   # AUDIT FIX: Initialize current round bets list

        # VWAP Calculator - Initialize to None, set in mode selection
        self.vwap_calculator = None    # AUDIT FIX: Initialize for all modes
        self._last_stale_cleanup = 0   # AUDIT FIX: Initialize stale cleanup timer

        # Edge Cooldown (regime detection)
        cooldown_cfg = self.config.get('risk_management', {}).get('edge_cooldown', {})
        self.edge_cooldown_enabled = cooldown_cfg.get('enabled', False)
        self.edge_cooldown_pause_threshold = cooldown_cfg.get('pause_threshold', 8.0)
        self.edge_cooldown_pause_pct = cooldown_cfg.get('pause_edge_pct', 20.0)
        self.edge_cooldown_pause_after = cooldown_cfg.get('pause_after_rounds', 2)
        self.edge_cooldown_resume_threshold = cooldown_cfg.get('resume_threshold', 15.0)
        self.edge_cooldown_resume_pct = cooldown_cfg.get('resume_edge_pct', 40.0)
        self.edge_cooldown_resume_after = cooldown_cfg.get('resume_after_rounds', 2)

        self.cooldown_active = False
        self.consecutive_low_edge_rounds = 0
        self.consecutive_signal_rounds = 0
        self.round_edge_samples = []          # List of edge values collected during MONITOR/SNIPE
        self.round_edge_per_coin = {}         # Per-coin edge samples: {coin: [edges]}
        self.cooldown_history = []            # For dashboard: last N round summaries
        self.round_number = 0                 # Round counter for summary logs

        # Learning Mode Components (NEW)
        self.learning_simulator = None  # Initialized after user selects learning mode
        self.learning_persistence = LearningPersistence()
        self.learning_recommender = LearningRecommendation()

        # Phantom Trade Tracker - Records rejected opportunities and their outcomes (ALL MODES)
        self.phantom_tracker = PhantomTracker() 
        
        funder = self.config['polymarket'].get('funder')
        if funder == "0x...": funder = None 
        
        logger.info(f"Initializing components... (Funder: {funder})")
        if funder: console.print(f"[green]Using Proxy Wallet: {funder}[/green]")
        else: console.print("[yellow]Using EOA Wallet (No Proxy Configured)[/yellow]")
        
        # Pass proxy address to wallet manager for correct balance checks
        self.wallet = WalletManager(proxy_address=funder)
        
        self.polymarket = PolymarketMechanics(
            private_key=os.getenv('WALLET_PRIVATE_KEY'),
            chain_id=self.config['polymarket'].get('chain_id', 137),
            signature_type=self.config['polymarket'].get('signature_type', 0),
            funder=funder
        )
        
        self.market_15m = Market15M(self.polymarket)
        self.order_tracker = OrderTracker(self.polymarket.client, self.history_manager)

        # Recover any trades left unsettled from previous runs (wallet is source of truth)
        try:
            proxy_addr = self.polymarket.funder_address
            if proxy_addr:
                result = self.order_tracker.sync_trades_from_wallet(proxy_addr)
                if result['settled'] > 0:
                    console.print(f"[green]Settled {result['settled']} trade(s) via wallet sync[/green]")
                if result['discovered'] > 0:
                    console.print(f"[yellow]Discovered {result['discovered']} trade(s) from wallet[/yellow]")
        except Exception as e:
            logger.error(f"Trade recovery failed (non-fatal): {e}")

        # Initialize shared price feed BEFORE detectors so they can use it
        self.price_feed = self._init_price_feed()

        # Pure Arbitrage Mode: Skip ML initialization entirely
        if self.pure_arbitrage_mode:
            logger.info("[PURE ARBITRAGE MODE] ML features disabled")
            console.print("[bold green]PURE ARBITRAGE MODE ENABLED[/bold green] - No ML, only mathematical arbitrage")
            self.learning_engine = None
            self.feature_extractor = None
            self.monitor = None
            self.arbitrage_detector = PureArbitrageDetector(self.config, price_feed=self.price_feed)
        else:
            self.learning_engine = ContinuousLearningEngine(self.config['machine_learning'])
            self.feature_extractor = FeatureExtractor()
            self.monitor = RealTimeMonitor(self.learning_engine)
            self.arbitrage_detector = PriceArbitrageDetector(self.config, price_feed=self.price_feed)
            # Time-Decay analytics and calibration
            self.time_decay_analytics = TimeDecayAnalytics()  # Analytics tracker
            self.time_decay_calibrator = TimeDecayCalibrator(analytics=self.time_decay_analytics)  # ML calibration for Time-Decay mode
            self.vwap_calculator = None  # Initialized when Time-Decay mode selected

            # Backfill ML training from corrected wallet outcomes
            try:
                trades = self.history_manager.history if hasattr(self.history_manager, 'history') else []
                if trades:
                    n = self.learning_engine.backfill_from_trade_history(trades)
                    if n > 0:
                        console.print(f"[green]ML trained on {n} new observations from wallet history[/green]")
            except Exception as e:
                logger.error(f"ML backfill failed (non-fatal): {e}")

        self.exchange_data = ExchangeDataManager()

        # Historical data and correlation engine (Week 3)
        # Note: Regime detection retired - no longer affects trading
        self.historical_data = HistoricalDataManager()
        self.correlation_engine = CorrelationEngine(self.historical_data)

        # Profit-taking system (Week 4) - Optional, disabled by default
        self.profit_taking_enabled = self.config['risk_management']['position_management'].get('enabled', False)
        if self.profit_taking_enabled:
            self.position_tracker = PositionTracker(self.market_15m, None)  # price_feed added later
            self.exit_timing_learner = ExitTimingLearner()
            self.profit_taking_engine = ProfitTakingEngine(
                self.position_tracker,
                self.exit_timing_learner,
                self.market_15m
            )
            logger.info("Profit-taking system enabled")
        else:
            self.position_tracker = None
            self.exit_timing_learner = None
            self.profit_taking_engine = None
            logger.info("Profit-taking system disabled (config: position_management.enabled = false)")


        self.ws_manager = PolymarketWebSocket(ws_url=self.config['polymarket'].get('ws_url'))
        self.ws_manager.start()

        tc = self.config['trading']
        self.strategy = TradingStrategy(tc.get('initial_bet_usdc') or 1.0, tc['profit_increase_pct'])
        
        # Skip MTF and ML initialization if pure arbitrage mode
        if not self.pure_arbitrage_mode:
            self.mtf_analyzer = {c: MultiTimeframeAnalyzer(self.config) for c in self.coins}
            for c in self.coins: self.learning_engine.initialize_model(c)
        else:
            self.mtf_analyzer = None
            logger.info("Skipped MTF analyzer and ML initialization (Pure Arbitrage Mode)")
        
        self.arbitrage_detector.start_price_feeds(self.coins)
        self.exchange_data.start()

        # Start profit-taking engine if enabled (Week 4)
        if self.profit_taking_enabled and self.profit_taking_engine:
            # Update position tracker with price feed
            self.position_tracker.price_feed = self.price_feed
            # Start monitoring
            self.profit_taking_engine.start()

        self.doctor = BotDoctor()
        self.doctor.start()
        
        self._check_initial_state()
        self._ask_user_preferences()
        trace_logger.info("Bot initialized and preferences set.")
        logger.info("Bot initialized successfully.")

    def _ask_user_preferences(self):
        console.print("\n[bold yellow]USER CONFIGURATION[/bold yellow]")
        console.print(f"Balance: [green]${self.balance:.2f} USDC[/green]")

        # Show learning mode recommendations if available
        self._show_learning_recommendations()

        # Mode profitability analysis (recent resolved markets)
        try:
            from scripts.analyze_best_mode import ModeAnalyzer
            analyzer = ModeAnalyzer(hours=12, coin_slug='btc')
            mode_analysis = analyzer.run_analysis()
            analyzer.display_results(mode_analysis, use_rich=True)
        except Exception as e:
            logger.warning(f"Mode profitability analysis failed: {e}")

        console.print("\n[bold cyan][1] MODE SELECTION[/bold cyan]")
        console.print("  A. Arbitrage Only (Sniper Mode)")
        console.print("  B. Standard ML (Predictive Mode)")
        console.print("  C. Learning Mode (Paper Trading - No Real Money)")
        console.print("  D. Time-Decay Sniper (High-Probability + Math)")
        console.print("  E. Time-Decay LEARNING (Virtual Time-Decay) [bold green]★ TEST SAFELY![/bold green]")
        console.print("  F. Low-Vol Lotto (Contrarian Cheap Tokens)")
        mode_in = console.input("  Select Mode (A/B/C/D/E/F) [A]: ").lower().strip()

        if mode_in == 'c':
            self.learning_mode = True
            self.arb_only_mode = False
            self.time_decay_sniper_mode = False
            console.print("\n[bold green]LEARNING MODE ACTIVATED[/bold green]")
            console.print("  • No real money will be spent")
            console.print("  • All trades are simulated")
            console.print("  • ML will train on virtual trades")
            console.print("  • Use this to collect training data risk-free")
        elif mode_in == 'd':
            self.learning_mode = False
            self.arb_only_mode = False
            self.time_decay_sniper_mode = True

            # Initialize VWAP calculator for Time-Decay mode
            self.vwap_calculator = get_vwap_calculator(window_seconds=900)  # 15-minute window
            td_logger.info("VWAP calculator initialized (15-minute rolling window)")

            console.print("\n[bold magenta]TIME-DECAY SNIPER MODE ACTIVATED[/bold magenta]")
            console.print("  • Targets 40-90¢ tokens (lowered from 60¢)")
            console.print("  • Exploits time-decay mathematical certainty")
            console.print("  • High win rate (75-85% expected)")
            console.print("  • VWAP features enabled (experimental) ★")
        elif mode_in == 'e':
            # TIME-DECAY LEARNING MODE: Combines virtual trading + Time-Decay strategy
            self.learning_mode = True  # Virtual trades only
            self.arb_only_mode = False
            self.time_decay_sniper_mode = True  # Use Time-Decay strategy

            # Initialize VWAP calculator for Time-Decay mode
            self.vwap_calculator = get_vwap_calculator(window_seconds=900)  # 15-minute window
            td_logger.info("VWAP calculator initialized (15-minute rolling window)")

            console.print("\n[bold green]TIME-DECAY LEARNING MODE ACTIVATED[/bold green]")
            console.print("  • [yellow]Virtual trading only - NO REAL MONEY![/yellow]")
            console.print("  • Uses Time-Decay strategy (40-90¢ tokens)")
            console.print("  • Trains Time-Decay ML system safely")
            console.print("  • Logs to time_decay.log with [LEARNING] tag")
            console.print("  • Perfect for testing Option 1 (40¢ threshold)")
            console.print("  • Your Time-Decay ML will learn from virtual trades!")
        elif mode_in == 'f':
            self.learning_mode = False
            self.arb_only_mode = False
            self.time_decay_sniper_mode = False
            self.low_vol_lotto_mode = True
            console.print("\n[bold cyan]LOW-VOL LOTTO MODE ACTIVATED[/bold cyan]")
            console.print("  • Buys cheap tokens (≤25¢) during low-volatility")
            console.print("  • Exploits price hovering near strike")
            console.print("  • Only $1 per bet, high asymmetry")
            console.print("  • Auto-detects low-vol conditions via vol ratio")
        elif mode_in == 'a':
            self.learning_mode = False
            self.arb_only_mode = True
            self.pure_arbitrage_mode = True  # Route to pure arb path (line 2472)
            self.arbitrage_detector = PureArbitrageDetector(self.config, price_feed=self.price_feed)
            self.time_decay_sniper_mode = False
            self.low_vol_lotto_mode = False
            self.risk_profile = "any"  # Pure arb uses any price level
            console.print("\n[bold yellow]PURE ARBITRAGE MODE ACTIVATED[/bold yellow]")
            console.print("  • Uses BS fair value vs Polymarket price divergence")
            console.print("  • No ML predictions, only mathematical edge")
            console.print("  • Vol-scaled distance guard active")
        else:
            # Mode B (Standard ML) or default
            self.learning_mode = False
            self.arb_only_mode = False
            self.pure_arbitrage_mode = False
            self.time_decay_sniper_mode = False
            self.low_vol_lotto_mode = False

        # Coin selection
        console.print("\n[bold cyan][2] COIN SELECTION[/bold cyan]")
        console.print("  A. All (BTC, ETH, SOL)")
        console.print("  B. BTC only")
        console.print("  E. ETH only")
        console.print("  S. SOL only")
        coin_in = console.input("  Select Coins (A/B/E/S) [A]: ").lower().strip()
        if coin_in == 'b':
            self.coins = ['BTC']
            console.print("  [yellow]Trading BTC only[/yellow]")
        elif coin_in == 'e':
            self.coins = ['ETH']
            console.print("  [yellow]Trading ETH only[/yellow]")
        elif coin_in == 's':
            self.coins = ['SOL']
            console.print("  [yellow]Trading SOL only[/yellow]")
        else:
            console.print("  [green]Trading all coins (BTC, ETH, SOL)[/green]")

        # Risk profile selection (skip for Time-Decay mode - has built-in profile)
        if not self.time_decay_sniper_mode:
            console.print("\n[bold cyan][3] RISK PROFILE[/bold cyan]")
            console.print("  1. Low Probability (Lotto)")
            console.print("  2. High Probability (Safe)")
            console.print("  3. Trust Algorithm (Any)")
            rp = console.input("  Select Profile (1/2/3) [3]: ").strip()
            if rp == '1': self.risk_profile = 'low'
            elif rp == '2': self.risk_profile = 'high'
            else: self.risk_profile = 'any'
        else:
            # Time-Decay mode uses its own risk profile (40-90¢ range - Option 1)
            self.risk_profile = 'time_decay'
            console.print("\n[bold cyan][3] RISK PROFILE[/bold cyan]")
            console.print("  [magenta]Built-in: Time-Decay (40-90¢ tokens only)[/magenta]")

        console.print("\n[bold cyan][4] BUDGET[/bold cyan]")
        if self.learning_mode:
            console.print("  [yellow]This is the VIRTUAL budget for learning mode[/yellow]")
            rec_bet = 10.0  # Default virtual balance
            bet_input = console.input(f"  Virtual Balance (Default: ${rec_bet:.2f}): $").strip()
        else:
            console.print("  [yellow]This is the TOTAL budget for all coins per 15-minute window[/yellow]")
            rec_bet = min(self.balance * 0.95, 10.0) if self.balance > 5 else self.balance * 0.95
            bet_input = console.input(f"  Total Round Budget (Default: ${rec_bet:.2f}): $").strip()

        try: self.user_max_bet = float(bet_input) if bet_input else rec_bet
        except (ValueError, TypeError): self.user_max_bet = rec_bet

        # Update TradingStrategy base bet to match user input
        # This ensures progressive betting resets to user's chosen amount
        from decimal import Decimal
        from pathlib import Path

        user_bet_amount = self.user_max_bet
        state_file = Path('data/strategy_state.json')

        # Store old initial bet to detect if we're in a fresh session
        old_initial_bet = self.strategy.initial_bet_usdt

        # Always update the BASE bet (where it resets on loss)
        self.strategy.initial_bet_usdt = Decimal(str(user_bet_amount))
        self.strategy.max_bet = self.strategy.initial_bet_usdt * self.strategy.max_bet_multiplier

        # If no saved state exists, or if current bet equals old base (fresh start),
        # then set current bet to user's amount
        if not state_file.exists() or self.strategy.current_bet == old_initial_bet:
            self.strategy.current_bet = Decimal(str(user_bet_amount))
            logger.info(f"Progressive betting initialized: Base=${user_bet_amount:.2f}, Current=${float(self.strategy.current_bet):.2f}")
        else:
            # Preserved progressive bet from previous session, but updated reset point
            logger.info(f"Progressive betting restored: Base=${float(self.strategy.initial_bet_usdt):.2f} (new), Current=${float(self.strategy.current_bet):.2f} (from state)")
            logger.info(f"  → On next loss, bet will reset to ${float(self.strategy.initial_bet_usdt):.2f}")

        if self.learning_mode:
            console.print(f"  [green]Virtual balance set: ${self.user_max_bet:.2f}[/green]")
            # Initialize learning simulator with virtual balance
            self.learning_simulator = LearningSimulator(initial_balance=self.user_max_bet)
        else:
            console.print(f"  [green]Budget set: ${self.user_max_bet:.2f} total per 15-minute window[/green]")

        # Log mode clearly for debugging
        logger.info("=" * 60)
        if self.learning_mode:
            logger.info("    BOT MODE: LEARNING (Virtual Trading)")
            logger.info("    Trades save to: data/learning_trades.json")
            logger.info(f"    Virtual Balance: ${self.user_max_bet:.2f}")
        else:
            logger.info("    BOT MODE: REAL (Live Trading)")
            logger.info("    Trades save to: data/trade_history.json")
            logger.info(f"    Real Balance: ${self.balance:.2f} USDC")
            logger.info(f"    Budget per Round: ${self.user_max_bet:.2f}")
        logger.info("=" * 60)

        time.sleep(1)

    def _show_learning_recommendations(self):
        """Show recommendations based on historical performance"""
        try:
            # Overall performance recommendations (Week 5-6)
            recommendation_engine = StartupRecommendationEngine(
                self.history_manager,
                self.learning_persistence
            )

            overall_analysis = recommendation_engine.analyze_and_recommend(min_trades=20)

            if overall_analysis.get('has_recommendations'):
                console.print("\n[bold cyan]PERFORMANCE ANALYSIS[/bold cyan]")
                console.print(f"  Total Trades: {overall_analysis['total_trades']}")

                for i, rec in enumerate(overall_analysis['recommendations'], 1):
                    console.print(f"  {i}. {rec}")

            # Learning mode specific recommendations
            from .core.learning_persistence import LearningPersistence
            from .core.learning_recommendation import LearningRecommendation

            persistence = LearningPersistence()
            recommender = LearningRecommendation()

            trades = persistence.load_trades()
            if len(trades) > 0:
                stats = persistence.get_statistics()
                analysis = recommender.analyze(trades, stats)

                console.print("\n[bold magenta]LEARNING MODE HISTORY[/bold magenta]")
                console.print(f"  Virtual Trades: {stats['total_trades']}")
                console.print(f"  Win Rate: {stats['win_rate']:.1f}%")
                console.print(f"  Total P&L: ${stats['total_pnl']:+.2f}")
                console.print(f"  Progress: {recommender.get_progress_display(trades, stats)}")

                if analysis['ready_for_live']:
                    console.print(f"\n  [bold green]✓ Ready for live trading![/bold green]")
                else:
                    console.print(f"\n  [yellow]• {analysis['reason']}[/yellow]")

            # Volatility analysis for mode suggestion
            try:
                vol_analysis = recommendation_engine.analyze_volatility(self.historical_data)
                if vol_analysis and vol_analysis.get('results'):
                    console.print("\n[bold cyan]VOLATILITY ANALYSIS[/bold cyan]")
                    for coin, data in vol_analysis.get('results', {}).items():
                        status = "[red]LOW[/red]" if data.get('is_low_vol') else "[green]NORMAL[/green]"
                        console.print(f"  {coin}: Recent={data['recent_vol']:.2f} vs Assumed={data['assumed_vol']:.2f} "
                                     f"(ratio={data['vol_ratio']:.1f}x) {status}")

                    if vol_analysis.get('suggest_low_vol_lotto'):
                        console.print(f"\n  [bold yellow]Low-vol conditions detected — Mode F (Low-Vol Lotto) recommended[/bold yellow]")
                    elif vol_analysis.get('suggest_wider_distance'):
                        console.print(f"\n  [yellow]Vol-scaled distance guard will widen thresholds automatically[/yellow]")
            except Exception as e:
                logger.debug(f"Vol analysis display failed: {e}")

        except Exception as e:
            # Silently skip if no data exists yet
            pass

    def _init_price_feed(self):
        try:
            feed = RealtimePriceFeed()
            feed.start()
            return feed
        except Exception: return None

    def _check_initial_state(self):
        try:
            # Use WalletManager for robust checks
            approvals = self.wallet.check_polymarket_approvals()
            self.balance = self.wallet.get_usdc_balance()
            
            if not approvals['usdc_approved'] or not approvals['ctf_approved']:
                logger.info("Approvals missing. Triggering on-chain approval...")
                console.print("[bold yellow]Approving tokens for trading...[/bold yellow]")
                success = self.wallet.approve_polymarket_trading()
                if not success:
                    logger.error("Failed to approve tokens. Trading may fail.")
            
            logger.info(f"Wallet Balance: ${self.balance:.2f} USDC")
        except Exception as e:
            logger.error(f"Initial state check failed: {e}")

    def make_layout(self) -> Layout:
        layout = Layout()

        # Time-Decay mode: Add analytics section
        if self.time_decay_sniper_mode:
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="main", size=12),
                Layout(name="middle", size=25),
                Layout(name="footer", size=12),
                Layout(name="analytics", size=20)  # New: Time-Decay analytics
            )
        else:
            # Standard layout: header, main (market + stats), middle (trades + ml), footer (log + correlations)
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="main", size=12),
                Layout(name="middle", size=25),
                Layout(name="footer", size=12)
            )

        layout["main"].split_row(Layout(name="market"), Layout(name="stats", size=40))
        layout["middle"].split_row(Layout(name="trades"), Layout(name="ml_stats", size=45))
        layout["footer"].split_row(Layout(name="log", size=60), Layout(name="correlations", size=40))
        return layout

    def update_dashboard(self) -> Layout:
        # Reload history from disk to ensure latest data is shown
        self.history_manager.history = self.history_manager._load_history()
        stats = self.history_manager.get_stats()
        # Add mode indicators to header
        mode_indicator = ""
        if self.learning_mode:
            mode_indicator = " | LEARNING MODE "
        elif self.time_decay_sniper_mode:
            mode_indicator = " | TIME-DECAY SNIPER "

        mode_style = "bold green on black" if self.learning_mode else "bold magenta on black"

        # Edge Cooldown indicator (not applicable to Mode A — its edge scale doesn't match)
        cooldown_text = ""
        if self.edge_cooldown_enabled and not self.pure_arbitrage_mode:
            if self.cooldown_active:
                cooldown_text = f" | COOLDOWN ({self.consecutive_signal_rounds}/{self.edge_cooldown_resume_after} signal)"
            elif self.consecutive_low_edge_rounds > 0:
                cooldown_text = f" | Low edge {self.consecutive_low_edge_rounds}/{self.edge_cooldown_pause_after}"

        cooldown_style = "bold red" if self.cooldown_active else "yellow"
        header_parts = [
            (" POLYMARKET BOT ", "bold white on blue"),
            (mode_indicator, mode_style),
            (f" | {self.current_status} | ", "bold yellow"),
        ]
        if cooldown_text:
            header_parts.append((cooldown_text, cooldown_style))
            header_parts.append((" | ", "bold yellow"))
        header_parts.append((datetime.now().strftime('%H:%M:%S'), "cyan"))

        header = Panel(Text.assemble(*header_parts), box=box.ROUNDED, style="blue")
        market_table = Table(title="Live Market Data", box=box.SIMPLE, expand=True)
        market_table.add_column("Coin", style="bold")
        market_table.add_column("Strike", justify="right")
        market_table.add_column("YES / NO", justify="right")  # Both token prices
        market_table.add_column("Real Price\n(Binance)", justify="right")  # Actual crypto price
        market_table.add_column("Edge", justify="right")
        market_table.add_column("Signal", justify="center")
        market_table.add_column("Time Left", justify="right")

        for coin in self.coins:
            pred = self.predictions.get(coin, {})
            cp = self.fetch_current_price(coin)
            edge = pred.get('edge', 0.0)
            strike = self.start_prices.get(coin, 0.0)
            stype = self.strike_types.get(coin, "Appx")
            direction = pred.get('direction', '--')

            # Get both YES and NO prices
            both_prices = self.market_15m.get_both_prices(coin)
            if both_prices:
                yes_price = both_prices['yes']
                no_price = both_prices['no']

                # Highlight the price being bet on based on direction
                if direction == "UP":
                    # Betting on YES - highlight YES price
                    price_display = f"[bold green]${yes_price:.2f}[/bold green] / ${no_price:.2f}"
                elif direction == "DOWN":
                    # Betting on NO - highlight NO price
                    price_display = f"${yes_price:.2f} / [bold red]${no_price:.2f}[/bold red]"
                else:
                    # No signal - show both without highlighting
                    price_display = f"${yes_price:.2f} / ${no_price:.2f}"
            else:
                # Fallback to old method if both_prices fails
                pp = self.market_15m.get_current_price(coin) or 0.5
                price_display = f"${pp:.2f} / --"

            sig_col = "green" if direction == "UP" else "red" if direction == "DOWN" else "white"
            market_table.add_row(coin, f"${strike:,.2f} ({stype})", price_display, f"${cp:,.2f}", f"{edge:+.1f}%", f"[{sig_col}]{direction}[/{sig_col}]", f"{self.window_info.get('seconds_remaining', 0):.0f}s")

        # Active Orders Section (using OrderTracker)
        orders_text = Text()

        # Get active orders based on mode
        if self.learning_mode and self.learning_simulator:
            # Learning mode: Show virtual positions
            active_orders = list(self.learning_simulator.virtual_positions.values())
        else:
            # Real mode: Show CLOB orders (AUDIT FIX: order_tracker initialized in __init__)
            active_orders = self.order_tracker.get_active_orders()

        if active_orders:
            for order in active_orders[:5]:  # Show top 5
                coin = order.get('coin', 'UNKNOWN')
                direction = order.get('prediction', '?')
                amount = order.get('cost', 0) or order.get('amount', 0)

                # Calculate age in seconds
                try:
                    order_time = datetime.fromisoformat(order['timestamp'])
                    age_seconds = int((datetime.now() - order_time).total_seconds())
                    age_str = f"{age_seconds}s ago"
                except (ValueError, TypeError, KeyError):
                    age_str = "unknown"

                # Color-code by direction
                color = "green" if direction == "UP" else "red"
                mode_tag = " [VIRTUAL]" if self.learning_mode else ""
                orders_text.append(
                    f"{coin} {direction} ${amount:.2f} ({age_str}){mode_tag}\n",
                    style=color
                )
        else:
            mode_prefix = "virtual " if self.learning_mode else ""
            orders_text = Text(f"No active {mode_prefix}orders", style="italic dim")

        # Calculate budget usage percentage and color
        budget_pct = (self.round_budget_spent / self.user_max_bet * 100) if self.user_max_bet > 0 else 0
        budget_color = "green" if budget_pct < 50 else "yellow" if budget_pct < 90 else "red"

        # Learning Mode: Show virtual stats + real balance
        if self.learning_mode and self.learning_simulator:
            # Get current session stats
            sim_stats = self.learning_simulator.get_stats()

            # Get cumulative stats from persistence (all past trades)
            learning_trades = self.learning_persistence.load_trades()
            persistence_stats = self.learning_persistence.get_statistics()

            # Combine: use persistence for cumulative trades/W/L, simulator for current balance
            total_trades = persistence_stats.get('total_trades', 0)
            wins = persistence_stats.get('wins', 0)
            losses = persistence_stats.get('losses', 0)
            win_rate = persistence_stats.get('win_rate', 0.0)
            total_pnl = persistence_stats.get('total_pnl', 0.0)
            roi = (total_pnl / self.learning_simulator.initial_balance * 100) if self.learning_simulator.initial_balance > 0 else 0.0

            # For progress display, use combined stats
            combined_stats = {
                'virtual_balance': sim_stats['virtual_balance'],
                'total_trades': total_trades,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'roi': roi
            }

            progress = self.learning_recommender.get_progress_display(learning_trades, combined_stats)

            perf_text = Text.assemble(
                ("VIRTUAL:  ", "bold green"), (f"${sim_stats['virtual_balance']:.2f}\n", "green"),
                ("P&L:      ", "bold"), (f"${total_pnl:+.2f} ({roi:+.1f}%)\n", "yellow" if total_pnl >= 0 else "red"),
                ("Trades:   ", "bold"), (f"{total_trades} ({wins}W/{losses}L)\n", "cyan"),
                ("Win Rate: ", "bold"), (f"{win_rate:.1f}%\n", "green" if win_rate >= 52 else "yellow"),
                ("Progress: ", "bold"), (f"{progress}\n", "magenta"),
                ("\nReal Bal: ", "dim"), (f"${self.balance:.2f} (untouched)", "dim green")
            )
            perf_panel = Panel(perf_text, title="Learning Mode Stats", box=box.ROUNDED, style="green")
        else:
            # Real Mode: Normal performance stats
            all_trades = stats['all']['count']
            all_time_pnl = stats['all']['pnl']
            all_time_wr = stats['all']['wr']

            perf_text = Text.assemble(
                ("Balance:  ", "bold"), (f"${self.balance:.2f}\n", "green"),
                ("All Time: ", "bold"), (f"${all_time_pnl:+.2f} | {all_time_wr:.1f}% WR\n", "yellow" if all_time_pnl >= 0 else "red"),
                ("1 Hour:   ", "bold"), (f"${stats['1h']['pnl']:+.2f} ({stats['1h']['count']} trades)\n", "yellow" if stats['1h']['pnl'] >= 0 else "red"),
                ("24 Hours: ", "bold"), (f"${stats['24h']['pnl']:+.2f} ({stats['24h']['count']} trades)\n", "yellow" if stats['24h']['pnl'] >= 0 else "red"),
                ("Total Trades: ", "bold"), (f"{all_trades}\n", "cyan"),
                ("Budget:   ", "bold"), (f"${self.user_max_bet:.2f}/round ({self.risk_profile.upper()})\n", "magenta"),
                ("Spent:    ", "bold"), (f"${self.round_budget_spent:.2f} ({budget_pct:.0f}%)", budget_color)
            )
            perf_panel = Panel(perf_text, title="Account Performance", box=box.ROUNDED)

        # Enhanced log panel with active orders and pending settlements
        log_text = Text()
        log_text.append(f"Last Status: {self.last_action_msg}\n\n", style="italic")
        log_text.append("Active Orders:\n", style="bold underline yellow")
        log_text.append(orders_text)

        # Add positions awaiting settlement
        log_text.append("\n\nPositions Awaiting Settlement:\n", style="bold underline cyan")
        settlement_text = self._get_pending_settlement_text()
        log_text.append(settlement_text)

        log_panel = Panel(log_text, title="Execution Log & Positions", box=box.ROUNDED)

        # Correlation Panel (Week 3) - Regime detection retired
        corr_text = Text()
        try:
            corr_summary = self.correlation_engine.get_summary()

            if corr_summary:
                corr_text.append("Cross-Market Correlations:\n", style="bold underline")
                for pair, info in corr_summary.items():
                    corr = info['correlation']
                    beta = info['beta']
                    # Color by correlation strength
                    corr_color = "green" if corr > 0.7 else "yellow" if corr > 0.4 else "red"
                    corr_text.append(f"  {pair}: ", style="bold")
                    corr_text.append(f"{corr:+.2f}", style=corr_color)
                    corr_text.append(f" (β={beta:.2f})\n")
            else:
                corr_text.append("Correlation data loading...", style="dim")

        except Exception as e:
            corr_text.append(f"Correlation data loading...", style="dim")

        corr_panel = Panel(corr_text if corr_text.plain else Text("Loading correlations...", style="dim"),
                           title="Cross-Market Correlations", box=box.ROUNDED, style="cyan")

        # Recent Trades Table (Last 50)
        trades_table = self._create_trades_table()

        # ML Training Stats Panel
        ml_stats_panel = self._create_ml_stats_panel()

        layout = self.make_layout()
        layout["header"].update(header)
        layout["market"].update(market_table)
        layout["stats"].update(perf_panel)
        layout["trades"].update(trades_table)
        layout["ml_stats"].update(ml_stats_panel)
        layout["log"].update(log_panel)
        layout["correlations"].update(corr_panel)

        # Time-Decay mode: Add comprehensive analytics panel
        if self.time_decay_sniper_mode:
            analytics_panel = self._create_time_decay_analytics_panel()
            layout["analytics"].update(analytics_panel)

        return layout

    def _create_trades_table(self) -> Panel:
        """Create a table showing the last 50 trades with outcomes"""
        table = Table(title="Recent Trades (Last 50)", box=box.SIMPLE, expand=True, show_header=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Time", style="cyan", width=8)
        table.add_column("Coin", style="bold", width=5)
        table.add_column("Dir", justify="center", width=4)
        table.add_column("Entry\nPrice", justify="right", width=6)  # Token entry price paid
        table.add_column("Cost\n(USDC)", justify="right", width=7)  # Total amount spent
        table.add_column("Outcome", justify="center", width=8)
        table.add_column("P&L\n(USDC)", justify="right", width=8)
        table.add_column("Status", justify="center", width=10)

        # Get recent trades from both real and learning mode
        all_trades = []

        # Real trades
        if hasattr(self, 'history_manager'):
            real_trades = self.history_manager.history[-50:] if self.history_manager.history else []
            logger.debug(f"[TRADES DEBUG] history_manager.history has {len(self.history_manager.history)} trades")
            logger.debug(f"[TRADES DEBUG] real_trades has {len(real_trades)} trades")
            for trade in real_trades:
                all_trades.append({**trade, 'mode': 'REAL'})

        # Learning trades
        if self.learning_mode and hasattr(self, 'learning_persistence'):
            learning_trades = self.learning_persistence.load_trades()[-50:] if self.learning_persistence.load_trades() else []
            for trade in learning_trades:
                all_trades.append({**trade, 'mode': 'VIRTUAL'})

        # Sort by timestamp (most recent last) and take last 50
        # Normalize mixed timestamp types (ISO strings vs epoch ints) to epoch float
        def _ts_sort_key(trade):
            ts = trade.get('timestamp', 0)
            if isinstance(ts, (int, float)):
                return float(ts)
            if isinstance(ts, str):
                try:
                    from datetime import datetime as _dt
                    return _dt.fromisoformat(ts).timestamp()
                except (ValueError, TypeError):
                    return 0.0
            return 0.0
        try:
            all_trades = sorted(all_trades, key=_ts_sort_key)[-50:]
        except Exception:
            pass

        # Display trades (most recent first for display)
        for idx, trade in enumerate(reversed(all_trades[-50:])):  # Show last 50
            try:
                # Parse timestamp
                ts_raw = trade.get('timestamp', '')
                if isinstance(ts_raw, (int, float)):
                    from datetime import datetime as _dt
                    time_str = _dt.fromtimestamp(ts_raw).strftime('%H:%M')
                elif isinstance(ts_raw, str) and 'T' in ts_raw:
                    time_str = ts_raw.split('T')[1][:5]  # HH:MM
                else:
                    time_str = '--:--'

                coin = trade.get('coin', '?')
                direction = trade.get('prediction', '?')
                price = trade.get('price', 0.0)
                amount = trade.get('cost', 0.0)
                won = trade.get('won')
                profit = trade.get('profit', 0.0)
                mode = trade.get('mode', 'REAL')

                # Determine status - must check value, not just key existence
                # order_tracker saves final_price=None when order fills (not yet settled)
                if trade.get('final_price') is not None and trade.get('won') is not None:
                    status = "SETTLED"
                    status_color = "green" if won else "red"
                    outcome = "✓ WIN" if won else "✗ LOSS"
                    outcome_color = "green" if won else "red"
                elif trade.get('order_status') == 'canceled':
                    status = "CANCELED"
                    status_color = "dim"
                    outcome = "---"
                    outcome_color = "dim"
                elif trade.get('order_status') == 'filled' or trade.get('status') == 'simulated_open':
                    status = "FILLED"
                    status_color = "cyan"
                    outcome = "awaiting..."
                    outcome_color = "yellow"
                else:
                    status = "PENDING"
                    status_color = "yellow"
                    outcome = "..."
                    outcome_color = "yellow"

                # Direction color
                dir_color = "green" if direction == "UP" else "red"

                # P&L color
                pnl_color = "green" if profit > 0 else "red" if profit < 0 else "white"

                # Add mode tag
                if mode == 'VIRTUAL':
                    status = f"[dim]{status}[/dim]"

                table.add_row(
                    str(idx + 1),
                    time_str,
                    coin,
                    f"[{dir_color}]{direction[:2]}[/{dir_color}]",
                    f"${price:.2f}",
                    f"${amount:.2f}",
                    f"[{outcome_color}]{outcome}[/{outcome_color}]",
                    f"[{pnl_color}]{profit:+.2f}[/{pnl_color}]",
                    f"[{status_color}]{status}[/{status_color}]"
                )
            except Exception as e:
                continue

        # If no trades, show message
        if len(all_trades) == 0:
            table.add_row("", "", "", "", "", "", "No trades yet", "", "")

        return Panel(table, title=f"Trade History ({len(all_trades)} total)", box=box.ROUNDED)

    def _get_pending_settlement_text(self) -> Text:
        """Get text showing positions waiting for market settlement"""
        text = Text()

        # Check for positions that are placed but not yet settled
        # These are trades that happened but don't have a final_price yet
        pending_positions = []

        # Check real trades
        if hasattr(self, 'history_manager'):
            recent_trades = self.history_manager.history[-20:]  # Check last 20 trades
            for trade in recent_trades:
                if 'final_price' not in trade or trade.get('final_price') is None:
                    pending_positions.append({**trade, 'mode': 'REAL'})

        # Check learning trades
        if self.learning_mode and hasattr(self, 'learning_persistence'):
            recent_learning = self.learning_persistence.load_trades()[-20:]
            for trade in recent_learning:
                if 'final_price' not in trade or trade.get('final_price') is None:
                    pending_positions.append({**trade, 'mode': 'VIRTUAL'})

        if pending_positions:
            for pos in pending_positions[-5:]:  # Show last 5
                try:
                    coin = pos.get('coin', '?')
                    direction = pos.get('prediction', '?')
                    amount = pos.get('cost', 0.0)
                    mode = pos.get('mode', 'REAL')

                    # Calculate time since placement
                    ts_str = pos.get('timestamp', '')
                    if 'T' in ts_str:
                        try:
                            order_time = datetime.fromisoformat(ts_str.replace('Z', ''))
                            age_seconds = int((datetime.now() - order_time).total_seconds())
                            if age_seconds < 60:
                                age_str = f"{age_seconds}s"
                            elif age_seconds < 3600:
                                age_str = f"{age_seconds // 60}m"
                            else:
                                age_str = f"{age_seconds // 3600}h"
                        except (ValueError, TypeError, KeyError):
                            age_str = "?"
                    else:
                        age_str = "?"

                    color = "green" if direction == "UP" else "red"
                    mode_tag = " [VIRTUAL]" if mode == 'VIRTUAL' else ""
                    text.append(
                        f"  {coin} {direction} ${amount:.2f} (placed {age_str} ago){mode_tag}\n",
                        style=color
                    )
                except (ValueError, TypeError, KeyError):
                    continue
        else:
            text.append("  No positions awaiting settlement\n", style="dim italic")

        return text

    def _create_ml_stats_panel(self) -> Panel:
        """Create a panel showing ML training progress and confidence"""
        text = Text()

        try:
            # TIME-DECAY MODE: Show calibrator stats instead of standard ML stats
            if self.time_decay_sniper_mode and hasattr(self, 'time_decay_calibrator'):
                cal_stats = self.time_decay_calibrator.get_statistics()
                total_trades = cal_stats['total_trades']
                threshold = 50

                text.append("TIME-DECAY ML CALIBRATOR\n", style="bold underline magenta")
                text.append("\nCalibration Trades:\n", style="bold")
                text.append(f"  {total_trades} trades ", style="cyan")

                if total_trades < threshold:
                    progress = int((total_trades / threshold) * 15)
                    bar = "█" * progress + "░" * (15 - progress)
                    pct = (total_trades / threshold) * 100
                    text.append(f"\n  [{bar}] {pct:.0f}%\n", style="yellow")
                    text.append(f"  {total_trades}/{threshold} to train\n", style="yellow")
                    text.append(f"  Status: ", style="bold")
                    text.append("COLLECTING DATA\n", style="yellow")
                else:
                    text.append(f"\n  Status: ", style="bold")
                    if cal_stats['is_trained']:
                        text.append("TRAINED ✓\n", style="green")
                        text.append(f"\n  Training Runs: ", style="bold")
                        text.append(f"{cal_stats['training_count']}\n", style="cyan")
                        text.append(f"  Last Accuracy: ", style="bold")
                        acc_pct = cal_stats['last_accuracy'] * 100
                        acc_color = "green" if acc_pct >= 80 else "yellow" if acc_pct >= 70 else "red"
                        text.append(f"{acc_pct:.1f}%\n", style=acc_color)
                    else:
                        text.append("READY TO TRAIN\n", style="yellow")

                # Calibration performance (only if trades placed)
                if total_trades > 0:
                    text.append("\nPERFORMANCE:\n", style="bold underline magenta")
                    win_rate = cal_stats['win_rate'] * 100
                    text.append(f"\n  Win Rate: ", style="bold")
                    wr_color = "green" if win_rate >= 75 else "yellow" if win_rate >= 65 else "red"
                    text.append(f"{win_rate:.1f}%\n", style=wr_color)

                    avg_edge = cal_stats['avg_bs_edge'] * 100
                    text.append(f"  Avg BS Edge: ", style="bold")
                    text.append(f"{avg_edge:.1f}%\n", style="cyan")

                    if 'bs_overconfidence' in cal_stats:
                        overconf = cal_stats['bs_overconfidence'] * 100
                        text.append(f"  BS Overconfidence: ", style="bold")
                        if abs(overconf) < 5:
                            text.append(f"{overconf:+.1f}% ", style="green")
                            text.append("(well calibrated)\n", style="dim")
                        elif overconf > 0:
                            text.append(f"{overconf:+.1f}% ", style="yellow")
                            text.append("(BS too optimistic)\n", style="dim")
                        else:
                            text.append(f"{overconf:+.1f}% ", style="yellow")
                            text.append("(BS too conservative)\n", style="dim")

                # PASSIVE LEARNING: Show standard ML learning engine stats (ALWAYS show)
                # This tracks observations even when no trades are placed
                text.append("\n")
                text.append("PASSIVE LEARNING:\n", style="bold underline cyan")
                text.append("(Learns patterns from all rounds)\n", style="dim italic")

                try:
                    training_stats = self.learning_engine.get_training_stats()
                    replay_size = training_stats['replay_buffer_size']
                    episode_size = training_stats['episode_buffer_total']
                    ml_threshold = 50

                    text.append(f"\n  Completed Rounds: ", style="bold")
                    text.append(f"{replay_size} labeled\n", style="cyan")

                    if replay_size < ml_threshold:
                        progress = int((replay_size / ml_threshold) * 10)
                        bar = "█" * progress + "░" * (10 - progress)
                        text.append(f"  [{bar}] {replay_size}/{ml_threshold}\n", style="yellow")
                    else:
                        text.append(f"  ML Status: ", style="bold")
                        text.append("TRAINED ✓\n", style="green")

                    text.append(f"  Current Round: ", style="bold")
                    text.append(f"{episode_size} obs\n", style="magenta")

                    # Per-coin compact view
                    coin_parts = []
                    for coin in ['BTC', 'ETH', 'SOL']:
                        coin_stats = training_stats['coins'].get(coin, {})
                        obs = coin_stats.get('episode_observations', 0)
                        coin_parts.append(f"{coin}:{obs}")
                    text.append(f"  ({', '.join(coin_parts)})\n", style="dim")

                except Exception as e:
                    text.append(f"\n  Stats loading...\n", style="dim")

            # STANDARD MODE: Show regular ML stats
            else:
                # Get training stats from learning engine
                training_stats = self.learning_engine.get_training_stats()

                # Overall stats
                replay_size = training_stats['replay_buffer_size']
                episode_size = training_stats['episode_buffer_total']
                threshold = 50

                text.append("ML TRAINING STATUS\n", style="bold underline white")
                text.append("\nLabeled Samples:\n", style="bold")
                text.append(f"  {replay_size} samples ", style="cyan")

                if replay_size < threshold:
                    progress = int((replay_size / threshold) * 15)
                    bar = "█" * progress + "░" * (15 - progress)
                    pct = (replay_size / threshold) * 100
                    text.append(f"\n  [{bar}] {pct:.0f}%\n", style="yellow")
                    text.append(f"  {replay_size}/{threshold} needed\n", style="yellow")
                    text.append(f"  Status: ", style="bold")
                    text.append("COLLECTING DATA\n", style="yellow")
                else:
                    text.append("\n  Status: ", style="bold")
                    text.append("TRAINING ACTIVE ✓\n", style="green")

                text.append(f"\nPending: ", style="bold")
                text.append(f"{episode_size} obs\n", style="magenta")

                # Per-coin stats - more compact
                text.append("\nMODEL STATUS:\n", style="bold underline white")
                for coin in ['BTC', 'ETH', 'SOL']:
                    coin_stats = training_stats['coins'].get(coin, {})
                    is_trained = coin_stats.get('is_trained', False)
                    accuracy = coin_stats.get('accuracy', 0.0)
                    episode_obs = coin_stats.get('episode_observations', 0)

                    text.append(f"\n{coin}: ", style="bold cyan")

                    if is_trained:
                        text.append("✓ ", style="green")
                        acc_color = "green" if accuracy >= 0.52 else "yellow" if accuracy >= 0.45 else "red"
                        text.append(f"{accuracy:.1%} acc", style=acc_color)

                        # Compact confidence
                        if replay_size < 100:
                            text.append(" [LOW]", style="red")
                        elif replay_size < 200:
                            text.append(" [MED]", style="yellow")
                        else:
                            text.append(" [HIGH]", style="green")
                        text.append(f"\n  {episode_obs} pending obs", style="dim")
                    else:
                        text.append("✗ NOT TRAINED", style="red")
                        need = max(0, threshold - replay_size)
                        text.append(f"\n  Need {need} more", style="dim")
                        text.append(f" | {episode_obs} pending", style="dim")

                    text.append("\n")

            # Add training info - more compact
            text.append("\n")
            text.append("Updates: After each round\n", style="dim italic")
            text.append("Retrain: Every 5 samples\n", style="dim italic")

        except Exception as e:
            text.append(f"ML stats loading...\n", style="dim red")

        return Panel(text, title="ML Training", box=box.ROUNDED, style="magenta")

    def _create_time_decay_analytics_panel(self) -> Panel:
        """Create comprehensive analytics panel for Time-Decay mode"""
        from rich.text import Text
        from rich.table import Table

        text = Text()

        try:
            if not hasattr(self, 'time_decay_analytics'):
                text.append("Analytics not initialized\n", style="dim red")
                return Panel(text, title="Time-Decay Analytics", box=box.ROUNDED, style="cyan")

            # Get all analytics data
            bs_stats = self.time_decay_analytics.get_bs_accuracy_stats()
            calibration_stats = self.time_decay_analytics.get_calibration_stats()
            best_hours = self.time_decay_analytics.get_best_hours(top_n=3)
            price_ranges = self.time_decay_analytics.get_best_price_ranges()
            coin_performance = self.time_decay_analytics.get_coin_performance()
            latest_features = self.time_decay_analytics.get_latest_feature_importance()

            # SECTION 1: Feature Importance (if ML trained)
            if latest_features:
                text.append("╔═══ FEATURE IMPORTANCE ═══╗\n", style="bold cyan")

                # Sort by importance descending
                sorted_features = sorted(latest_features.items(), key=lambda x: x[1], reverse=True)

                # Top 5 with beautiful progress bars
                for i, (feature_name, importance) in enumerate(sorted_features[:5], 1):
                    # Create progress bar (20 chars wide)
                    bar_length = int(importance * 20)
                    bar = "█" * bar_length + "░" * (20 - bar_length)

                    # Color code by importance
                    if importance >= 0.15:
                        color = "green"
                    elif importance >= 0.08:
                        color = "yellow"
                    else:
                        color = "white"

                    text.append(f"  {i}. ", style="bold")
                    text.append(f"{feature_name:25s} ", style="cyan")
                    text.append(f"[{bar}] ", style=color)
                    text.append(f"{importance*100:5.1f}%\n", style=color)

                text.append("\n")

            # SECTION 2: BS Edge Accuracy
            if bs_stats['total_trades'] > 0:
                text.append("╔═══ BLACK-SCHOLES ACCURACY ═══╗\n", style="bold magenta")
                text.append(f"  Total Trades:        ", style="bold")
                text.append(f"{bs_stats['total_trades']}\n", style="cyan")

                text.append(f"  Avg Edge (Winners):  ", style="bold")
                text.append(f"{bs_stats['avg_edge_winners']*100:+.1f}%\n", style="green")

                text.append(f"  Avg Edge (Losers):   ", style="bold")
                text.append(f"{bs_stats['avg_edge_losers']*100:+.1f}%\n", style="red")

                text.append(f"  Edge Accuracy:       ", style="bold")
                acc = bs_stats['edge_accuracy']
                acc_color = "green" if acc >= 0.5 else "yellow" if acc >= 0.3 else "red"
                text.append(f"{acc*100:.1f}%\n", style=acc_color)
                text.append("\n")

            # SECTION 3: ML Calibration Stats
            if calibration_stats['total_calibrations'] > 0:
                text.append("╔═══ ML CALIBRATION ═══╗\n", style="bold yellow")
                text.append(f"  Calibrations:        ", style="bold")
                text.append(f"{calibration_stats['total_calibrations']}\n", style="cyan")

                text.append(f"  Avg Adjustment:      ", style="bold")
                adj = calibration_stats['avg_adjustment_factor']
                adj_color = "green" if 0.9 <= adj <= 1.1 else "yellow"
                text.append(f"{adj:.3f}x\n", style=adj_color)

                text.append(f"  Avg Edge Reduction:  ", style="bold")
                text.append(f"{calibration_stats['avg_reduction']*100:.1f}%\n", style="yellow")
                text.append("\n")

            # SECTION 4: Best Times of Day
            if best_hours:
                text.append("╔═══ BEST TRADING HOURS (UTC) ═══╗\n", style="bold green")
                for i, (hour, win_rate, count) in enumerate(best_hours, 1):
                    text.append(f"  {i}. ", style="bold")
                    text.append(f"{hour:02d}:00 ", style="cyan")
                    text.append(f"→ ", style="dim")

                    wr_color = "green" if win_rate >= 0.75 else "yellow" if win_rate >= 0.65 else "white"
                    text.append(f"{win_rate*100:.1f}% ", style=wr_color)
                    text.append(f"({count} trades)\n", style="dim")
                text.append("\n")

            # SECTION 5: Best Price Ranges
            if price_ranges:
                text.append("╔═══ PRICE RANGE PERFORMANCE ═══╗\n", style="bold blue")
                for range_key, win_rate, count, avg_edge in price_ranges[:3]:
                    text.append(f"  {range_key:10s} ", style="cyan")
                    text.append(f"→ ", style="dim")

                    wr_color = "green" if win_rate >= 0.75 else "yellow" if win_rate >= 0.65 else "white"
                    text.append(f"{win_rate*100:5.1f}% WR ", style=wr_color)
                    text.append(f"| Edge: {avg_edge*100:+.1f}% ", style="yellow")
                    text.append(f"({count})\n", style="dim")
                text.append("\n")

            # SECTION 6: Entry Window Optimization (NEW!)
            entry_windows = self.time_decay_analytics.get_best_entry_windows(bucket_size_sec=60)
            if entry_windows:
                text.append("╔═══ ENTRY WINDOW PERFORMANCE ═══╗\n", style="bold magenta")

                # Show current optimal window
                optimal_window = self.time_decay_analytics.get_optimal_entry_window(min_trades=5, default_window=500)
                text.append(f"  Current Optimal: ", style="bold")
                text.append(f"{optimal_window}s ({optimal_window//60}min)\n", style="cyan")

                # Show top 3 performing windows
                for i, (window_sec, win_rate, count, avg_edge) in enumerate(entry_windows[:3], 1):
                    text.append(f"  {i}. ", style="bold")
                    text.append(f"{window_sec:3d}s ({window_sec//60}min) ", style="cyan")
                    text.append(f"→ ", style="dim")

                    wr_color = "green" if win_rate >= 0.75 else "yellow" if win_rate >= 0.65 else "white"
                    text.append(f"{win_rate*100:5.1f}% WR ", style=wr_color)
                    text.append(f"| Edge: {avg_edge*100:+.1f}% ", style="yellow")
                    text.append(f"({count})\n", style="dim")
                text.append("\n")

            # SECTION 7: Per-Coin Performance
            if coin_performance:
                text.append("╔═══ COIN PERFORMANCE ═══╗\n", style="bold white")
                for coin, win_rate, count, avg_price, avg_edge in coin_performance[:3]:
                    text.append(f"  {coin:4s} ", style="bold cyan")
                    text.append(f"→ ", style="dim")

                    wr_color = "green" if win_rate >= 0.75 else "yellow" if win_rate >= 0.65 else "white"
                    text.append(f"{win_rate*100:5.1f}% ", style=wr_color)
                    text.append(f"| Avg: {avg_price*100:.0f}¢ ", style="cyan")
                    text.append(f"| Edge: {avg_edge*100:+.1f}% ", style="yellow")
                    text.append(f"({count})\n", style="dim")

        except Exception as e:
            text.append(f"Analytics error: {e}\n", style="dim red")

        return Panel(text, title="⚡ Time-Decay Analytics", box=box.ROUNDED, style="cyan")

    def fetch_current_price(self, coin: str) -> float:
        price = None
        if self.price_feed: price = self.price_feed.get_price(coin)
        if not price: price = self.market_15m.get_real_crypto_price(coin)
        return price or 0
    def wait_for_market_resolution(self, condition_id: str, coin: str, max_wait: int = 120) -> Optional[str]:
        """
        Poll until market resolves. On-chain CTF contract is the source of truth.

        Phase 1: Fast polling via Gamma/CLOB/on-chain every 10s for up to max_wait seconds.
        Phase 2: On-chain only, every 180s, indefinitely (on-chain WILL resolve).

        Args:
            condition_id: Market condition ID
            coin: Coin symbol (for logging)
            max_wait: Maximum wait time in seconds for Phase 1 (default: 120s)

        Returns:
            'UP' or 'DOWN' if resolved, None only if condition_id is invalid
        """
        mode_label = "[LEARNING]" if self.learning_mode else "[REAL]"
        poll_interval = 10
        waited = 0

        logger.info(f"{mode_label} [RESOLUTION] Phase 1: Fast polling for {coin} (condition: {condition_id[:16]}..., max_wait={max_wait}s)")

        # Phase 1: Fast polling (Gamma → CLOB → on-chain, every 10s)
        while waited < max_wait:
            try:
                outcome = self.market_15m.check_official_resolution(condition_id)
                if outcome:
                    logger.info(f"{mode_label} [RESOLUTION] ✓ Resolved (Phase 1): {coin} → {outcome} (waited {waited}s)")
                    return outcome

                if waited % 30 == 0:
                    logger.info(f"{mode_label} [RESOLUTION] {coin}: Not resolved yet ({waited}/{max_wait}s)")

                time.sleep(poll_interval)
                waited += poll_interval
            except Exception as e:
                logger.error(f"{mode_label} [RESOLUTION] Phase 1 error: {e}")
                time.sleep(poll_interval)
                waited += poll_interval

        # Phase 2: On-chain only, every 180s, no timeout (source of truth)
        onchain_interval = 180  # 3 minutes
        onchain_waited = 0
        logger.warning(f"{mode_label} [RESOLUTION] Phase 2: On-chain polling for {coin} (every {onchain_interval}s, indefinite)")

        while True:
            try:
                outcome = self.market_15m.check_onchain_resolution(condition_id)
                if outcome:
                    logger.info(f"{mode_label} [RESOLUTION] ✓ Resolved (on-chain): {coin} → {outcome} (total wait: {waited + onchain_waited}s)")
                    return outcome

                onchain_waited += onchain_interval
                logger.info(f"{mode_label} [RESOLUTION] {coin}: On-chain not resolved yet ({onchain_waited}s in Phase 2, {waited + onchain_waited}s total)")
                time.sleep(onchain_interval)
            except Exception as e:
                logger.error(f"{mode_label} [RESOLUTION] On-chain poll error: {e}")
                onchain_waited += onchain_interval
                time.sleep(onchain_interval)

    def _evaluate_edge_cooldown(self):
        """Evaluate round edges and update cooldown state.

        Only ACTIONABLE edges are tracked — edges where check_arbitrage returned
        opportunity=True (inside dynamic window AND above min threshold). Raw BS
        edge at 800s remaining is meaningless because it can never become a bet.

        If round_edge_samples is empty, that means zero actionable opportunities
        existed this entire round — the strongest possible low-edge signal.

        Pause:  actionable edge >= pause_threshold for LESS than pause_edge_pct% → low-edge round
        Resume: actionable edge >= resume_threshold for AT LEAST resume_edge_pct% → signal round
        """
        if not self.round_edge_samples:
            max_edge = 0.0
            mean_edge = 0.0
            pct_above_pause = 0.0
            pct_above_resume = 0.0
        else:
            max_edge = max(self.round_edge_samples)
            mean_edge = sum(self.round_edge_samples) / len(self.round_edge_samples)
            above_pause = sum(1 for e in self.round_edge_samples if e >= self.edge_cooldown_pause_threshold)
            pct_above_pause = (above_pause / len(self.round_edge_samples)) * 100.0
            above_resume = sum(1 for e in self.round_edge_samples if e >= self.edge_cooldown_resume_threshold)
            pct_above_resume = (above_resume / len(self.round_edge_samples)) * 100.0

        # Record for dashboard history
        self.cooldown_history.append({
            'max_edge': max_edge,
            'mean_edge': mean_edge,
            'pct_above_pause': pct_above_pause,
            'pct_above_resume': pct_above_resume,
            'was_paused': self.cooldown_active,
            'samples': len(self.round_edge_samples)
        })
        # Keep only last 20 rounds
        self.cooldown_history = self.cooldown_history[-20:]

        if self.cooldown_active:
            # Check for resume: is this a "signal round"?
            is_signal = pct_above_resume >= self.edge_cooldown_resume_pct
            if is_signal:
                self.consecutive_signal_rounds += 1
                logger.info(f"COOLDOWN: Signal round ({pct_above_resume:.0f}% >= {self.edge_cooldown_resume_pct}% above {self.edge_cooldown_resume_threshold}%). "
                           f"Signals: {self.consecutive_signal_rounds}/{self.edge_cooldown_resume_after}")
            else:
                self.consecutive_signal_rounds = 0
                n = len(self.round_edge_samples)
                logger.info(f"COOLDOWN: Still low-edge ({n} actionable samples, mean={mean_edge:.1f}%, {pct_above_resume:.0f}% above {self.edge_cooldown_resume_threshold}%)")

            if self.consecutive_signal_rounds >= self.edge_cooldown_resume_after:
                self.cooldown_active = False
                self.consecutive_signal_rounds = 0
                self.consecutive_low_edge_rounds = 0
                logger.info("COOLDOWN LIFTED — Resuming trading")
        else:
            # Pause check: edge above pause_threshold for less than pause_edge_pct% of time → low-edge round
            # Works for 1 coin or 3 — even BTC alone has many sub-8% samples
            is_low = pct_above_pause < self.edge_cooldown_pause_pct
            if is_low:
                self.consecutive_low_edge_rounds += 1
                logger.info(f"LOW EDGE round ({pct_above_pause:.0f}% < {self.edge_cooldown_pause_pct}% above {self.edge_cooldown_pause_threshold}%, mean={mean_edge:.1f}%). "
                           f"Consecutive: {self.consecutive_low_edge_rounds}/{self.edge_cooldown_pause_after}")
            else:
                self.consecutive_low_edge_rounds = 0

            if self.consecutive_low_edge_rounds >= self.edge_cooldown_pause_after:
                self.cooldown_active = True
                self.consecutive_signal_rounds = 0
                logger.info(f"COOLDOWN ACTIVATED — {self.consecutive_low_edge_rounds} consecutive low-edge rounds ({pct_above_pause:.0f}% above {self.edge_cooldown_pause_threshold}%)")

        # Reset for next round
        self.round_edge_samples = []
        self.round_edge_per_coin = {}

    def _log_round_summary(self):
        """Log a comprehensive summary of the completed round."""
        self.round_number += 1
        bets = self.current_round_bets
        n_samples = sum(len(v) for v in self.round_edge_per_coin.values())

        logger.info(f"\n{'='*70}")
        logger.info(f"ROUND {self.round_number} SUMMARY — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*70}")
        logger.info(f"  (Only actionable edges counted — opportunity=True, inside dynamic window)")

        # Per-coin edge stats
        for coin in self.active_coins:
            coin_edges = self.round_edge_per_coin.get(coin, [])
            if coin_edges:
                c_max = max(coin_edges)
                c_mean = sum(coin_edges) / len(coin_edges)
                c_min = min(coin_edges)
                logger.info(f"  {coin:4s}: mean={c_mean:.1f}%  max={c_max:.1f}%  min={c_min:.1f}%  ({len(coin_edges)} actionable)")
            else:
                logger.info(f"  {coin:4s}: 0 actionable edges")

        # Overall edge stats
        all_edges = self.round_edge_samples
        if all_edges:
            overall_mean = sum(all_edges) / len(all_edges)
            overall_max = max(all_edges)
            sorted_edges = sorted(all_edges)
            p75 = sorted_edges[int(len(sorted_edges) * 0.75)] if len(sorted_edges) > 3 else overall_max
            pct_above_pause = sum(1 for e in all_edges if e >= self.edge_cooldown_pause_threshold) / len(all_edges) * 100
            pct_above_resume = sum(1 for e in all_edges if e >= self.edge_cooldown_resume_threshold) / len(all_edges) * 100
            logger.info(f"  ALL : mean={overall_mean:.1f}%  max={overall_max:.1f}%  p75={p75:.1f}%  ({len(all_edges)} actionable)")
            logger.info(f"  PAUSE CHECK: {pct_above_pause:.0f}% of actionable edges >={self.edge_cooldown_pause_threshold}% (need <{self.edge_cooldown_pause_pct}% to be low-edge)")
            logger.info(f"  RESUME CHECK: {pct_above_resume:.0f}% of actionable edges >={self.edge_cooldown_resume_threshold}% (need >={self.edge_cooldown_resume_pct}% to be signal)")
        else:
            overall_mean = 0.0
            logger.info(f"  ALL : 0 actionable edges this round (automatic low-edge)")

        # Bets placed
        if bets:
            for b in bets:
                coin = b.get('coin', '?')
                direction = b.get('prediction', b.get('direction', '?'))
                cost = b.get('cost', b.get('amount', 0))
                logger.info(f"  BET: {coin} {direction} ${cost:.2f}")
        else:
            logger.info(f"  BETS: None this round")

        # Cooldown status
        cd_status = "ACTIVE" if self.cooldown_active else "inactive"
        logger.info(f"  COOLDOWN: {cd_status} | low_edge_streak={self.consecutive_low_edge_rounds}/{self.edge_cooldown_pause_after} | signal_streak={self.consecutive_signal_rounds}/{self.edge_cooldown_resume_after}")
        logger.info(f"{'='*70}")

    def background_settlement(self, placed_bets, start_prices, seconds_remaining_at_start=0):
        try:
            mode_label = "[LEARNING]" if self.learning_mode else "[REAL]"
            logger.info(f"{mode_label} [SETTLEMENT] Starting settlement for {len(placed_bets)} bets")

            # Calculate proper wait time: time until market close + resolution delay
            # Market must close (900 seconds total) + Chainlink oracle fetches price (30-90s)
            resolution_delay = 90  # Conservative: 90 seconds for Chainlink oracle
            time_until_close = max(0, seconds_remaining_at_start)
            total_wait = time_until_close + resolution_delay

            logger.info(f"{mode_label} [SETTLEMENT] Market timing: {time_until_close:.0f}s until close + {resolution_delay}s resolution delay = {total_wait:.0f}s total wait")

            if total_wait > 0:
                logger.info(f"{mode_label} [SETTLEMENT] Waiting {total_wait:.0f}s for market close + resolution...")
                time.sleep(total_wait)
                logger.info(f"{mode_label} [SETTLEMENT] Wait complete, now checking market resolution...")

            # Track all official outcomes for phantom tracking
            all_outcomes = {}

            for bet in placed_bets:
                try:
                    logger.info(f"{mode_label} [SETTLEMENT] Processing bet: {bet.get('coin')} {bet.get('prediction')}")
                    coin = bet['coin']

                    # Always fetch final price (needed for learning simulator and real mode records)
                    final_p = self.fetch_current_price(coin)

                    # Get actual market resolution via Gamma API (primary) + CLOB API (backup)
                    condition_id = bet.get('condition_id')
                    actual = None

                    logger.info(f"{mode_label} [SETTLEMENT] {coin}: condition_id={condition_id}")

                    # Try to get condition_id from bet, then from market cache
                    if not condition_id:
                        market = self.market_15m.market_cache.get(coin, {})
                        condition_id = market.get('conditionId') or market.get('condition_id')
                        if condition_id:
                            logger.info(f"{mode_label} [SETTLEMENT] Got condition_id from cache: {condition_id[:16]}...")

                    # Poll for official resolution via Gamma API + CLOB API
                    if condition_id:
                        actual = self.wait_for_market_resolution(condition_id, coin, max_wait=600)

                    # FALLBACK: Price comparison when API resolution fails
                    # For 15-min crypto markets, Chainlink oracle uses exchange prices
                    # so Binance final price vs strike is a reliable last resort
                    if not actual:
                        start_p = start_prices.get(coin) or bet.get('start_price', 0)
                        if final_p and start_p and final_p > 0 and start_p > 0:
                            actual = "UP" if final_p >= start_p else "DOWN"
                            logger.warning(f"{mode_label} [SETTLEMENT] ⚠ Using PRICE FALLBACK for {coin}: "
                                           f"final=${final_p:.2f} vs strike=${start_p:.2f} → {actual}")
                            logger.warning(f"{mode_label} [SETTLEMENT] API resolution failed - price comparison used as last resort")
                        else:
                            logger.error(f"{mode_label} [SETTLEMENT] ✗ No resolution AND no price data for {coin}")

                    # If still no official resolution, record as unresolved (don't silently drop)
                    if not actual:
                        logger.error(f"{mode_label} [SETTLEMENT] ✗✗✗ UNRESOLVED {coin} - no official resolution available")
                        logger.error(f"{mode_label} [SETTLEMENT] Recording as UNRESOLVED - will NOT train ML on this")

                        # Clear virtual position if in learning mode (to avoid orphaned active orders)
                        if self.learning_mode and self.learning_simulator:
                            order_id = bet.get('order_id')
                            if order_id:
                                self.learning_simulator.cancel_position(order_id, reason="no official resolution")
                                logger.info(f"{mode_label} [SETTLEMENT] Cancelled virtual position for {coin}")
                        else:
                            # REAL MODE: Record unresolved trade so there's an audit trail
                            # Money was spent but outcome unknown - must be tracked
                            # Use upsert pattern to update stub record if it exists
                            try:
                                order_id = bet.get('order_id')
                                unresolved_data = {
                                    'won': None,
                                    'final_price': final_p,
                                    'profit': 0,
                                    'status': 'UNRESOLVED',
                                    'settled_at': datetime.now().isoformat(),
                                    'note': 'No official resolution available - needs manual review'
                                }
                                with self.order_tracker.history._lock:
                                    found = False
                                    if order_id:
                                        for i, t in enumerate(self.order_tracker.history.history):
                                            if t.get('order_id') == order_id:
                                                self.order_tracker.history.history[i].update(unresolved_data)
                                                found = True
                                                break
                                    if not found:
                                        full_record = {**bet, **unresolved_data,
                                                       'timestamp': datetime.now().isoformat()}
                                        self.order_tracker.history.history.append(full_record)
                                    self.order_tracker.history._save_to_disk()
                                logger.warning(f"{mode_label} [SETTLEMENT] Unresolved trade recorded to history for audit: {coin}")
                            except Exception as e:
                                logger.error(f"{mode_label} [SETTLEMENT] Failed to record unresolved trade: {e}")

                        # Clear from real mode tracker if applicable
                        order_id = bet.get('order_id')
                        if order_id and hasattr(self, 'order_tracker'):
                            with self.order_tracker._lock:
                                self.order_tracker.active_orders.pop(order_id, None)
                            logger.info(f"{mode_label} [SETTLEMENT] Removed unresolved order from tracker: {order_id[:16]}...")

                        continue

                    # Store official outcome for phantom tracking
                    all_outcomes[coin] = actual
                    logger.info(f"{mode_label} [SETTLEMENT] ✓ Official outcome for {coin}: {actual}")

                    # Learning Mode: Settle virtual positions
                    if self.learning_mode and self.learning_simulator:
                        logger.info(f"[LEARNING] Taking LEARNING MODE settlement path")
                        order_id = bet.get('order_id')
                        if order_id:
                            # Settle simulated position using OFFICIAL CLOB outcome
                            trade_record = self.learning_simulator.settle_position(
                                order_id=order_id,
                                final_price=final_p,
                                start_price=bet['start_price'],
                                official_outcome=actual  # CRITICAL: Use official CLOB resolution
                            )

                            # THREAD-SAFE: Save to learning trades using atomic writes
                            if trade_record:
                                try:
                                    from .core.persistence import atomic_json_write, safe_json_load

                                    filepath = 'data/learning_trades.json'
                                    existing_trades = safe_json_load(filepath, default=[])
                                    existing_trades.append(trade_record)
                                    atomic_json_write(filepath, existing_trades)

                                    logger.info(f"[LEARNING] ✓ Virtual trade saved! Total: {len(existing_trades)}")

                                    # Record to Time-Decay analytics if in Time-Decay mode
                                    # Skip Low-Vol Lotto trades: different strategy would contaminate TD stats
                                    if self.time_decay_sniper_mode and hasattr(self, 'time_decay_analytics') and not bet.get('is_low_vol_lotto'):
                                        try:
                                            td_meta = bet.get('td_metadata', {})
                                            analytics_data = {
                                                'coin': trade_record.get('coin'),
                                                'token_price': trade_record.get('price', 0.75),  # Token price bought
                                                'bs_edge': trade_record.get('arb_edge', 0.0),  # BS edge
                                                'won': trade_record.get('won', False),
                                                'timestamp': trade_record.get('timestamp', datetime.now().isoformat()),
                                                'time_remaining': td_meta.get('time_remaining', 300)  # Entry time for window optimization
                                            }
                                            self.time_decay_analytics.record_trade(analytics_data)
                                            logger.info(f"[LEARNING] ✓ Recorded to Time-Decay analytics")
                                        except Exception as analytics_error:
                                            logger.error(f"[LEARNING] Failed to record analytics: {analytics_error}")
                                    elif bet.get('is_low_vol_lotto'):
                                        logger.info(f"[LEARNING] Skipped TD analytics for Low-Vol Lotto trade (separate strategy)")

                                    # Record to Time-Decay calibrator for ML training if in Time-Decay mode
                                    # Skip Low-Vol Lotto trades: different strategy would contaminate calibrator model
                                    if self.time_decay_sniper_mode and hasattr(self, 'time_decay_calibrator') and not bet.get('is_low_vol_lotto'):
                                        try:
                                            # Reconstruct calibrator training data from trade_record and bet metadata
                                            td_meta = bet.get('td_metadata', {})

                                            calibrator_data = {
                                                'coin': trade_record.get('coin'),
                                                'bs_probability': td_meta.get('bs_probability', trade_record.get('price', 0.75) + trade_record.get('arb_edge', 0.0)),
                                                'market_price': td_meta.get('market_price', trade_record.get('price', 0.75)),
                                                'bs_edge': trade_record.get('arb_edge', 0.0),
                                                'token_price': trade_record.get('price', 0.75),
                                                'time_remaining': td_meta.get('time_remaining', 300),
                                                'price_distance_pct': td_meta.get('price_distance_pct', 0.01),
                                                'volatility_realized': td_meta.get('volatility_realized', 0.8),
                                                'volatility_assumed': td_meta.get('volatility_assumed', 0.8),
                                                'orderbook_imbalance': td_meta.get('orderbook_imbalance', 0.0),
                                                'vwap_deviation_pct': td_meta.get('vwap_deviation_pct', 0.0),
                                                'price_above_vwap': td_meta.get('price_above_vwap', 0.5),
                                                'vwap_trend': td_meta.get('vwap_trend', 0.0),
                                                # NEW: Dynamic Entry Window features for ML learning
                                                'entry_timing_ratio': td_meta.get('entry_timing_ratio', td_meta.get('time_remaining', 300) / 900.0),
                                                'dynamic_window_norm': td_meta.get('dynamic_window_used', 300) / 900.0,
                                                'edge_at_entry': td_meta.get('edge_at_entry', abs(trade_record.get('arb_edge', 0.05))),
                                                'won': trade_record.get('won', False)
                                            }

                                            self.time_decay_calibrator.add_trade(calibrator_data)
                                            logger.info(f"[LEARNING] ✓ Recorded to Time-Decay calibrator (entry_timing={calibrator_data['entry_timing_ratio']:.2f}, edge={calibrator_data['edge_at_entry']*100:.1f}%)")
                                        except Exception as calibrator_error:
                                            logger.error(f"[LEARNING] Failed to record to calibrator: {calibrator_error}")
                                    elif bet.get('is_low_vol_lotto'):
                                        logger.info(f"[LEARNING] Skipped TD calibrator for Low-Vol Lotto trade (separate strategy)")

                                except Exception as e:
                                    logger.error(f"[LEARNING] Failed to save virtual trade: {e}")

                                # Update learning state
                                simulator_stats = self.learning_simulator.get_stats()
                                self.learning_persistence.save_state(simulator_stats)

                                # Train ML on virtual outcome (non-fatal if fails)
                                won = trade_record['won']
                                try:
                                    # CRITICAL: Validate actual outcome exists before ML training
                                    if actual:
                                        self.learning_engine.finalize_round(coin, actual)
                                    else:
                                        logger.error(f"[LEARNING] Cannot train ML: actual outcome is None for {coin}")
                                        logger.error(f"[LEARNING] Trade saved but ML training skipped")
                                except Exception as ml_error:
                                    logger.error(f"[LEARNING] ML training failed (non-fatal): {ml_error}")
                                    logger.error(f"[LEARNING] Trade will still be saved")

                                # Progressive betting: process win/loss via TradingStrategy
                                pnl = trade_record.get('profit', 0.0)
                                if won:
                                    self.strategy.process_win(pnl)
                                    logger.info(f"[LEARNING] Win processed - New bet size: ${self.strategy.get_current_bet():.2f} (+10%)")
                                else:
                                    self.strategy.process_loss(pnl)
                                    logger.info(f"[LEARNING] Loss processed - Bet reset to: ${self.strategy.get_current_bet():.2f} (base)")

                    else:
                        # Real Mode: Normal settlement
                        logger.info(f"[REAL] Taking REAL MODE settlement path")
                        logger.info(f"[REAL] Step 1: Determine outcome - bet prediction={bet.get('prediction')}, actual={actual}")

                        # CRITICAL: Validate actual outcome before using it
                        if not actual:
                            logger.error(f"[REAL] CRITICAL: actual outcome is None for {coin}")
                            logger.error(f"[REAL] Cannot determine win/loss or train ML - skipping this bet")
                            continue

                        won = (bet['prediction'] == actual)
                        logger.info(f"[REAL] Step 2: Won = {won}")

                        # Train ML (non-fatal if fails - trade must be saved regardless)
                        try:
                            logger.info(f"[REAL] Step 3: Starting ML training via finalize_round()")
                            self.learning_engine.finalize_round(coin, actual)
                            logger.info(f"[REAL] Step 4: ML training completed successfully")
                        except Exception as ml_error:
                            logger.error(f"[REAL] ML training failed (non-fatal): {ml_error}")
                            logger.error(f"[REAL] Continuing to save trade anyway...")

                        # Calculate profit/loss
                        # Win: shares are worth $1 each, so profit = shares - cost
                        # Loss: lost the entire cost
                        shares_val = bet.get('shares') or 0
                        cost_val = bet.get('cost') or 0
                        logger.info(f"[REAL] Step 5: Calculating P&L - shares={shares_val}, cost={cost_val}")
                        if won:
                            profit = shares_val - cost_val
                        else:
                            profit = -cost_val
                        logger.info(f"[REAL] Step 6: Calculated profit = {profit}")

                        # Progressive betting: process win/loss via TradingStrategy
                        logger.info(f"[REAL] Step 7: Processing win/loss for progressive betting")
                        if won:
                            self.strategy.process_win(profit)
                            logger.info(f"[REAL] Win processed - New bet size: ${self.strategy.get_current_bet():.2f} (+10%)")
                        else:
                            self.strategy.process_loss(profit)
                            logger.info(f"[REAL] Loss processed - Bet reset to: ${self.strategy.get_current_bet():.2f} (base)")

                        # Save trade with complete information — upsert pattern:
                        # If a record already exists for this order_id, update it in-place.
                        # Otherwise create a full record.
                        logger.info(f"[REAL] Step 8: Settling trade record")
                        try:
                            self.order_tracker.settle_and_save_trade(bet, final_p, won, profit)

                            logger.info(f"[SETTLEMENT] ✓ Trade saved: {coin} {'WON' if won else 'LOST'} ${profit:+.2f}")

                            # Record to Time-Decay analytics if in Time-Decay mode
                            # Skip Low-Vol Lotto trades: different strategy would contaminate TD stats
                            if self.time_decay_sniper_mode and hasattr(self, 'time_decay_analytics') and not bet.get('is_low_vol_lotto'):
                                try:
                                    td_meta = bet.get('td_metadata', {})
                                    analytics_data = {
                                        'coin': bet.get('coin'),
                                        'token_price': bet.get('price', 0.75),
                                        'bs_edge': bet.get('arb_edge', 0.0),
                                        'won': won,
                                        'timestamp': bet.get('timestamp', datetime.now().isoformat()),
                                        'time_remaining': td_meta.get('time_remaining', 300)
                                    }
                                    self.time_decay_analytics.record_trade(analytics_data)
                                    logger.info(f"[SETTLEMENT] ✓ Recorded to Time-Decay analytics")
                                except Exception as analytics_error:
                                    logger.error(f"[SETTLEMENT] Failed to record analytics: {analytics_error}")
                            elif bet.get('is_low_vol_lotto'):
                                logger.info(f"[SETTLEMENT] Skipped TD analytics for Low-Vol Lotto trade (separate strategy)")

                            # Record to Time-Decay calibrator for ML training if in Time-Decay mode
                            # Skip Low-Vol Lotto trades: different strategy would contaminate calibrator model
                            if self.time_decay_sniper_mode and hasattr(self, 'time_decay_calibrator') and not bet.get('is_low_vol_lotto'):
                                try:
                                    td_meta = bet.get('td_metadata', {})

                                    calibrator_data = {
                                        'coin': bet.get('coin'),
                                        'bs_probability': td_meta.get('bs_probability', bet.get('price', 0.75) + bet.get('arb_edge', 0.0)),
                                        'market_price': td_meta.get('market_price', bet.get('price', 0.75)),
                                        'bs_edge': bet.get('arb_edge', 0.0),
                                        'token_price': bet.get('price', 0.75),
                                        'time_remaining': td_meta.get('time_remaining', 300),
                                        'price_distance_pct': td_meta.get('price_distance_pct', 0.01),
                                        'volatility_realized': td_meta.get('volatility_realized', 0.8),
                                        'volatility_assumed': td_meta.get('volatility_assumed', 0.8),
                                        'orderbook_imbalance': td_meta.get('orderbook_imbalance', 0.0),
                                        'vwap_deviation_pct': td_meta.get('vwap_deviation_pct', 0.0),
                                        'price_above_vwap': td_meta.get('price_above_vwap', 0.5),
                                        'vwap_trend': td_meta.get('vwap_trend', 0.0),
                                        'entry_timing_ratio': td_meta.get('entry_timing_ratio', td_meta.get('time_remaining', 300) / 900.0),
                                        'dynamic_window_norm': td_meta.get('dynamic_window_used', 300) / 900.0,
                                        'edge_at_entry': td_meta.get('edge_at_entry', abs(bet.get('arb_edge', 0.05))),
                                        'won': won
                                    }

                                    self.time_decay_calibrator.add_trade(calibrator_data)
                                    logger.info(f"[SETTLEMENT] ✓ Recorded to Time-Decay calibrator (entry_timing={calibrator_data['entry_timing_ratio']:.2f}, edge={calibrator_data['edge_at_entry']*100:.1f}%)")
                                except Exception as calibrator_error:
                                    logger.error(f"[SETTLEMENT] Failed to record to calibrator: {calibrator_error}")
                            elif bet.get('is_low_vol_lotto'):
                                logger.info(f"[SETTLEMENT] Skipped TD calibrator for Low-Vol Lotto trade (separate strategy)")

                        except Exception as save_error:
                            logger.error(f"[SETTLEMENT] CRITICAL: Failed to save trade: {save_error}")
                            logger.error(f"[SETTLEMENT] bet = {bet}")
                            import traceback
                            traceback.print_exc()

                        # Remove settled order from active tracking
                        order_id = bet.get('order_id')
                        if order_id:
                            with self.order_tracker._lock:
                                self.order_tracker.active_orders.pop(order_id, None)

                        # Learn from position for profit-taking (Week 4)
                        if self.profit_taking_enabled and self.profit_taking_engine:
                            # Find and close position in tracker
                            active_positions = self.position_tracker.get_active_positions()
                            for position in active_positions:
                                if position['coin'] == coin:
                                    # Close position with final price
                                    completed_position = self.position_tracker.close_position(
                                        position['position_id'],
                                        exit_price=1.0 if won else 0.0,  # Binary outcome
                                        exit_type='expiry'
                                    )

                                    # Learn from this position
                                    if completed_position:
                                        self.profit_taking_engine.learn_from_position(completed_position)

                except Exception as bet_error:
                    logger.error(f"[SETTLEMENT] ✗✗✗ ERROR processing bet for {bet.get('coin', 'UNKNOWN')}: {bet_error}")
                    import traceback
                    logger.error(traceback.format_exc())

                    # RECOVERY: Try on-chain resolution so ML can still learn
                    error_order_id = bet.get('order_id')
                    error_condition_id = bet.get('condition_id')
                    recovered = False

                    if error_condition_id:
                        try:
                            # On-chain is source of truth — poll every 180s until resolved
                            logger.info(f"[SETTLEMENT] Attempting on-chain recovery for {bet.get('coin')}...")
                            onchain_outcome = None
                            for attempt in range(20):  # Up to 60 minutes (20 * 180s)
                                onchain_outcome = self.market_15m.check_onchain_resolution(error_condition_id)
                                if onchain_outcome:
                                    break
                                logger.info(f"[SETTLEMENT] On-chain recovery attempt {attempt+1}: not resolved yet, waiting 180s...")
                                time.sleep(180)

                            if onchain_outcome:
                                logger.info(f"[SETTLEMENT] ✓ ON-CHAIN RECOVERY: {bet.get('coin')} → {onchain_outcome}")
                                coin_name = bet.get('coin', 'UNKNOWN')
                                final_p = 0
                                try:
                                    final_p = self.fetch_current_price(coin_name)
                                except Exception:
                                    pass  # Non-critical for settlement

                                if self.learning_mode and self.learning_simulator and error_order_id:
                                    trade_record = self.learning_simulator.settle_position(
                                        order_id=error_order_id,
                                        final_price=final_p,
                                        start_price=bet.get('start_price', 0),
                                        official_outcome=onchain_outcome
                                    )
                                    if trade_record:
                                        from .core.persistence import atomic_json_write, safe_json_load
                                        filepath = 'data/learning_trades.json'
                                        existing = safe_json_load(filepath, default=[])
                                        existing.append(trade_record)
                                        atomic_json_write(filepath, existing)
                                        logger.info(f"[SETTLEMENT] ✓ Recovery trade saved for ML training")
                                        recovered = True
                                elif not self.learning_mode:
                                    # Real mode: settle via normal path
                                    actual = onchain_outcome
                                    won = (bet.get('prediction') == actual)
                                    shares_val = bet.get('shares') or 0
                                    cost_val = bet.get('cost') or 0
                                    profit = (shares_val - cost_val) if won else -cost_val
                                    try:
                                        self.order_tracker.settle_and_save_trade(bet, final_p, won, profit)
                                        logger.info(f"[SETTLEMENT] ✓ Real trade recovered via on-chain: {'WON' if won else 'LOST'} ${profit:+.2f}")
                                        recovered = True
                                    except Exception as save_err:
                                        logger.error(f"[SETTLEMENT] Failed to save recovered trade: {save_err}")

                        except Exception as recovery_error:
                            logger.error(f"[SETTLEMENT] On-chain recovery failed: {recovery_error}")

                    # Last resort: cancel virtual position to recover balance
                    if not recovered and self.learning_mode and self.learning_simulator and error_order_id:
                        self.learning_simulator.cancel_position(error_order_id, reason=f"all recovery failed: {bet_error}")

                    logger.error(f"[SETTLEMENT] Continuing to next bet...")
                    continue

            # Wallet sync EVERY round — settles new trades, discovers missing, repairs predictions
            try:
                proxy_addr = getattr(self.polymarket, 'funder_address', None)
                if proxy_addr:
                    sync_result = self.order_tracker.sync_trades_from_wallet(proxy_addr)
                    if sync_result['settled'] > 0:
                        logger.info(f"{mode_label} [SETTLEMENT] Wallet sync settled {sync_result['settled']} trade(s)")
                    if sync_result['discovered'] > 0:
                        logger.info(f"{mode_label} [SETTLEMENT] Wallet sync discovered {sync_result['discovered']} trade(s)")

                    # Feed newly settled trades to ML pipelines
                    if sync_result['settled'] > 0 or sync_result['discovered'] > 0:
                        # Reload history to pick up wallet-sync updates
                        with self.history_manager._lock:
                            self.history_manager.history = self.history_manager._load_history()

                        # ML backfill: label episode observations from newly settled trades
                        if hasattr(self, 'learning_engine') and self.learning_engine:
                            n = self.learning_engine.backfill_from_trade_history(self.history_manager.history)
                            if n > 0:
                                logger.info(f"{mode_label} [SETTLEMENT] ML backfill: {n} observations labeled from wallet sync")
            except Exception as e:
                logger.debug(f"Post-settlement wallet sync failed (non-fatal): {e}")

            # PASSIVE LEARNING: Track outcomes for ALL coins (even those without bets)
            # This allows ML to learn from observations even when not trading
            logger.info(f"{mode_label} [PASSIVE] Checking outcomes for all coins (including non-bet coins)...")

            coins_with_bets = {bet['coin'] for bet in placed_bets}
            passive_learning_coins = [coin for coin in self.active_coins if coin not in coins_with_bets]

            # Note: all_outcomes already contains outcomes for coins with bets (from settlement loop above)
            # Passive learning will add outcomes for coins WITHOUT bets to the same dictionary

            if passive_learning_coins:
                logger.info(f"{mode_label} [PASSIVE] Found {len(passive_learning_coins)} coins without bets: {passive_learning_coins}")
                logger.info(f"{mode_label} [PASSIVE] start_prices received: {start_prices}")

                for coin in passive_learning_coins:
                    try:
                        # Get OFFICIAL market outcome via CLOB API (NOT price comparison!)
                        market = self.market_15m.market_cache.get(coin, {})
                        condition_id = market.get('conditionId') or market.get('condition_id')

                        if condition_id:
                            logger.info(f"{mode_label} [PASSIVE] {coin}: Polling for official resolution...")
                            actual = self.wait_for_market_resolution(condition_id, coin, max_wait=600)

                            if actual:
                                all_outcomes[coin] = actual

                                # Train ML on this observation (even though no bet was placed)
                                # The episode buffer was filled during the round - now label it
                                try:
                                    self.learning_engine.finalize_round(coin, actual)
                                    logger.info(f"{mode_label} [PASSIVE] ✓ ML trained on {coin} OFFICIAL outcome: {actual} (no bet placed)")
                                except Exception as ml_error:
                                    logger.warning(f"{mode_label} [PASSIVE] ML training failed for {coin}: {ml_error}")
                            else:
                                logger.warning(f"{mode_label} [PASSIVE] ✗ Could not get official outcome for {coin} - skipping ML training")
                        else:
                            logger.warning(f"{mode_label} [PASSIVE] No condition_id for {coin} - cannot get official outcome")
                    except Exception as passive_error:
                        logger.warning(f"{mode_label} [PASSIVE] Error processing {coin}: {passive_error}")
                        import traceback
                        logger.warning(f"{mode_label} [PASSIVE] Traceback: {traceback.format_exc()}")

            else:
                logger.info(f"{mode_label} [PASSIVE] All active coins had bets placed (no passive learning needed)")

            # PHANTOM TRADE TRACKING: Record what would have happened for rejected opportunities
            # Note: Outcomes for coins with bets are collected during settlement loop above
            # and stored in all_outcomes via the passive learning section

            if all_outcomes and hasattr(self, 'phantom_tracker'):
                self.phantom_tracker.finalize_round(all_outcomes)
                logger.info(f"{mode_label} [PHANTOM] Finalized phantom trades for {len(all_outcomes)} coins")

            self.last_action_msg = "Round settled (Virtual)" if self.learning_mode else "Round settled."
        except Exception as e:
            logger.error(f"Settlement error: {e}")
            logger.error(f"Failed to settle {len(placed_bets)} orders")

            # Log which orders failed
            for bet in placed_bets:
                logger.error(f"  - {bet.get('coin')} {bet.get('prediction')} ${bet.get('cost', 0):.2f}")

            # Don't pass silently - let monitoring know
            traceback.print_exc()

    def calculate_bs_minimum_window(self, coin, strike_price, current_spot,
                                     edge_threshold=0.15, max_window=600):
        """
        Calculate minimum viable entry window using Black-Scholes.

        Finds earliest time (largest time_remaining) where BS edge exceeds threshold.

        Args:
            coin: BTC/ETH/SOL
            strike_price: Market open price
            current_spot: Current asset price
            edge_threshold: Minimum BS edge required (default 15%)
            max_window: Maximum window to check (default 600s = 10 min)

        Returns:
            Minimum window in seconds (earliest safe entry point)
        """
        vol = self.arbitrage_detector.volatility.get(coin, 0.8)
        price_distance_pct = abs(current_spot - strike_price) / max(strike_price, 1.0)
        direction = 'UP' if current_spot > strike_price else 'DOWN'

        # Simulate decreasing time windows (from max to 1 second)
        for t_remaining in range(max_window, 0, -10):  # Check every 10 seconds
            # Calculate BS probability at this time
            try:
                from scipy.stats import norm
                import math

                # Time in years
                t_years = t_remaining / (365.25 * 24 * 3600)

                if t_years <= 0:
                    continue

                # BS formula for binary option
                d1 = (math.log(current_spot / strike_price) + (0.5 * vol**2) * t_years) / (vol * math.sqrt(t_years))
                bs_prob = norm.cdf(d1) if direction == 'UP' else norm.cdf(-d1)

                # Estimate market price (would need real orderbook, but estimate based on movement)
                # Assuming market prices roughly halfway between strike and current
                estimated_market_prob = 0.5 + (price_distance_pct * 2 if direction == 'UP' else -price_distance_pct * 2)
                estimated_market_prob = max(0.01, min(0.99, estimated_market_prob))

                bs_edge = bs_prob - estimated_market_prob

                # Check if this window meets threshold
                if bs_edge >= edge_threshold:
                    # Found earliest viable window
                    return t_remaining

            except Exception as e:
                continue

        # If no window found, return conservative 60s
        return 60

    def get_dynamic_entry_window(self):
        """
        Calculate optimal entry window using hybrid BS + ML approach.

        Combines:
        1. BS-calculated minimum viable window (mathematical certainty)
        2. ML-learned optimal window (historical performance)

        Returns:
            Optimal window in seconds
        """
        # Default window should match SNIPE state trigger (420s = 7 min)
        # This ensures opportunities are evaluated as soon as SNIPE state begins
        default_window = 420  # 7 minutes (matches SNIPE trigger)

        # Try to get ML-learned optimal window
        if hasattr(self, 'time_decay_analytics'):
            try:
                ml_optimal = self.time_decay_analytics.get_optimal_entry_window(
                    min_trades=5,  # Require 5+ trades per window
                    default_window=default_window
                )

                # Use ML window if we have enough data
                total_trades = self.time_decay_analytics.get_bs_accuracy_stats()['total_trades']
                if total_trades >= 20:  # Require 20+ total trades for ML confidence
                    td_logger.info(f"[WINDOW] Using ML-learned optimal window: {ml_optimal}s ({total_trades} trades)")
                    return ml_optimal

            except Exception as e:
                td_logger.warning(f"[WINDOW] ML window calculation failed: {e}")

        # Not enough ML data, use default
        td_logger.debug(f"[WINDOW] Using default window: {default_window}s (insufficient ML data)")
        return default_window

    def _compute_realized_volatility(self):
        """Compute realized volatility from recent 1m candles (Binance).

        Uses a 30-minute window of 1m candles for fast regime detection:
        - Fetches 30 x 1m candles from Binance each round (3 API calls)
        - 29 log returns → annualized vol estimate
        - Detects vol regime changes within 2 rounds (30 min), always within 3
        - Falls back to 1h candles from historical DB if Binance fetch fails
        """
        for coin in self.active_coins:
            try:
                realized = None

                # Primary: 30 x 1m candles from Binance (fast-reacting, 30-min window)
                try:
                    candles_1m = self.exchange_data.fetch_historical_ohlcv(coin, '1m', limit=30)
                    if candles_1m and len(candles_1m) >= 10:
                        closes = [c[4] for c in candles_1m]  # close price is index 4
                        log_returns = np.diff(np.log(closes))
                        # Annualize: 1m std * sqrt(minutes_per_year)
                        realized = float(np.std(log_returns) * np.sqrt(525600))
                        logger.info(f"[VOL] {coin}: realized={realized:.3f} (from {len(closes)} x 1m candles)")
                except Exception as e:
                    logger.debug(f"[VOL] {coin}: 1m fetch failed ({e}), trying 1h fallback")

                # Fallback: 1h candles from historical DB (slower but always available)
                if realized is None:
                    closes = self.historical_data.get_recent_closes(coin, '1h', 24)
                    if len(closes) >= 6:
                        log_returns = np.diff(np.log(closes))
                        realized = float(np.std(log_returns) * np.sqrt(24 * 365))
                        logger.info(f"[VOL] {coin}: realized={realized:.3f} (fallback: {len(closes)} x 1h candles)")

                if realized is not None:
                    self.arbitrage_detector.update_realized_volatility(coin, realized)
                    assumed = self.arbitrage_detector.volatility.get(coin, 0.8)
                    ratio = assumed / max(realized, 0.01)
                    logger.info(f"[VOL] {coin}: assumed={assumed:.2f}, ratio={ratio:.2f}")
                else:
                    logger.debug(f"[VOL] {coin}: No data available, using assumed vol")
            except Exception as e:
                logger.warning(f"[VOL] {coin}: Failed to compute realized vol: {e}")

    def is_time_decay_opportunity(self, coin, polymarket_price, strike_price,
                                   time_remaining, current_spot, direction='UP'):
        """
        Detect time-decay arbitrage opportunities (with DYNAMIC window).

        Criteria:
        1. Time remaining <= optimal window (ML-learned or default 420s = 7 min)
        2. Token price 75-85¢ (high conviction zone, 15-25¢ upside)
        3. Black-Scholes edge >= 15% (mathematical certainty)
        4. Price moved >0.5% from strike (clear direction)

        Args:
            direction: 'UP' for YES token, 'DOWN' for NO token
                       This affects edge calculation (YES uses fair_prob, NO uses 1-fair_prob)

        Returns:
            dict: {'opportunity': bool, 'edge': float, 'reasoning': str}
        """
        reasons = []

        # Get optimal entry window (dynamic based on ML learning)
        optimal_window = self.get_dynamic_entry_window()

        # Must be within optimal entry window
        if time_remaining > optimal_window:
            reasons.append(f"Outside optimal window (need ≤{optimal_window}s, have {time_remaining:.0f}s)")
            return {'opportunity': False, 'edge': 0.0, 'reasoning': '; '.join(reasons)}

        # Token price must be in sweet spot (75-85¢)
        # Focused range: high conviction zone with 15-25¢ upside to settlement
        if polymarket_price < 0.75:
            reasons.append(f"Price too low (need ≥75¢, have {polymarket_price*100:.0f}¢)")
            return {'opportunity': False, 'edge': 0.0, 'reasoning': '; '.join(reasons)}

        if polymarket_price > 0.85:
            reasons.append(f"Price too high (need ≤85¢, have {polymarket_price*100:.0f}¢)")
            return {'opportunity': False, 'edge': 0.0, 'reasoning': '; '.join(reasons)}

        # Calculate Black-Scholes fair value
        # fair_prob = P(spot > strike) = fair price of YES token
        fair_prob_yes = self.arbitrage_detector.calculate_fair_value(
            coin, strike_price, time_remaining
        )

        # Calculate edge based on which token we're buying
        # YES token: edge = fair_prob_YES - market_price
        # NO token: edge = (1 - fair_prob_YES) - market_price = fair_prob_NO - market_price
        if direction == 'UP':
            fair_prob = fair_prob_yes
            edge = fair_prob - polymarket_price
            token_type = 'YES'
        else:
            fair_prob = 1.0 - fair_prob_yes
            edge = fair_prob - polymarket_price
            token_type = 'NO'

        td_logger.debug(f"[TD] {coin} {token_type}: fair={fair_prob:.2%}, market={polymarket_price:.2%}, edge={edge:.2%}")

        # Require significant edge (mathematical certainty)
        if edge < 0.15:
            reasons.append(f"Edge too small (need ≥15%, have {edge*100:.1f}%) [{token_type} token]")
            return {'opportunity': False, 'edge': edge, 'reasoning': '; '.join(reasons)}

        # Vol-scaled distance guard (same formula as check_arbitrage)
        price_move_pct = abs(current_spot - strike_price) / strike_price
        vol_assumed_td = self.arbitrage_detector.volatility.get(coin, 0.8)
        vol_realized_td = self.arbitrage_detector.realized_volatility.get(coin, vol_assumed_td)
        vol_ratio_td = vol_assumed_td / max(vol_realized_td, 0.01)
        min_distance_td = 0.005 * vol_ratio_td

        if price_move_pct < min_distance_td:
            reasons.append(f"Price too close to strike (need >{min_distance_td*100:.2f}%, have {price_move_pct*100:.2f}%, vol_ratio={vol_ratio_td:.1f}x)")
            return {'opportunity': False, 'edge': edge, 'reasoning': '; '.join(reasons)}

        # ALL CRITERIA MET!
        reasoning = (f"✓ Time: {time_remaining:.0f}s | "
                    f"Price: {polymarket_price*100:.0f}¢ | "
                    f"Edge: {edge*100:.1f}% | "
                    f"Move: {price_move_pct*100:.2f}% from strike")

        td_logger.info(f"[OPPORTUNITY] {coin}: {reasoning}")
        return {'opportunity': True, 'edge': edge, 'reasoning': reasoning}

    def validate_trade(self, coin, price):
        # Time-Decay mode: Only allow 75-85¢ range (high conviction zone)
        if self.risk_profile == 'time_decay':
            if price < 0.75:
                logger.info(f"Skipped {coin}: Price {price:.2f} < 0.75 (Time-Decay requires 75-85¢)")
                return False
            if price > 0.85:
                logger.info(f"Skipped {coin}: Price {price:.2f} > 0.85 (Time-Decay requires 75-85¢)")
                return False

        # Standard risk profiles
        if self.risk_profile == 'low' and price > 0.25:
            logger.info(f"Skipped {coin}: Price {price:.2f} > 0.25 (Low Risk / Lotto)")
            return False
        if self.risk_profile == 'high' and price < 0.60:
            logger.info(f"Skipped {coin}: Price {price:.2f} < 0.60 (High Risk)")
            return False

        # Polymarket minimum order size is $1.00 USD (not share-based)
        # See: examples/Polymarket documentation/py-clob-client-main/
        min_cost = 1.0  # Hard $1.00 USD minimum per order

        # Log minimum requirements
        logger.info(f"{coin} Min Order: ${min_cost:.2f} USD minimum (Polymarket floor)")

        if min_cost > self.user_max_bet:
            logger.warning(f"Skipped {coin}: Min cost ${min_cost:.2f} > Max Bet ${self.user_max_bet:.2f}")
            return False
        if min_cost > self.balance:
            logger.warning(f"Skipped {coin}: Min cost ${min_cost:.2f} > Balance ${self.balance:.2f}")
            return False
        return True

    def _collect_data(self, coin, start_price, time_remaining):
        try:
            price = self.fetch_current_price(coin)
            self.mtf_analyzer[coin].add_tick(time.time(), price)
            # Compute arbitrage data so training features match prediction features
            pp = self.market_15m.get_current_price(coin) or 0.5
            arb = self.arbitrage_detector.check_arbitrage(coin, pp, start_price, time_remaining)
            features = self.extract_features(coin, start_price, {}, time_remaining, arbitrage_data=arb)
            self.learning_engine.add_observation(coin, features, time.time())

            # Feed VWAP calculator if Time-Decay mode
            if self.time_decay_sniper_mode and self.vwap_calculator:
                # Use volume=1.0 since we don't have real-time volume from Binance spot
                self.vwap_calculator.add_tick(coin, price, volume=1.0)
        except Exception: pass

    def extract_features(self, coin: str, start_price: float, orderbook: dict, time_remaining: float = 0, arbitrage_data: dict = None) -> np.ndarray:
        try:
            mtf_feats = self.mtf_analyzer[coin].get_trend_features()
            # Use 1m candles for TA-Lib (accumulates ~15/round vs 15m which gets 0-1/round)
            data_1m = self.mtf_analyzer[coin].get_timeframe_data('1m')

            # Fetch Bot Stats
            stats = self.history_manager.get_stats()
            bot_stats = {
                'win_rate': stats.get('win_rate', 0.5),
                'streak': stats.get('current_streak', 0)
            }

            # Fetch Market Stats
            market_data = self.market_15m.market_cache.get(coin, {})
            market_stats = {
                'volume': market_data.get('volume', 0)
            }

            # Create DataFrame with explicit float64 dtypes for TA-Lib compatibility
            # Threshold 5: TA-Lib returns NaN for warm-up candles, safe_get() handles defaults
            if len(data_1m) >= 5:
                df = pd.DataFrame(data_1m)
                # Force all numeric columns to float64 to prevent TA-Lib errors
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').astype(np.float64)
                base_feats = self.feature_extractor.extract_features(df, mtf_feats)
            else:
                base_feats = np.zeros(70)  # 42 MTF + 10 indicators + 6 cross-market + 4 BB + 6 extra + 2 candle

            bin_feats = self.exchange_data.get_features(coin)

            return self.feature_extractor.append_microstructure_features(
                base_feats,
                self.fetch_current_price(coin),
                start_price,
                orderbook,
                bin_feats,
                time_remaining,
                bot_stats=bot_stats,
                market_stats=market_stats,
                arbitrage_data=arbitrage_data
            )
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            # Ensure return size matches new feature count (61 + 21 VWAP + 4 arbitrage = 86)
            return np.zeros(86)

    def _get_effective_budgets(self, remaining_budget):
        """
        Calculate effective trading budgets per coin.
        Regime detection retired - all coins get full budget.

        Returns dict: {coin: {'amount': float, 'multiplier': float}}
        """
        effective_budgets = {}

        for coin in ['BTC', 'ETH', 'SOL']:
            # No regime multipliers - full budget for all coins
            effective_budgets[coin] = {
                'amount': remaining_budget,
                'multiplier': 1.0
            }

        return effective_budgets

    def smart_coin_selection(self, remaining):
        """
        SMART COIN SELECTION - Respects minimum order sizes and budget constraints

        Algorithm:
        1. Collect all coin opportunities with ML confidence + arbitrage edge
        2. Apply Polymarket's $1.00 USD minimum order requirement
        3. Filter coins where min_cost <= remaining_budget
        4. Rank by winning probability (ML + arbitrage combined)
        5. Select best coin(s) that fit budget
        6. Skip round if no coins meet minimum requirements
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"SMART COIN SELECTION - Budget: ${self.user_max_bet:.2f}")
        logger.info(f"{'='*60}")

        # Calculate remaining budget
        remaining_budget = self.user_max_bet - self.round_budget_spent

        if remaining_budget < 0.1:
            logger.info("Round budget exhausted. Skipping coin selection.")
            return

        # Edge Cooldown: Skip trading if cooldown is active
        # Cooldown thresholds (8%/15%) are calibrated for Mode D's BS probability edge.
        # Mode A returns spot-vs-strike distance (~0.5%) which never reaches those
        # thresholds, so cooldown would permanently lock Mode A. Skip it.
        if self.edge_cooldown_enabled and self.cooldown_active and not self.pure_arbitrage_mode:
            logger.info(f"EDGE COOLDOWN ACTIVE - Skipping trading (signal rounds: {self.consecutive_signal_rounds}/{self.edge_cooldown_resume_after})")
            self.current_status = "Cooldown (Low Edge Regime)"
            return

        # Calculate effective budgets (regime detection retired - full budget for all)
        effective_budgets = self._get_effective_budgets(remaining_budget)

        # Step 1: Collect all opportunities
        opportunities = []

        for coin in self.active_coins:
            # Skip if already bet on this coin
            if coin in self.round_coins_bet:
                continue

            # Get effective budget for this coin
            effective = effective_budgets.get(coin, {'amount': remaining_budget, 'multiplier': 1.0})

            # Collect data for this coin
            self._collect_data(coin, self.start_prices.get(coin, 0), remaining)
            cp = self.fetch_current_price(coin)
            pp = self.market_15m.get_current_price(coin) or 0.5

            # Get strike price (continuous sync)
            official = self.market_15m.get_official_strike_price(coin)
            if official:
                self.start_prices[coin] = official
                self.strike_types[coin] = "OFFCL"

            # Check arbitrage opportunity
            if self.pure_arbitrage_mode:
                arb = self.arbitrage_detector.check_arbitrage(coin, pp, self.start_prices.get(coin, cp), remaining, market_15m=self.market_15m)
            else:
                arb = self.arbitrage_detector.check_arbitrage(coin, pp, self.start_prices.get(coin, cp), remaining)

            # FIX: Update predictions dict for dashboard (using EXISTING pattern from process_coin_sniping)
            # Safe handling of potentially None direction
            direction_display = arb.get('direction', '--') if arb else '--'

            # Compute display edge: for pure arbitrage, always show spot-vs-strike distance
            display_edge = arb.get('diff', 0.0) if arb else 0.0
            if self.pure_arbitrage_mode and display_edge == 0.0:
                strike = self.start_prices.get(coin, 0)
                if cp and cp > 0 and strike and strike > 0:
                    display_edge = ((cp - strike) / strike) * 100
                    if not direction_display or direction_display == '--':
                        direction_display = "UP" if display_edge > 0 else "DOWN" if display_edge < 0 else "--"

            self.predictions[coin] = {
                'direction': direction_display,
                'arb_opportunity': arb['opportunity'] if arb else False,
                'edge': display_edge,
                'time_left': remaining
            }

            # Edge Cooldown: Track only ACTIONABLE edges (inside dynamic window)
            # Skip for Mode A — its edge scale (spot distance %) doesn't match cooldown thresholds
            if self.edge_cooldown_enabled and not self.pure_arbitrage_mode and arb and arb.get('opportunity'):
                edge_val = abs(arb.get('diff', 0.0))
                self.round_edge_samples.append(edge_val)
                self.round_edge_per_coin.setdefault(coin, []).append(edge_val)

            # Check arbitrage opportunity OR high ML confidence for early betting
            has_arb_opportunity = arb and arb['opportunity']

            # CRITICAL: Validate direction exists before using it
            # If no direction (arb['direction'] is None), we can't determine which token to trade
            # EXCEPTION: Time-Decay mode determines direction from spot vs strike (not arbitrage window)
            if not arb or arb.get('direction') is None:
                if self.time_decay_sniper_mode:
                    # Time-Decay: Determine direction from price position relative to strike
                    strike = self.start_prices.get(coin, cp)
                    if cp > strike:
                        arb['direction'] = 'UP'  # Price above strike = YES likely
                        logger.info(f"{coin}: [TD] Direction=UP (spot ${cp:,.2f} > strike ${strike:,.2f})")
                    else:
                        arb['direction'] = 'DOWN'  # Price below strike = NO likely
                        logger.info(f"{coin}: [TD] Direction=DOWN (spot ${cp:,.2f} < strike ${strike:,.2f})")
                else:
                    logger.debug(f"{coin}: No arbitrage direction signal, skipping")
                    continue
            else:
                # Log when arb already has direction (from arbitrage window)
                logger.info(f"{coin}: [ARB] Direction={arb['direction']} from arbitrage detector")

            # CRITICAL FIX: Use same price source as CLI (get_both_prices)
            # This ensures all modes use correct, fresh Polymarket prices
            both_prices = self.market_15m.get_both_prices(coin)
            if not both_prices:
                logger.warning(f"{coin}: Could not fetch prices")
                continue

            # DEBUG: Log prices and market for diagnosis
            market = self.market_15m.market_cache.get(coin, {})
            market_end = market.get('endDate', 'unknown')
            logger.info(f"[PRICE DEBUG] {coin}: both_prices={both_prices}, direction={arb['direction']}, market_end={market_end}")

            # Get token IDs for order placement (still needed for actual trading)
            tokens = self.market_15m.get_token_ids_for_coin(coin)
            if not tokens:
                logger.warning(f"{coin}: Could not find token IDs")
                continue

            # Select correct token price based on direction (matches CLI logic)
            tid = tokens['yes'] if arb['direction'] == 'UP' else tokens['no']
            t_price = both_prices['yes'] if arb['direction'] == 'UP' else both_prices['no']

            # DEBUG: Log selected token
            token_type = 'YES' if arb['direction'] == 'UP' else 'NO'
            logger.info(f"[PRICE DEBUG] {coin}: Selected {token_type} token at {t_price*100:.0f}¢")

            # Polymarket minimum order is $1.00 USD
            min_cost = 1.0

            # Check against effective budget
            if min_cost > effective['amount']:
                logger.info(f"Skipped {coin}: Min ${min_cost:.2f} > Effective budget ${effective['amount']:.2f}")
                continue

            # Pure Arbitrage Mode: Skip ML entirely, use only arbitrage edge
            ml_confidence = 0.5  # Default neutral (not used in pure arb mode)
            allow_early_betting = False

            if self.pure_arbitrage_mode:
                # Pure arbitrage: No ML, no early betting, only mathematical edge
                if not has_arb_opportunity:
                    logger.info(f"{coin}: No arbitrage opportunity (Pure Arbitrage Mode)")
                    continue

                # Use arbitrage edge as sole signal (100% weight)
                arb_edge = abs(arb.get('diff', 0.0)) / 100.0  # Convert % to 0-1 scale (diff is already in %)
                combined_score = arb_edge
                logger.info(f"{coin}: Pure Arbitrage - Edge: {arb_edge:.2%}, Strategy: {arb.get('strategy', 'unknown')}")

            elif self.time_decay_sniper_mode:
                # Time-Decay Sniper: High-probability + time-decay mathematical certainty
                # Check if meets time-decay criteria
                td_check = self.is_time_decay_opportunity(
                    coin=coin,
                    polymarket_price=t_price,
                    strike_price=self.start_prices.get(coin, cp),
                    time_remaining=remaining,
                    current_spot=cp,
                    direction=arb['direction']  # Pass direction for correct edge calculation
                )

                if not td_check['opportunity']:
                    td_logger.warning(f"[REJECT] {coin}: {td_check['reasoning']}")

                    # PHANTOM TRACKING: Record rejected opportunity for ML learning
                    # This allows ML to learn whether lower thresholds could work
                    if hasattr(self, 'phantom_tracker'):
                        self.phantom_tracker.record_rejection(coin, {
                            'price': t_price,
                            'direction': arb['direction'],
                            'edge': td_check.get('edge', 0.0),
                            'bs_edge': td_check.get('edge', 0.0),
                            'time_remaining': remaining,
                            'strike_price': self.start_prices.get(coin, cp),
                            'spot_price': cp,
                            'rejection_reason': td_check['reasoning'],
                            'mode': 'time_decay'
                        })
                    continue

                # Use time-decay edge as primary signal (80%), optional ML confirmation (20%)
                td_edge = td_check['edge']

                # ALWAYS extract features (needed for ML training even if not calibrating yet)
                # Calculate price distance
                strike = self.start_prices.get(coin, cp)
                price_distance_pct = abs(cp - strike) / max(strike, 1.0)

                # Get orderbook for imbalance calculation
                tokens_for_ob = self.market_15m.get_token_ids_for_coin(coin)
                orderbook_for_ob = None
                if tokens_for_ob:
                    token_id_for_ob = tokens_for_ob['yes'] if arb['direction'] == 'UP' else tokens_for_ob['no']
                    orderbook_for_ob = self.market_15m.client.get_orderbook(token_id_for_ob)

                # Calculate orderbook imbalance (OrderBookSummary is a dataclass with .bids/.asks lists of OrderSummary)
                bids_list = (orderbook_for_ob.bids or []) if orderbook_for_ob else []
                asks_list = (orderbook_for_ob.asks or []) if orderbook_for_ob else []
                bid_vol = sum(float(b.size) for b in bids_list[:5])
                ask_vol = sum(float(a.size) for a in asks_list[:5])
                ob_imbalance = (bid_vol - ask_vol) / max(bid_vol + ask_vol, 1.0)

                # Get volatility parameters
                vol_assumed = self.arbitrage_detector.volatility.get(coin, 0.8)
                # Calculate realized volatility from recent price data
                vol_realized = vol_assumed  # fallback
                try:
                    if hasattr(self, 'multi_timeframe') and self.multi_timeframe:
                        tf_data = self.multi_timeframe.get_timeframe_data('1m', coin)
                        if tf_data is not None and len(tf_data) >= 10:
                            recent_closes = tf_data['close'].astype(float).values[-30:]
                            if len(recent_closes) >= 10:
                                log_returns = np.diff(np.log(recent_closes))
                                vol_realized = float(np.std(log_returns) * np.sqrt(60 * 24 * 365))  # Annualized
                except Exception:
                    pass  # Keep vol_assumed as fallback

                # Get VWAP features
                vwap_features = {'vwap_deviation_pct': 0.0, 'price_above_vwap': 0.5, 'vwap_trend': 0.0}
                if self.vwap_calculator:
                    vwap_features = self.vwap_calculator.get_vwap_features(coin, cp)
                    td_logger.debug(f"[VWAP] {coin}: VWAP=${vwap_features['vwap_price']:.2f}, "
                                  f"Dev={vwap_features['vwap_deviation_pct']*100:+.2f}%, "
                                  f"Above={vwap_features['price_above_vwap']:.0f}")

                # ML Calibration: Adjust BS edge based on learned patterns (only if already trained)
                if hasattr(self, 'time_decay_calibrator') and self.time_decay_calibrator.is_trained:
                    try:
                        # Calibrate edge using already-extracted features
                        calibration = self.time_decay_calibrator.calibrate_edge(
                            bs_probability=arb.get('fair_value', t_price + td_edge),
                            market_price=t_price,
                            token_price=t_price,
                            time_remaining=remaining,
                            price_distance_pct=price_distance_pct,
                            volatility_realized=vol_realized,
                            volatility_assumed=vol_assumed,
                            orderbook_imbalance=ob_imbalance,
                            vwap_deviation_pct=vwap_features['vwap_deviation_pct'],
                            price_above_vwap=vwap_features['price_above_vwap'],
                            vwap_trend=vwap_features['vwap_trend']
                        )

                        # Use calibrated edge if available
                        if calibration['calibrated_edge'] > 0:
                            td_edge_calibrated = calibration['calibrated_edge']
                            td_logger.info(f"[CALIBRATION] {coin}: BS {td_edge:.2%} → ML {td_edge_calibrated:.2%} "
                                         f"(adj: {calibration['adjustment_factor']:.2f}x, conf: {calibration['confidence']:.2f})")
                            td_edge = td_edge_calibrated
                        else:
                            td_logger.debug(f"[CALIBRATION] {coin}: Skipped - {calibration.get('note', 'unknown reason')}")
                    except Exception as e:
                        td_logger.warning(f"[CALIBRATION] {coin}: Failed - {e}")

                # Try to get standard ML confidence if available (secondary signal)
                ml_confidence = 0.5
                try:
                    tokens = self.market_15m.get_token_ids_for_coin(coin)
                    orderbook = None
                    if tokens:
                        token_id = tokens['yes'] if arb['direction'] == 'UP' else tokens['no']
                        orderbook = self.market_15m.client.get_orderbook(token_id)

                    start_price = self.start_prices.get(coin, 0)
                    features = self.extract_features(coin, start_price, orderbook, remaining, arbitrage_data=arb)
                    ml_pred = self.learning_engine.predict(coin, features)
                    if ml_pred is not None:
                        # predict() returns a single float: prob_up (0.0-1.0)
                        prob_up = float(ml_pred)
                        ml_confidence = prob_up if arb['direction'] == 'UP' else (1.0 - prob_up)
                except Exception as e:
                    logger.debug(f"{coin}: Standard ML unavailable in TD mode: {e}")

                # Combined score: 80% time-decay edge (calibrated), 20% ML confidence
                combined_score = 0.8 * td_edge + 0.2 * ml_confidence
                arb_edge = td_edge  # For logging

                td_logger.info(f"[SCORE] {coin}: TD Edge {td_edge:.2%} + ML {ml_confidence:.2%} = Combined {combined_score:.3f}")

            else:
                # Standard Mode: ML + Arbitrage hybrid
                try:
                    # Get token ID for direction to fetch orderbook
                    tokens = self.market_15m.get_token_ids_for_coin(coin)
                    orderbook = None
                    if tokens:
                        token_id = tokens['yes'] if arb['direction'] == 'UP' else tokens['no']
                        orderbook = self.market_15m.client.get_orderbook(token_id)

                    # Extract features with all required arguments (including arbitrage context)
                    start_price = self.start_prices.get(coin, 0)
                    features = self.extract_features(coin, start_price, orderbook, remaining, arbitrage_data=arb)
                    ml_pred = self.learning_engine.predict(coin, features)
                    if ml_pred is not None:
                        # predict() returns a single float: prob_up (0.0-1.0)
                        prob_up = float(ml_pred)
                        ml_confidence = prob_up if arb['direction'] == 'UP' else (1.0 - prob_up)
                except Exception as e:
                    logger.error(f"{coin}: ML prediction failed: {e}")

                # Early betting override: Allow trading without arbitrage if ML confidence is very high
                # This enables earlier entry (up to 10 minutes before close) when ML is confident
                if not has_arb_opportunity:
                    # Check for early betting conditions:
                    # 1. ML confidence > 0.75 (75% confident)
                    # 2. Time remaining <= 600 seconds (10 minutes)
                    # 3. ML prediction exists and has a clear direction
                    if ml_confidence > 0.75 and remaining <= 600 and arb and arb.get('direction'):
                        allow_early_betting = True
                        logger.info(f"{coin}: Early betting enabled - ML confidence {ml_confidence:.2%} "
                                  f"(time remaining: {remaining}s)")
                    else:
                        logger.info(f"{coin}: No arbitrage opportunity, ML confidence too low "
                                  f"({ml_confidence:.2%}) or too much time remaining ({remaining}s)")
                        continue

                # Calculate combined confidence score
                # Weight: 60% arbitrage edge, 40% ML confidence
                arb_edge_raw = abs(arb.get('diff', 0.0)) / 100.0  # Convert % to decimal (e.g., 5.0 → 0.05)
                # Normalize arb edge to 0-1 scale: 5% edge → 0.25, 10% → 0.50, 20%+ → 1.0
                arb_edge = min(arb_edge_raw / 0.20, 1.0)
                combined_score = (0.6 * arb_edge) + (0.4 * ml_confidence)

                # If early betting, use ML confidence as primary signal
                if allow_early_betting:
                    combined_score = ml_confidence

            # Check if coin meets risk profile
            if not self.validate_trade(coin, t_price):
                logger.info(f"{coin}: Failed risk validation")

                # PHANTOM TRACKING: Record rejected opportunity for ML learning (all modes)
                if hasattr(self, 'phantom_tracker'):
                    rejection_reason = f"Risk profile '{self.risk_profile}': price {t_price:.2f}"
                    if self.risk_profile == 'low' and t_price > 0.15:
                        rejection_reason = f"Price {t_price*100:.0f}¢ > 15¢ (Lotto mode)"
                    elif self.risk_profile == 'high' and t_price < 0.60:
                        rejection_reason = f"Price {t_price*100:.0f}¢ < 60¢ (High probability mode)"

                    self.phantom_tracker.record_rejection(coin, {
                        'price': t_price,
                        'direction': arb['direction'],
                        'edge': arb_edge,
                        'ml_confidence': ml_confidence,
                        'combined_score': combined_score,
                        'time_remaining': remaining,
                        'rejection_reason': rejection_reason,
                        'mode': self.risk_profile
                    })
                continue

            # Build opportunity dict
            opp_dict = {
                'coin': coin,
                'direction': arb['direction'],
                'price': t_price,
                'min_cost': min_cost,  # $1.00 USD minimum
                'arb_edge': arb_edge,
                'ml_confidence': ml_confidence,
                'combined_score': combined_score,
                'token_id': tid
            }

            # Store Time-Decay metadata for ML training (if TD mode)
            # In Time-Decay mode, all these variables are guaranteed to be defined above
            if self.time_decay_sniper_mode:
                opp_dict['td_metadata'] = {
                    'bs_probability': arb.get('fair_value', t_price + arb_edge),
                    'market_price': t_price,
                    'time_remaining': remaining,
                    'price_distance_pct': price_distance_pct,
                    'volatility_assumed': vol_assumed,
                    'volatility_realized': vol_realized,
                    'orderbook_imbalance': ob_imbalance,
                    'vwap_deviation_pct': vwap_features.get('vwap_deviation_pct', 0.0),
                    'price_above_vwap': vwap_features.get('price_above_vwap', 0.5),
                    'vwap_trend': vwap_features.get('vwap_trend', 0.0),
                    # NEW: Dynamic Entry Window features for ML learning
                    'entry_timing_ratio': arb.get('entry_timing_ratio', remaining / 900.0),
                    'dynamic_window_used': arb.get('dynamic_window_used', 300),
                    'edge_at_entry': arb.get('edge_at_entry', arb_edge_raw)
                }

            opportunities.append(opp_dict)

            logger.info(f"{coin}: Score={combined_score:.3f} (ArbNorm={arb_edge:.3f}, ArbRaw={arb_edge_raw:.3f}, ML={ml_confidence:.3f}) MinCost=${min_cost:.2f}")

        # Step 2: Check if any opportunities found (already filtered by effective budget)
        if not opportunities:
            # === LATE-GAME FALLBACK: Momentum-following when no BS opportunities ===
            # If time remaining ≤ 200s and a coin shows 80-85¢, bet on that direction
            # Rationale: Market is committing to a direction, 15-20% upside potential
            fallback_config = self.config.get('late_game_fallback', {})
            fallback_enabled = fallback_config.get('enabled', False)
            fallback_max_time = fallback_config.get('max_time_remaining', 200)
            fallback_min_price = fallback_config.get('min_price', 0.80)
            fallback_max_price = fallback_config.get('max_price', 0.85)

            fallback_opportunity = None

            if fallback_enabled and remaining <= fallback_max_time and self.time_decay_sniper_mode:
                td_logger.info(f"\n{'='*60}")
                td_logger.info(f"[LATE-GAME FALLBACK] Checking (time={remaining}s ≤ {fallback_max_time}s)")
                td_logger.info(f"{'='*60}")

                for coin in self.active_coins:
                    # Skip if already bet this round
                    if coin in self.round_coins_bet:
                        td_logger.debug(f"  {coin}: Already bet this round, skipping")
                        continue

                    # Get both YES and NO prices
                    both_prices = self.market_15m.get_both_prices(coin)
                    if not both_prices:
                        td_logger.debug(f"  {coin}: Could not fetch prices")
                        continue

                    yes_price = both_prices.get('yes', 0.5)
                    no_price = both_prices.get('no', 0.5)

                    td_logger.info(f"  {coin}: YES={yes_price*100:.0f}¢, NO={no_price*100:.0f}¢")

                    # Check if YES is in the 80-85¢ range (market committing to UP)
                    if fallback_min_price <= yes_price <= fallback_max_price:
                        td_logger.info(f"  → {coin} YES token at {yes_price*100:.0f}¢ - MOMENTUM UP")

                        # Get token IDs
                        tokens = self.market_15m.get_token_ids_for_coin(coin)
                        if not tokens:
                            continue

                        # Polymarket minimum order is $1.00 USD
                        min_cost = 1.0

                        effective = effective_budgets.get(coin, {'amount': remaining_budget, 'multiplier': 1.0})
                        if min_cost > effective['amount']:
                            td_logger.warning(f"  → Skipped: Min ${min_cost:.2f} > Budget ${effective['amount']:.2f}")
                            continue

                        # Get current spot price for metadata
                        cp = self.fetch_current_price(coin)
                        strike = self.start_prices.get(coin, cp)

                        fallback_opportunity = {
                            'coin': coin,
                            'direction': 'UP',
                            'price': yes_price,
                            'token_id': tokens['yes'],
                            'min_cost': min_cost,
                            'arb_edge': 0.0,  # No BS edge - pure momentum
                            'ml_confidence': 0.5,  # Neutral ML
                            'combined_score': (1.0 - yes_price),  # Potential upside (99¢ - current price)
                            'is_fallback': True,
                            'fallback_reason': f"Momentum UP - YES at {yes_price*100:.0f}¢ with {remaining}s left",
                            # TD Metadata for ML learning
                            'td_metadata': {
                                'bs_probability': yes_price,  # Market implied probability
                                'market_price': yes_price,
                                'time_remaining': remaining,
                                'price_distance_pct': abs(cp - strike) / strike * 100 if strike > 0 else 0,
                                'volatility_assumed': 0.8,
                                'volatility_realized': 0.0,
                                'orderbook_imbalance': 0.0,
                                'vwap_deviation_pct': 0.0,
                                'price_above_vwap': 0.5,
                                'vwap_trend': 0.0,
                                'entry_timing_ratio': remaining / 900.0,
                                'dynamic_window_used': fallback_max_time,
                                'edge_at_entry': 0.0,
                                'is_fallback': True
                            }
                        }
                        break

                    # Check if NO is in the 80-85¢ range (market committing to DOWN)
                    elif fallback_min_price <= no_price <= fallback_max_price:
                        td_logger.info(f"  → {coin} NO token at {no_price*100:.0f}¢ - MOMENTUM DOWN")

                        # Get token IDs
                        tokens = self.market_15m.get_token_ids_for_coin(coin)
                        if not tokens:
                            continue

                        # Polymarket minimum order is $1.00 USD
                        min_cost = 1.0

                        effective = effective_budgets.get(coin, {'amount': remaining_budget, 'multiplier': 1.0})
                        if min_cost > effective['amount']:
                            td_logger.warning(f"  → Skipped: Min ${min_cost:.2f} > Budget ${effective['amount']:.2f}")
                            continue

                        # Get current spot price for metadata
                        cp = self.fetch_current_price(coin)
                        strike = self.start_prices.get(coin, cp)

                        fallback_opportunity = {
                            'coin': coin,
                            'direction': 'DOWN',
                            'price': no_price,
                            'token_id': tokens['no'],
                            'min_cost': min_cost,
                            'arb_edge': 0.0,  # No BS edge - pure momentum
                            'ml_confidence': 0.5,  # Neutral ML
                            'combined_score': (1.0 - no_price),  # Potential upside (99¢ - current price)
                            'is_fallback': True,
                            'fallback_reason': f"Momentum DOWN - NO at {no_price*100:.0f}¢ with {remaining}s left",
                            # TD Metadata for ML learning
                            'td_metadata': {
                                'bs_probability': no_price,  # Market implied probability
                                'market_price': no_price,
                                'time_remaining': remaining,
                                'price_distance_pct': abs(cp - strike) / strike * 100 if strike > 0 else 0,
                                'volatility_assumed': 0.8,
                                'volatility_realized': 0.0,
                                'orderbook_imbalance': 0.0,
                                'vwap_deviation_pct': 0.0,
                                'price_above_vwap': 0.5,
                                'vwap_trend': 0.0,
                                'entry_timing_ratio': remaining / 900.0,
                                'dynamic_window_used': fallback_max_time,
                                'edge_at_entry': 0.0,
                                'is_fallback': True
                            }
                        }
                        break

            # === LOW-VOL LOTTO: Buy cheap tokens when vol is low ===
            # Activates in Mode F (dedicated) or Mode D/E (automatic when vol is low)
            if (self.low_vol_lotto_mode or self.time_decay_sniper_mode) and not fallback_opportunity:
                lotto_cfg = self.config.get('low_vol_lotto', {})
                lotto_max_price = lotto_cfg.get('max_token_price', 0.25)
                lotto_min_vol_ratio = lotto_cfg.get('min_vol_ratio', 1.5)
                lotto_max_time = lotto_cfg.get('max_time_remaining', 300)

                if remaining <= lotto_max_time:
                    logger.info(f"[LOW-VOL LOTTO] Scanning for cheap tokens (≤{lotto_max_price*100:.0f}¢, vol_ratio≥{lotto_min_vol_ratio})")

                    for coin in self.active_coins:
                        if coin in self.round_coins_bet:
                            continue

                        # Check vol ratio
                        vol_assumed = self.arbitrage_detector.volatility.get(coin, 0.8)
                        vol_realized = self.arbitrage_detector.realized_volatility.get(coin, vol_assumed)
                        vol_ratio = vol_assumed / max(vol_realized, 0.01)

                        if vol_ratio < lotto_min_vol_ratio:
                            logger.info(f"  {coin}: vol_ratio={vol_ratio:.2f} < {lotto_min_vol_ratio} - not low-vol enough")
                            continue

                        # Get both prices
                        both_prices = self.market_15m.get_both_prices(coin)
                        if not both_prices:
                            continue

                        yes_price = both_prices.get('yes', 0.5)
                        no_price = both_prices.get('no', 0.5)
                        tokens = self.market_15m.get_token_ids_for_coin(coin)
                        if not tokens:
                            continue

                        logger.info(f"  {coin}: YES={yes_price*100:.0f}¢, NO={no_price*100:.0f}¢, vol_ratio={vol_ratio:.2f}")

                        # Buy whichever side is cheap (≤25¢)
                        chosen = None
                        if yes_price <= lotto_max_price and yes_price > 0.01:
                            chosen = {'direction': 'UP', 'price': yes_price, 'token_id': tokens['yes']}
                        elif no_price <= lotto_max_price and no_price > 0.01:
                            chosen = {'direction': 'DOWN', 'price': no_price, 'token_id': tokens['no']}

                        if chosen:
                            cp = self.fetch_current_price(coin)
                            strike = self.start_prices.get(coin, cp)
                            min_cost = 1.0
                            effective = effective_budgets.get(coin, {'amount': remaining_budget, 'multiplier': 1.0})
                            if min_cost > effective['amount']:
                                continue

                            price_distance_pct = abs(cp - strike) / max(strike, 1.0)

                            fallback_opportunity = {
                                'coin': coin,
                                'direction': chosen['direction'],
                                'price': chosen['price'],
                                'token_id': chosen['token_id'],
                                'min_cost': min_cost,
                                'arb_edge': 0.0,
                                'ml_confidence': 0.5,
                                'combined_score': (1.0 - chosen['price']),  # Higher score for cheaper tokens
                                'is_fallback': True,
                                'is_low_vol_lotto': True,
                                'fallback_reason': f"Low-Vol Lotto: {chosen['direction']} at {chosen['price']*100:.0f}¢ (vol_ratio={vol_ratio:.1f}x)",
                                'td_metadata': {
                                    'bs_probability': chosen['price'],
                                    'market_price': chosen['price'],
                                    'time_remaining': remaining,
                                    'price_distance_pct': price_distance_pct,
                                    'volatility_assumed': vol_assumed,
                                    'volatility_realized': vol_realized,
                                    'vol_ratio': vol_ratio,
                                    'orderbook_imbalance': 0.0,
                                    'vwap_deviation_pct': 0.0,
                                    'price_above_vwap': 0.5,
                                    'vwap_trend': 0.0,
                                    'entry_timing_ratio': remaining / 900.0,
                                    'dynamic_window_used': lotto_max_time,
                                    'edge_at_entry': 0.0,
                                    'is_fallback': True,
                                    'is_low_vol_lotto': True
                                }
                            }
                            logger.info(f"  → LOW-VOL LOTTO: {coin} {chosen['direction']} at {chosen['price']*100:.0f}¢")
                            break

            # If fallback found, add it to opportunities
            if fallback_opportunity:
                td_logger.info(f"\n{'='*60}")
                td_logger.info(f"[LATE-GAME FALLBACK] OPPORTUNITY FOUND!")
                td_logger.info(f"  {fallback_opportunity['coin']} {fallback_opportunity['direction']}")
                td_logger.info(f"  Price: {fallback_opportunity['price']*100:.0f}¢")
                td_logger.info(f"  Potential: +{(1.0 - fallback_opportunity['price'])*100:.0f}¢ to settlement")
                td_logger.info(f"  Reason: {fallback_opportunity['fallback_reason']}")
                td_logger.info(f"{'='*60}\n")
                opportunities.append(fallback_opportunity)
            else:
                # No fallback either - log and return
                if self.time_decay_sniper_mode:
                    td_logger.warning(f"\n{'='*60}")
                    td_logger.warning(f"NO OPPORTUNITIES FOUND THIS ROUND")
                    td_logger.warning(f"{'='*60}")
                    td_logger.warning(f"Rejection summary:")
                    for coin in self.active_coins:
                        if coin in self.round_coins_bet:
                            td_logger.warning(f"  {coin}: Already bet this round")
                    td_logger.warning(f"\nWaiting for 75-85¢ tokens with 15%+ Black-Scholes edge...")
                    if fallback_enabled:
                        td_logger.warning(f"Late-game fallback: No 80-85¢ tokens found (time={remaining}s)")
                    td_logger.warning(f"{'='*60}\n")
                else:
                    logger.warning(f"No coins meet minimum order size with effective budgets")
                return

        # Step 3: Sort by combined score (highest confidence first)
        opportunities.sort(key=lambda x: x['combined_score'], reverse=True)

        logger.info(f"\n{'='*60}")
        logger.info(f"RANKED OPPORTUNITIES (Budget: ${remaining_budget:.2f})")
        logger.info(f"{'='*60}")
        for i, opp in enumerate(opportunities, 1):
            logger.info(f"{i}. {opp['coin']} {opp['direction']}: Score={opp['combined_score']:.3f} MinCost=${opp['min_cost']:.2f}")

        # Step 4: Select best coin(s) that fit budget
        selected = []
        budget_left = remaining_budget

        for opp in opportunities:
            if opp['min_cost'] <= budget_left:
                selected.append(opp)
                budget_left -= opp['min_cost']
                logger.info(f"✓ Selected {opp['coin']} (${opp['min_cost']:.2f}), Remaining: ${budget_left:.2f}")

                # Only select one coin per round for now (can be adjusted)
                break

        if not selected:
            logger.warning("No coins selected after budget allocation")
            return

        # Step 5: Place orders on selected coins
        logger.info(f"\n{'='*60}")
        logger.info(f"PLACING ORDERS")
        logger.info(f"{'='*60}")

        for opp in selected:
            try:
                with self.bet_lock:
                    # Get effective budget for this coin
                    effective = effective_budgets.get(opp['coin'], {'amount': remaining_budget, 'multiplier': 1.0})

                    # Calculate per-coin allocation (same pattern as process_coin_sniping)
                    num_coins_left = len([c for c in self.active_coins if c not in self.round_coins_bet])
                    per_coin_budget = remaining_budget / max(num_coins_left, 1)

                    # Calculate bet amount using PROGRESSIVE betting from TradingStrategy
                    progressive_bet = float(self.strategy.get_current_bet())
                    bet_amt = min(progressive_bet, per_coin_budget, remaining_budget, self.balance * 0.95)

                    # Validate bet still meets minimum
                    if bet_amt < opp['min_cost']:
                        logger.warning(f"Skipped {opp['coin']}: Final bet ${bet_amt:.2f} < Min ${opp['min_cost']:.2f}")
                        continue

                    mode_label = "[LEARNING]" if self.learning_mode else "[REAL]"

                    # Log to Time-Decay log if in TD mode
                    if self.time_decay_sniper_mode:
                        td_logger.info(f"\n{'='*60}")
                        td_logger.info(f"[ORDER] {mode_label} {'SIMULATING' if self.learning_mode else 'Placing'}: {opp['coin']} {opp['direction']} ${bet_amt:.2f}")
                        td_logger.info(f"  Price: {opp['price']*100:.0f}¢ | TD Edge: {opp['arb_edge']:.1%} | ML: {opp['ml_confidence']:.1%}")
                        td_logger.info(f"  Combined Score: {opp['combined_score']:.3f}")
                        td_logger.info(f"{'='*60}\n")

                    logger.info(f"{mode_label} {'SIMULATING' if self.learning_mode else 'Placing'} order: {opp['coin']} {opp['direction']} ${bet_amt:.2f}")
                    logger.info(f"  Confidence: Arb={opp['arb_edge']:.1%} ML={opp['ml_confidence']:.1%} Combined={opp['combined_score']:.3f}")

                    # Route to simulator in learning mode, real order otherwise
                    if self.learning_mode and self.learning_simulator:
                        # Simulate order placement (no real API call)
                        cp = self.fetch_current_price(opp['coin'])
                        # Get condition_id from market cache for learning mode
                        market = self.market_15m.market_cache.get(opp['coin'], {})
                        condition_id = market.get('conditionId') or market.get('condition_id') or market.get('id')

                        # DEBUG: Log condition_id extraction
                        logger.info(f"[DEBUG] {opp['coin']}: Market keys = {list(market.keys())[:10]}")
                        logger.info(f"[DEBUG] {opp['coin']}: conditionId={market.get('conditionId')}, condition_id={market.get('condition_id')}, id={market.get('id')}")
                        logger.info(f"[DEBUG] {opp['coin']}: Using condition_id = {condition_id}")

                        order = self.learning_simulator.simulate_order(
                            coin=opp['coin'],
                            direction=opp['direction'],
                            amount=bet_amt,
                            token_id=opp['token_id'],
                            start_price=self.start_prices.get(opp['coin'], 0),
                            current_price=cp,
                            confidence=opp['combined_score'],
                            condition_id=condition_id
                        )
                    else:
                        # Real order placement
                        order = self.market_15m.place_prediction(opp['coin'], opp['direction'], bet_amt)

                    if order:
                        order['start_price'] = self.start_prices.get(opp['coin'], 0)
                        # Attach arbitrage metadata for ALL modes (enables post-hoc analysis)
                        order['arb_metadata'] = {
                            'fair_value': arb.get('fair_value', 0) if arb else 0,
                            'poly_price': arb.get('poly_price', 0) if arb else 0,
                            'divergence_pct': arb.get('diff', 0) if arb else 0,
                            'edge_at_entry': arb.get('edge_at_entry', 0) if arb else 0,
                            'arb_score_normalized': opp.get('arb_edge', 0),
                            'ml_confidence': opp.get('ml_confidence', 0.5),
                            'combined_score': opp.get('combined_score', 0),
                            'time_remaining': remaining,
                            'spot_price': self.fetch_current_price(opp['coin']),
                            'vol_assumed': self.arbitrage_detector.volatility.get(opp['coin'], 0.8),
                            'vol_realized': self.arbitrage_detector.realized_volatility.get(opp['coin'], 0),
                            'dynamic_window_used': arb.get('dynamic_window_used', 0) if arb else 0,
                            'mode': 'pure_arb' if self.pure_arbitrage_mode else ('td' if self.time_decay_sniper_mode else ('lotto' if self.low_vol_lotto_mode else 'standard')),
                            'risk_profile': self.risk_profile,
                        }
                        # Preserve Time-Decay metadata for ML training during settlement
                        if self.time_decay_sniper_mode and 'td_metadata' in opp:
                            order['td_metadata'] = opp['td_metadata']
                        # Preserve fallback flags for settlement routing
                        if opp.get('is_low_vol_lotto'):
                            order['is_low_vol_lotto'] = True
                        if opp.get('is_fallback'):
                            order['is_fallback'] = True
                        mode_prefix = "SIMULATED" if self.learning_mode else "SUCCESS"
                        self.last_action_msg = f"{mode_prefix}: {opp['coin']} {opp['direction']} ${bet_amt:.2f} (Score: {opp['combined_score']:.2f})"

                        # Update round tracking
                        self.round_budget_spent += bet_amt
                        self.round_coins_bet.add(opp['coin'])
                        remaining_budget -= bet_amt

                        # Track order for monitoring and outcome recording (real mode only)
                        if not self.learning_mode:
                            self.order_tracker.track_order(
                                order_id=order.get('order_id'),
                                coin=opp['coin'],
                                prediction=opp['direction'],
                                cost=bet_amt,
                                token_id=order.get('token_id', opp.get('token_id', '')),
                                start_price=self.start_prices.get(opp['coin'], 0),
                                condition_id=order.get('condition_id'),
                                shares=order.get('shares', 0),
                                price=order.get('price', 0),
                                market_slug=order.get('market_slug', ''),
                                transaction_hashes=order.get('transaction_hashes', []),
                            )

                            # Add to profit-taking position tracker (Week 4)
                            if self.profit_taking_enabled and self.position_tracker:
                                # Calculate expiry time (15 minutes from now)
                                import time
                                expiry_time = time.time() + remaining

                                # Estimate shares (simplified - actual shares from order response would be better)
                                entry_price = opp['price']
                                shares = bet_amt / entry_price if entry_price > 0 else 0

                                position_id = self.position_tracker.add_position({
                                    'coin': opp['coin'],
                                    'direction': opp['direction'],
                                    'token_id': opp['token_id'],
                                    'shares': shares,
                                    'entry_price': entry_price,
                                    'amount': bet_amt,
                                    'entry_time': time.time(),
                                    'expiry_time': expiry_time,
                                    'start_price': self.start_prices.get(opp['coin'], 0),
                                    'confidence': opp['combined_score']
                                })
                                logger.info(f"Position tracked for profit-taking: {position_id}")

                        # AUDIT FIX: current_round_bets now initialized in __init__
                        self.current_round_bets.append(order)
                        self.balance -= bet_amt

                        logger.info(f"✓ Order placed! Spent: ${self.round_budget_spent:.2f}/${self.user_max_bet:.2f}")
                    else:
                        logger.error(f"Failed to place order for {opp['coin']}")

            except Exception as e:
                logger.error(f"Error placing order for {opp['coin']}: {e}")

    def process_coin_sniping(self, coin, remaining):
        self._collect_data(coin, self.start_prices.get(coin, 0), remaining)
        cp = self.fetch_current_price(coin)
        pp = self.market_15m.get_current_price(coin) or 0.5

        # CONTINUOUS SYNC: Try to get official strike from metadata
        official = self.market_15m.get_official_strike_price(coin)
        if official:
            self.start_prices[coin] = official
            self.strike_types[coin] = "OFFCL"

        # Pass market_15m for real YES/NO prices; spot prices come from shared price feed
        if self.pure_arbitrage_mode:
            arb = self.arbitrage_detector.check_arbitrage(
                coin, pp, self.start_prices.get(coin, cp), remaining,
                market_15m=self.market_15m
            )
        else:
            arb = self.arbitrage_detector.check_arbitrage(
                coin, pp, self.start_prices.get(coin, cp), remaining
            )

        # Safe handling of potentially None direction
        direction_display = arb.get('direction', '--') if arb else '--'

        # Compute display edge: for pure arbitrage, always show spot-vs-strike distance
        # so the dashboard is never blank. Uses cp (Real Price) and strike (both shown in UI).
        display_edge = arb.get('diff', 0.0) if arb else 0.0
        if self.pure_arbitrage_mode and display_edge == 0.0:
            strike = self.start_prices.get(coin, 0)
            if cp and cp > 0 and strike and strike > 0:
                display_edge = ((cp - strike) / strike) * 100
                if not direction_display or direction_display == '--':
                    direction_display = "UP" if display_edge > 0 else "DOWN" if display_edge < 0 else "--"

        self.predictions[coin] = {
            'direction': direction_display,
            'arb_opportunity': arb['opportunity'] if arb else False,
            'edge': display_edge,
            'time_left': remaining
        }

        # Edge Cooldown: Track only ACTIONABLE edges (inside dynamic window)
        # Raw edge at 800s remaining is meaningless — it can't become a bet.
        # Only edges where opportunity=True could actually lead to a trade.
        # Skip for Mode A — its edge scale (spot distance %) doesn't match cooldown thresholds.
        if self.edge_cooldown_enabled and not self.pure_arbitrage_mode and arb:
            edge_val = abs(arb.get('diff', 0.0))
            if arb.get('opportunity'):
                self.round_edge_samples.append(edge_val)
                self.round_edge_per_coin.setdefault(coin, []).append(edge_val)

        # CRITICAL: Validate direction exists before attempting to trade
        # Only place orders during SNIPE state — MONITOR just collects data + updates dashboard
        if arb and arb['opportunity'] and arb.get('direction') and self.round_state == "SNIPE":
            try:
                with self.bet_lock:
                    # CRITICAL FIX: Check if already bet on this coin this round
                    if coin in self.round_coins_bet:
                        logger.info(f"Skipped {coin}: Already bet on this coin this round")
                        return None

                    # CRITICAL FIX: Check remaining round budget
                    remaining_budget = self.user_max_bet - self.round_budget_spent
                    if remaining_budget < 0.1:  # Minimum $0.10 to place order
                        logger.info(f"Skipped {coin}: Round budget exhausted (${self.round_budget_spent:.2f}/${self.user_max_bet:.2f})")
                        return None

                    # CRITICAL FIX: Use same price source as CLI (get_both_prices)
                    both_prices = self.market_15m.get_both_prices(coin)
                    if not both_prices:
                        logger.warning(f"Skipped {coin}: Could not fetch prices")
                        return None

                    tokens = self.market_15m.get_token_ids_for_coin(coin)
                    if not tokens:
                        logger.warning(f"Skipped {coin}: Could not find token IDs.")
                        return None
                    tid = tokens['yes'] if arb['direction'] == 'UP' else tokens['no']
                    t_price = both_prices['yes'] if arb['direction'] == 'UP' else both_prices['no']
                    if self.validate_trade(coin, t_price):
                        # CRITICAL FIX: Calculate per-coin allocation
                        # Distribute budget fairly across remaining coins
                        num_coins_left = len([c for c in self.active_coins if c not in self.round_coins_bet])
                        per_coin_budget = remaining_budget / max(num_coins_left, 1)

                        # Use PROGRESSIVE betting from TradingStrategy, constrained by budget
                        progressive_bet = float(self.strategy.get_current_bet())
                        bet_amt = min(progressive_bet, per_coin_budget, remaining_budget, self.balance * 0.95)

                        # Polymarket minimum order is $1.00 USD
                        if bet_amt < 1.0:
                            logger.info(f"Skipped {coin}: Bet ${bet_amt:.2f} < $1.00 Polymarket minimum")
                            return None

                        mode_label = "[LEARNING]" if self.learning_mode else "[REAL]"
                        logger.info(f"{mode_label} {'SIMULATING' if self.learning_mode else 'Placing'} order: {coin} {arb['direction']} ${bet_amt:.2f} (Budget: ${self.round_budget_spent:.2f}/${self.user_max_bet:.2f})")

                        # Route to simulator in learning mode, real order otherwise
                        if self.learning_mode and self.learning_simulator:
                            # Simulate order placement (no real API call)
                            tokens = self.market_15m.get_token_ids_for_coin(coin)
                            if not tokens:
                                logger.warning(f"Skipped {coin}: Could not find token IDs for simulation.")
                                return None

                            token_id = tokens['yes'] if arb['direction'] == 'UP' else tokens['no']
                            market = self.market_15m.market_cache.get(coin, {})
                            condition_id = market.get('conditionId') or market.get('condition_id') or market.get('id')
                            order = self.learning_simulator.simulate_order(
                                coin=coin,
                                direction=arb['direction'],
                                amount=bet_amt,
                                token_id=token_id,
                                start_price=self.start_prices.get(coin, 0),
                                current_price=cp,
                                confidence=min(abs(arb.get('diff', 0.0)) / 100.0, 1.0),
                                condition_id=condition_id
                            )
                        else:
                            # Real order placement
                            order = self.market_15m.place_prediction(coin, arb['direction'], bet_amt)

                        if order:
                            order['start_price'] = self.start_prices.get(coin, 0)
                            # Attach arbitrage metadata for post-hoc analysis
                            order['arb_metadata'] = {
                                'fair_value': arb.get('fair_value', 0),
                                'poly_price': arb.get('poly_price', 0),
                                'divergence_pct': arb.get('diff', 0),
                                'edge_at_entry': arb.get('edge_at_entry', 0),
                                'time_remaining': remaining,
                                'spot_price': cp,
                                'vol_assumed': self.arbitrage_detector.volatility.get(coin, 0.8),
                                'vol_realized': self.arbitrage_detector.realized_volatility.get(coin, 0),
                                'dynamic_window_used': arb.get('dynamic_window_used', 0),
                                'mode': 'pure_arb' if self.pure_arbitrage_mode else 'standard',
                                'risk_profile': self.risk_profile,
                            }
                            mode_prefix = "SIMULATED" if self.learning_mode else "SUCCESS"
                            self.last_action_msg = f"{mode_prefix}: {coin} {arb['direction']} ${bet_amt:.2f}"

                            # CRITICAL FIX: Update round tracking
                            self.round_budget_spent += bet_amt
                            self.round_coins_bet.add(coin)

                            # Track order for monitoring and outcome recording (real mode only)
                            if not self.learning_mode:
                                self.order_tracker.track_order(
                                    order_id=order.get('order_id'),
                                    coin=coin,
                                    prediction=arb['direction'],
                                    cost=bet_amt,
                                    token_id=order.get('token_id', ''),
                                    start_price=self.start_prices.get(coin, 0),
                                    condition_id=order.get('condition_id'),
                                    shares=order.get('shares', 0),
                                    price=order.get('price', 0),
                                    market_slug=order.get('market_slug', ''),
                                    transaction_hashes=order.get('transaction_hashes', []),
                                )

                            # AUDIT FIX: current_round_bets now initialized in __init__
                            self.current_round_bets.append(order)
                            self.balance -= bet_amt

                            logger.info(f"{'Simulated' if self.learning_mode else 'Order placed'}! Total round spending: ${self.round_budget_spent:.2f}/${self.user_max_bet:.2f}")
                            return coin
            except Exception as e:
                logger.error(f"Error placing bet on {coin}: {e}")
        return None

    def tick(self):
        self.window_info = self.market_15m.get_current_window_info()
        remaining = self.window_info['seconds_remaining']
        elapsed = self.window_info['seconds_elapsed']

        # FOK orders fill instantly — no need to poll CLOB API every tick.
        # Settlement handles outcome recording via settle_and_save_trade().
        # Just clean up stale entries periodically.
        if time.time() - self._last_stale_cleanup > 60:
            self.order_tracker.clear_stale_orders(max_age_seconds=1800)  # 30 min
            self._last_stale_cleanup = time.time()

        if self.round_state == "INIT":
            if elapsed < 60:
                self.current_status = "Capturing Round Start"
                self.market_15m.clear_market_cache()
                markets = self.market_15m.get_current_15m_markets(self.coins)
                if markets:
                    self.active_coins = list(markets.keys())

                    # FIX: Use EXISTING get_official_strike_price() to get official strikes at INIT
                    self.start_prices = {}
                    self.strike_types = {}
                    for c in self.active_coins:
                        official_strike = self.market_15m.get_official_strike_price(c)
                        if official_strike:
                            self.start_prices[c] = official_strike
                            self.strike_types[c] = "OFFCL"
                            logger.info(f"{c}: Official strike ${official_strike:.2f}")
                        else:
                            # Fallback to current price
                            self.start_prices[c] = self.fetch_current_price(c)
                            self.strike_types[c] = "Appx"
                            logger.warning(f"{c}: Using approximate strike ${self.start_prices[c]:.2f}")

                    # Reset round budget tracking
                    self.round_budget_spent = 0.0
                    self.round_coins_bet = set()
                    self.current_round_bets = []  # AUDIT FIX: Clear bets for new round
                    self.round_edge_samples = []  # Reset edge tracking for new round
                    self.round_edge_per_coin = {}  # Reset per-coin edge tracking
                    logger.info(f"New round started - Budget: ${self.user_max_bet:.2f}")

                    # Clean up any stale orders from previous rounds
                    # AUDIT FIX: order_tracker initialized in __init__
                    self.order_tracker.clear_stale_orders(max_age_seconds=900)  # 15 min
                    logger.info("Cleared stale orders from previous round")

                    # Clean up orphaned virtual positions from previous rounds
                    # On-chain is source of truth — settle properly if resolved, cancel only as fallback
                    if self.learning_mode and self.learning_simulator:
                        orphaned = list(self.learning_simulator.virtual_positions.items())
                        if orphaned:
                            logger.warning(f"[INIT] Found {len(orphaned)} orphaned virtual position(s) — attempting on-chain settlement")
                            for oid, pos in orphaned:
                                cid = pos.get('condition_id')
                                if cid:
                                    try:
                                        onchain_outcome = self.market_15m.check_onchain_resolution(cid)
                                        if onchain_outcome:
                                            logger.info(f"[INIT] ✓ On-chain resolved orphan {pos.get('coin')} → {onchain_outcome}")
                                            trade_record = self.learning_simulator.settle_position(
                                                order_id=oid,
                                                final_price=0,
                                                start_price=pos.get('start_price', 0),
                                                official_outcome=onchain_outcome
                                            )
                                            if trade_record:
                                                from .core.persistence import atomic_json_write, safe_json_load
                                                filepath = 'data/learning_trades.json'
                                                existing = safe_json_load(filepath, default=[])
                                                existing.append(trade_record)
                                                atomic_json_write(filepath, existing)
                                                logger.info(f"[INIT] ✓ Orphaned trade settled and saved for ML training")
                                            continue
                                    except Exception as e:
                                        logger.error(f"[INIT] On-chain resolution failed for orphan {oid}: {e}")
                                # Fallback: cancel and refund
                                self.learning_simulator.cancel_position(oid, reason="orphaned from previous round")

                    # Update correlations (Week 3) - Regime detection retired
                    try:
                        self.correlation_engine.update_correlations()
                    except Exception as e:
                        logger.error(f"Failed to update correlations: {e}")

                    # Compute realized volatility for vol-scaled distance guard
                    try:
                        self._compute_realized_volatility()
                    except Exception as e:
                        logger.error(f"Failed to compute realized volatility: {e}")

                    # Update historical database with latest candles (Week 6)
                    try:
                        for coin in self.active_coins:
                            for timeframe in ['1h', '4h', '1d', '1w']:
                                self.exchange_data.update_latest_candles(
                                    coin, timeframe, self.historical_data
                                )
                        logger.debug("Historical data updated")
                    except Exception as e:
                        logger.error(f"Failed to update historical data: {e}")

                    # Calculate edge immediately on startup (so user sees opportunities right away)
                    logger.info("Calculating initial arbitrage edges...")
                    for coin in self.active_coins:
                        try:
                            self.process_coin_sniping(coin, remaining)
                        except Exception as e:
                            logger.error(f"Failed to calculate edge for {coin}: {e}")

                    # Jump to SNIPE if >60s remaining and within max dynamic window (720s)
                    if remaining > 60 and remaining <= 720:
                        self.round_state = "SNIPE"
                        logger.info(f"Bot started late ({remaining}s remaining) - jumping directly to SNIPE")
                    else:
                        self.round_state = "MONITOR"
            else:
                self.current_status = f"Syncing ({remaining:.0f}s)"
                if remaining < 5: self.round_state = "RESET"
        
        elif self.round_state == "MONITOR":
            self.current_status = "Monitoring & Learning"
            # FIX: Use EXISTING process_coin_sniping to update predictions (but won't place orders)
            # This updates edge/signal in dashboard and syncs official strikes
            for coin in self.active_coins:
                self.process_coin_sniping(coin, remaining)
            if remaining <= 720: self.round_state = "SNIPE"  # 720s = 12 min max dynamic window
                
        elif self.round_state == "SNIPE":
            self.current_status = "Sniping Opportunities"
            # NEW: Smart coin selection based on ML confidence + arbitrage edge
            self.smart_coin_selection(remaining)
            if remaining < 10: self.round_state = "SETTLE"
                
        elif self.round_state == "SETTLE":
            self.current_status = "Settling"
            # DEBUG: Log settlement attempt (AUDIT FIX: removed hasattr - now initialized in __init__)
            bets_count = len(self.current_round_bets)
            logger.info(f"SETTLE state reached - Bets to settle: {bets_count}")

            # Always start settlement thread - handles both placed bets AND passive learning
            # Even with 0 bets, we need to:
            # 1. Run passive learning (label observations for ML training)
            # 2. Finalize phantom tracking (learn from rejected opportunities)
            logger.info(f"Starting settlement thread for {len(self.current_round_bets)} bets")
            seconds_remaining = self.window_info.get('seconds_remaining', 0)
            logger.info(f"Settlement started with {seconds_remaining}s remaining in market")
            Thread(target=self.background_settlement, args=(self.current_round_bets, self.start_prices, seconds_remaining)).start()

            # Round summary log (always runs, captures edge stats + bets + cooldown state)
            if self.edge_cooldown_enabled:
                self._log_round_summary()
                self._evaluate_edge_cooldown()

            self.current_round_bets = []
            self.round_state = "RESET"
            
        elif self.round_state == "RESET":
            # Transition back to INIT when new market window starts (most of 15min window available)
            # Using 850s threshold ensures brief RESET period (50s) before new INIT
            if remaining >= 850: self.round_state = "INIT"  # AUDIT FIX: >= prevents oscillation at boundary

    def run(self, num_rounds=None):
        try:
            last_balance_check = 0
            with Live(self.update_dashboard(), refresh_per_second=2) as live:
                while True:
                    # Check balance/approvals every 60s
                    if time.time() - last_balance_check > 60:
                        self._check_initial_state()
                        last_balance_check = time.time()
                        
                    self.tick()
                    live.update(self.update_dashboard())
                    time.sleep(0.5)
        except KeyboardInterrupt: pass
        finally: self.ws_manager.stop(); self.exchange_data.stop(); self.doctor.stop()

if __name__ == "__main__":
    bot = AdvancedPolymarketBot()
    bot.run()