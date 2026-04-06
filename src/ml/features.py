"""
Feature Engineering - Extract technical indicators from price data
Uses TA-Lib for professional technical analysis
"""

import numpy as np
import pandas as pd
import talib
from typing import Dict, List, Optional

class FeatureExtractor:
    """
    Extracts comprehensive features for ML models:
    - 21 multi-timeframe features
    - 22 technical indicators
    - 6 cross-market correlation features
    - 4 microstructure features (Time Remaining, Distance, Imbalance, Spread)
    - 3 Binance Signal features (Trend, Imbalance, Spread)
    Total: 56 features per prediction
    """

    def __init__(self):
        self.feature_names = []
        self._build_feature_names()

    def _build_feature_names(self):
        """Build list of all feature names for reference"""
        timeframes = ['1s', '1m', '15m', '1h', '4h', '1d', '1w']

        # Multi-timeframe features (now includes VWAP)
        for tf in timeframes:
            self.feature_names.extend([
                f'{tf}_trend_direction',
                f'{tf}_trend_strength',
                f'{tf}_momentum',
                f'{tf}_vwap',              # NEW: Volume Weighted Average Price
                f'{tf}_price_vs_vwap',     # NEW: Current price vs VWAP
                f'{tf}_vwap_distance_pct'  # NEW: Distance from VWAP
            ])

        # Technical indicators
        indicators = [
            'rsi_14', 'rsi_7',
            'macd', 'macd_signal', 'macd_hist',
            'stoch_k', 'stoch_d',
            'adx', 'cci', 'mfi',
            'bb_upper', 'bb_middle', 'bb_lower', 'bb_position',
            'atr',
            'obv',
            'mom_10', 'roc_10',
            'ema_12', 'ema_26',
            'candle_volatility',
            'candle_momentum'
        ]

        self.feature_names.extend(indicators)

        # Cross-market correlation features
        cross_market = [
            'btc_change_1m',
            'eth_change_1m',
            'sol_change_1m',
            'btc_eth_correlation',
            'btc_sol_correlation',
            'eth_sol_correlation'
        ]

        self.feature_names.extend(cross_market)
        
        # Microstructure features
        microstructure = [
            'time_remaining_pct', # NEW
            'distance_to_strike',
            'orderbook_imbalance',
            'spread_pct'
        ]
        self.feature_names.extend(microstructure)
        
        # Binance features
        self.feature_names.extend(['bin_trend', 'bin_imbalance', 'bin_spread'])
        
        # Advanced Context & Self-Correction
        self.feature_names.extend([
            'spread_diff',       # Poly vs Binance spread
            'imbalance_diff',    # Poly vs Binance orderbook imbalance
            'market_volume',     # Poly liquidity/volume context
            'win_rate',          # Bot's historical performance (Self-Correction)
            'streak'             # Bot's winning/losing streak
        ])

        # Arbitrage Context Features (Hybrid Approach - Option C)
        self.feature_names.extend([
            'has_arbitrage_opportunity',  # Boolean: Is there an arbitrage edge?
            'arbitrage_strength',         # Normalized arbitrage edge (0-1)
            'fair_value_deviation',       # How far market price is from fair value
            'price_level_category'        # Low (<0.20), Mid (0.20-0.80), High (>0.80)
        ])

    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators using TA-Lib"""
        close = df['close'].values
        high = df['high'].values if 'high' in df else close
        low = df['low'].values if 'low' in df else close
        volume = df['volume'].values if 'volume' in df else np.ones_like(close)

        indicators = {}

        # Moving Averages
        indicators['sma_5'] = talib.SMA(close, timeperiod=5)
        indicators['sma_10'] = talib.SMA(close, timeperiod=10)
        indicators['sma_20'] = talib.SMA(close, timeperiod=20)
        indicators['ema_12'] = talib.EMA(close, timeperiod=12)
        indicators['ema_26'] = talib.EMA(close, timeperiod=26)

        # Momentum Indicators
        indicators['rsi_7'] = talib.RSI(close, timeperiod=7)
        indicators['rsi_14'] = talib.RSI(close, timeperiod=14)

        # MACD
        indicators['macd'], indicators['macd_signal'], indicators['macd_hist'] = talib.MACD(
            close, fastperiod=12, slowperiod=26, signalperiod=9
        )

        # Stochastic
        indicators['stoch_k'], indicators['stoch_d'] = talib.STOCH(
            high, low, close, fastk_period=14, slowk_period=3, slowd_period=3
        )

        # ADX (trend strength)
        indicators['adx'] = talib.ADX(high, low, close, timeperiod=14)

        # CCI (Commodity Channel Index)
        indicators['cci'] = talib.CCI(high, low, close, timeperiod=14)

        # MFI (Money Flow Index)
        indicators['mfi'] = talib.MFI(high, low, close, volume, timeperiod=14)

        # Bollinger Bands
        indicators['bb_upper'], indicators['bb_middle'], indicators['bb_lower'] = talib.BBANDS(
            close, timeperiod=20, nbdevup=2, nbdevdn=2
        )

        # ATR (Average True Range - volatility)
        indicators['atr'] = talib.ATR(high, low, close, timeperiod=14)

        # OBV (On Balance Volume)
        indicators['obv'] = talib.OBV(close, volume)

        # Momentum
        indicators['mom_10'] = talib.MOM(close, timeperiod=10)

        # Rate of Change
        indicators['roc_10'] = talib.ROC(close, timeperiod=10)

        return pd.DataFrame(indicators)

    def extract_features(self, df: pd.DataFrame, mtf_features: np.ndarray = None) -> np.ndarray:
        """
        Extract base technical features
        """
        # Calculate technical indicators
        indicators_df = self.calculate_technical_indicators(df)

        features = []

        # 1. Multi-timeframe features (21)
        if mtf_features is not None:
            features.extend(mtf_features.tolist())
        else:
            features.extend([0] * 42)  # 7 timeframes × 6 features each (incl. VWAP)

        # 2. Technical indicators (22)
        def safe_get(series, default=0):
            val = series.iloc[-1]
            return val if not pd.isna(val) else default

        indicator_features = [
            safe_get(indicators_df['rsi_14'], 50) / 100,
            safe_get(indicators_df['rsi_7'], 50) / 100,
            safe_get(indicators_df['macd'], 0),
            safe_get(indicators_df['macd_signal'], 0),
            safe_get(indicators_df['macd_hist'], 0),
            safe_get(indicators_df['stoch_k'], 50) / 100,
            safe_get(indicators_df['stoch_d'], 50) / 100,
            safe_get(indicators_df['adx'], 0) / 100,
            safe_get(indicators_df['cci'], 0) / 200,
            safe_get(indicators_df['mfi'], 50) / 100,
        ]
        features.extend(indicator_features)

        # 3. Cross-Market Features (Placeholder - 6 features)
        # TODO: Pass actual price dict to calculate real correlations
        features.extend([0.0] * 6)

        # Bollinger Bands position
        close = df['close'].iloc[-1]
        bb_upper = safe_get(indicators_df['bb_upper'], close)
        bb_lower = safe_get(indicators_df['bb_lower'], close)
        
        if bb_upper != bb_lower:
            bb_position = (close - bb_lower) / (bb_upper - bb_lower)
        else:
            bb_position = 0.5

        features.extend([
            bb_upper,
            safe_get(indicators_df['bb_middle'], close),
            bb_lower,
            bb_position
        ])

        features.extend([
            safe_get(indicators_df['atr'], 0),
            safe_get(indicators_df['obv'], 0) / 1e6,
            safe_get(indicators_df['mom_10'], 0),
            safe_get(indicators_df['roc_10'], 0) / 100,
            safe_get(indicators_df['ema_12'], close),
            safe_get(indicators_df['ema_26'], close),
        ])

        # Candle features
        if len(df) >= 60:
            recent_prices = df['close'].iloc[-60:].values
            mean_price = np.mean(recent_prices)
            volatility = np.std(recent_prices) / mean_price if mean_price > 0 else 0
            momentum = (recent_prices[-1] - recent_prices[0]) / max(abs(recent_prices[0]), 1e-10)
        else:
            volatility = 0
            momentum = 0

        features.extend([volatility, momentum])
        
        return np.array(features)

    def append_microstructure_features(self, base_features: np.ndarray,
                                     current_price: float,
                                     start_price: float,
                                     orderbook: Optional[Dict],
                                     binance_features: Optional[Dict] = None,
                                     time_remaining: float = 0,
                                     bot_stats: Optional[Dict] = None,
                                     market_stats: Optional[Dict] = None,
                                     arbitrage_data: Optional[Dict] = None) -> np.ndarray:
        """
        Append microstructure, Binance signals, time context, self-learning stats, and arbitrage context
        """
        # 1. Time Remaining (Normalized 0-1)
        time_rem_pct = time_remaining / 900.0 # 900s in 15m
        time_rem_pct = max(0.0, min(1.0, time_rem_pct))

        # 2. Distance to Strike
        dist_to_strike = 0.0
        if start_price and start_price > 0:
            dist_to_strike = (current_price - start_price) / start_price
            
        # 3. Orderbook Imbalance & Spread
        imbalance = 0.0
        spread_pct = 0.0

        if orderbook:
            # Handle both dict and OrderBookSummary dataclass
            if hasattr(orderbook, 'bids'):
                bids = orderbook.bids or []
                asks = orderbook.asks or []
            else:
                bids = orderbook.get('bids', [])
                asks = orderbook.get('asks', [])
            
            def sum_vol(items):
                total = 0
                for item in items[:5]: 
                    if isinstance(item, dict):
                        total += float(item.get('size', 0))
                    elif hasattr(item, 'size'):
                        total += float(item.size)
                return total
            
            bid_vol = sum_vol(bids)
            ask_vol = sum_vol(asks)
            
            if bid_vol + ask_vol > 0:
                imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)
                
            if bids and asks:
                best_bid = float(bids[0]['price']) if isinstance(bids[0], dict) else float(bids[0].price)
                best_ask = float(asks[0]['price']) if isinstance(asks[0], dict) else float(asks[0].price)
                if best_bid > 0:
                    spread_pct = (best_ask - best_bid) / best_bid

        # 4. Binance Signals
        bin_trend = 0.0
        bin_imbalance = 0.0
        bin_spread = 0.0
        
        if binance_features:
            bin_trend = binance_features.get('bin_trend_5m', 0)
            bin_imbalance = binance_features.get('bin_imbalance', 0)
            bin_spread = binance_features.get('bin_spread', 0)

        # 5. Advanced / Self-Learning Features
        # Spread Diff
        spread_diff = spread_pct - bin_spread
        
        # Imbalance Diff
        imbalance_diff = imbalance - bin_imbalance
        
        # Market Volume (Log Scaled)
        market_vol = 0.0
        if market_stats:
            raw_vol = float(market_stats.get('volume', 0))
            market_vol = np.log1p(raw_vol) # log(1+x) to handle 0 and scale
            
        # Bot Performance (Win Rate & Streak)
        win_rate = 0.5
        streak = 0.0
        if bot_stats:
            win_rate = float(bot_stats.get('win_rate', 0.5))
            streak = float(bot_stats.get('streak', 0.0))

        # 6. Arbitrage Context Features (Hybrid Approach - Option C)
        has_arbitrage_opportunity = 0.0
        arbitrage_strength = 0.0
        fair_value_deviation = 0.0
        price_level_category = 0.5  # Default to mid

        if arbitrage_data:
            # Has arbitrage opportunity (boolean 1/0)
            arb_edge = arbitrage_data.get('edge_pct', 0.0)
            has_arbitrage_opportunity = 1.0 if abs(arb_edge) > 0.02 else 0.0  # >2% edge threshold

            # Arbitrage strength (normalized 0-1)
            # Typical edges range from 0-10%, normalize to 0-1
            arbitrage_strength = min(1.0, abs(arb_edge) / 0.10)

            # Fair value deviation (market price vs fair value)
            market_price = arbitrage_data.get('market_price', current_price)
            fair_value = arbitrage_data.get('fair_value', current_price)
            if fair_value > 0:
                fair_value_deviation = (market_price - fair_value) / fair_value

            # Price level category: Low (<0.20)=0, Mid (0.20-0.80)=0.5, High (>0.80)=1.0
            if market_price < 0.20:
                price_level_category = 0.0
            elif market_price > 0.80:
                price_level_category = 1.0
            else:
                price_level_category = 0.5

        micro_features = np.array([
            time_rem_pct, dist_to_strike, imbalance, spread_pct,
            bin_trend, bin_imbalance, bin_spread,
            spread_diff, imbalance_diff, market_vol, win_rate, streak,
            has_arbitrage_opportunity, arbitrage_strength, fair_value_deviation, price_level_category
        ])

        return np.concatenate([base_features, micro_features])

    def extract_cross_market_features(self, prices: Dict[str, Dict]) -> np.ndarray:
        try:
            btc_change = 0.0
            eth_change = 0.0
            sol_change = 0.0

            if 'BTC' in prices and prices['BTC']['current'] and prices['BTC']['1m_ago']:
                btc_change = (prices['BTC']['current'] - prices['BTC']['1m_ago']) / prices['BTC']['1m_ago']

            if 'ETH' in prices and prices['ETH']['current'] and prices['ETH']['1m_ago']:
                eth_change = (prices['ETH']['current'] - prices['ETH']['1m_ago']) / prices['ETH']['1m_ago']

            if 'SOL' in prices and prices['SOL']['current'] and prices['SOL']['1m_ago']:
                sol_change = (prices['SOL']['current'] - prices['SOL']['1m_ago']) / prices['SOL']['1m_ago']

            btc_eth_corr = btc_change * eth_change
            btc_sol_corr = btc_change * sol_change
            eth_sol_corr = eth_change * sol_change

            return np.array([
                btc_change, eth_change, sol_change,
                btc_eth_corr, btc_sol_corr, eth_sol_corr
            ])

        except Exception:
            return np.zeros(6)