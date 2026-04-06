# Advanced Polymarket Trading Bot

## 🎯 Features

✅ **Last-Second Betting** - Bets at 14:59 (not 0:00) using full candle data  
✅ **Continuous Learning** - Updates ML models every 5 observations  
✅ **Multi-Timeframe Analysis** - 7 timeframes (1s to 1w)  
✅ **Technical Indicators** - 15+ indicators (RSI, MACD, Bollinger Bands, etc.)  
✅ **Arbitrage Detection** - Real-time price comparison vs exchanges  
✅ **Risk Management** - Circuit breakers, loss limits, position sizing  
✅ **Profit Protection** - Saves 100% of profits immediately  
✅ **Parallel Trading** - Trades BTC, ETH, SOL simultaneously  

## 📦 Installation

### 1. Install Dependencies
```bash
# Python 3.9+ required
pip install -r requirements.txt

# Install TA-Lib (requires C library)
# macOS:
brew install ta-lib

# Ubuntu/Debian:
sudo apt-get install ta-lib

# Windows: Download from https://ta-lib.org
```

### 2. Configure Environment
```bash
# Copy example env file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Required variables:
- `WALLET_PRIVATE_KEY` - Your Polygon wallet private key
- `POLYGON_RPC_URL` - Polygon RPC endpoint
- Other optional settings

### 3. Edit Configuration
```bash
# Edit config/config.yaml
nano config/config.yaml
```

Key settings:
- `initial_bet_usdt` - Starting bet size
- `profit_increase_pct` - % of profit to add after wins
- `max_daily_loss_pct` - Daily loss limit
- `circuit_breaker_consecutive_losses` - Auto-stop threshold

## 🚀 Usage

### Basic Usage
```bash
python src/bot.py
```

### With Custom Config
```bash
python src/bot.py --config config/my_config.yaml
```

### Run Specific Number of Rounds
```python
from src.bot import AdvancedPolymarketBot

bot = AdvancedPolymarketBot()
bot.run(num_rounds=10)  # Trade for 10 rounds (2.5 hours)
```

## 🔐 Security

⚠️ **NEVER commit your `.env` file to Git!**

- Store private keys in `.env` (not in code)
- Use hardware wallet for large amounts
- Test with small amounts first
- Keep sufficient MATIC for gas fees

## 📊 Monitoring

The bot outputs:
- Real-time price updates every 60 seconds
- Trade results after each round
- Final comprehensive report
- JSON trade history in `reports/`

## 🧪 Testing
```bash
# Run unit tests
pytest tests/

# Run backtest
python scripts/backtest.py --start 2025-01-01 --end 2025-01-29
```

## 📈 Strategy

### Money Management

1. Start with default bet (e.g., 10 USDT)
2. On WIN: Save 100% of profit, add X% to next bet
3. On LOSS: Reset to default bet immediately
4. Saved profits NEVER at risk

### Example 10-Win Streak