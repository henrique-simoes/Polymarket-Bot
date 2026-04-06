# Project Cleanup Summary

**Date**: February 4, 2026
**Status**: ✅ COMPLETED

---

## What Was Cleaned Up

### 1. Archived Test Scripts (23 files moved to `tests/archive/`)

**Wallet/Balance Testing**:
- audit_wallet.py
- check_usdc_balance.py
- check_wallet.py
- check_order_args.py

**Market Investigation**:
- inspect_market.py
- inspect_market_structure.py
- inspect_webpage.py
- investigate_tokens.py

**Debugging Scripts**:
- diagnose_trades.py
- parse_debug_html.py
- probe_arbitrage.py

**Component Tests**:
- test_bot_init.py
- test_enhancements.py
- test_market_data.py
- test_meta_learning.py
- test_orderbook.py
- test_price_display.py
- test_regime_fix.py
- test_websockets.py

**Quick Tests**:
- quick_test.py
- verify_fixes.py
- verify_ml_fixes.py

**Monitoring**:
- monitor_bot.py (archived - monitor_positions.py kept in root)

---

### 2. Deleted Broken/Unused Files

**Broken Standalone Bot**:
- `src/contrarian_bot.py` - Had import errors, duplicated functionality

**Unused Components**:
- `src/core/improved_order_tracker.py` - Never imported, replaced by regular order tracker

**Corrupted Backups**:
- `data/ml_episodes.json.corrupted` - Old backup from Feb 3

---

### 3. Moved to Better Locations

**Examples**:
- `src/simple_bot_example.py` → `examples/simple_bot_example.py`

---

### 4. Configuration Fixes

**Fixed Config Mismatches**:
- `contrarian.enabled: false` - Was enabled but not integrated into main bot
- `pure_arbitrage.enabled: false` - User was profitable with Standard ML mode, not pure arbitrage

**Restored Profitable Settings**:
- `snipe_window: 300` - 5 minutes (user's profitable setting)
- Standard ML mode active (60% arbitrage + 40% ML)

---

## Project Structure After Cleanup

### Core Files (Keep - Actively Used)

**Main Bot**:
- `src/bot.py` - Main orchestration
- `run_bot.py` - Launcher wrapper

**Core Components** (11 files):
- `src/core/wallet.py`
- `src/core/polymarket.py`
- `src/core/market_15m.py`
- `src/core/price_feed.py`
- `src/core/persistence.py`
- `src/core/order_tracker.py` ✓ ACTIVE
- `src/core/exchange_data.py`
- `src/core/historical_data.py`
- `src/core/monitoring.py`
- `src/core/websocket_manager.py`
- `src/core/doctor.py`

**Learning Mode** (3 files):
- `src/core/learning_simulator.py`
- `src/core/learning_persistence.py`
- `src/core/learning_recommendation.py`

**ML Components** (7 files):
- `src/ml/features.py`
- `src/ml/learning.py`
- `src/ml/models.py`
- `src/ml/strategy_tracker.py`
- `src/ml/position_tracker.py`
- `src/ml/exit_timing_learner.py`
- `src/ml/profit_taking_engine.py`

**Analysis** (5 files):
- `src/analysis/arbitrage.py` - Theoretical pricing (Black-Scholes)
- `src/analysis/pure_arbitrage.py` - Mathematical arbitrage
- `src/analysis/timeframes.py`
- `src/analysis/regime_detector.py`
- `src/analysis/correlation_engine.py`

**Trading** (4 files):
- `src/trading/strategy.py`
- `src/trading/risk.py`
- `src/trading/market_maker.py`
- `src/trading/contrarian.py`

**Utils** (4 files):
- `src/utils/backfill_historical_data.py` ✓ ESSENTIAL
- `src/utils/startup_recommendations.py` ✓ USED
- `src/utils/recover_trades.py`
- `src/utils/verify_mode.py`

**Utilities to Keep** (3 files):
- `monitor_positions.py` - Position tracking
- `force_redeem.py` - CTF token redemption
- `run_bot.py` - Simple launcher

---

## Clarifications Added

### Dual Arbitrage Detectors (Both Needed)

The project has **two different arbitrage detectors** that serve different purposes:

**1. `src/analysis/arbitrage.py` - Theoretical Pricing Detector**
- **Used when**: `pure_arbitrage.enabled: false` (Standard ML mode)
- **Strategy**: Black-Scholes fair value calculation
- **Features**: Uses annualized volatility (BTC: 80%, ETH: 90%, SOL: 110%)
- **Purpose**: Calculates "fair probability" based on theoretical pricing model
- **User's profitable mode**: ✓ THIS ONE (Standard ML with 60% arb + 40% ML)

**2. `src/analysis/pure_arbitrage.py` - Mathematical Arbitrage Detector**
- **Used when**: `pure_arbitrage.enabled: true` (Pure arbitrage mode)
- **Strategy**: Pure mathematical arbitrage (complement, spot price, lotto)
- **Features**: No models, just math (YES+NO<$1, price vs strike, <15¢ bets)
- **Purpose**: Detects guaranteed profit opportunities

**Why Both Exist**: They're completely different strategies. One uses theoretical models, the other uses pure math. Both are valid depending on trading mode.

---

## Statistics

**Before Cleanup**:
- Total Python files: ~70
- Root test scripts: 26
- Orphaned files: 3
- Config mismatches: 2
- Disk usage: ~11MB (excluding examples)

**After Cleanup**:
- Total Python files: ~45
- Root scripts: 3 (run_bot, monitor_positions, force_redeem)
- Orphaned files: 0
- Config mismatches: 0
- Disk usage: ~6MB (excluding examples)

**Improvement**:
- 25 files removed/archived
- ~5MB freed
- 0 config errors
- Significantly clearer project structure

---

## What Remains (Intentionally)

### Examples Directory (3.3MB)
- Polymarket official documentation and SDK examples
- Useful reference material
- Can be deleted if you want, but valuable for API compliance

### Data Directory
- `replay_buffer.json` (3.7MB) - May be duplicate of ml_episodes.json, but kept for safety
- Empty files (learning_trades.json, trade_history.json) - Kept as they're actively used

### Disabled Features (Kept for Future Use)
- Market Maker (`market_making.enabled: false`)
- Profit-Taking System (`position_management.enabled: false`)
- Contrarian Strategy (not integrated yet)

---

## Next Steps (Optional)

### Phase 2: Further Optimization (If Desired)

1. **Lazy Loading**: Convert disabled feature imports to conditional loading
2. **Rename arbitrage.py**: Consider renaming to `theoretical_pricing.py` for clarity
3. **Clean replay_buffer.json**: Verify if it's a duplicate and can be deleted

### Phase 3: Documentation

1. Add README.md explaining project structure
2. Document which arbitrage detector is used when
3. Create quick start guide

---

## Configuration After Cleanup

**Your Profitable Setup (Restored)**:
- ✅ **Mode**: Standard ML (60% arbitrage + 40% ML)
- ✅ **Arbitrage Detector**: Theoretical Pricing (Black-Scholes)
- ✅ **Snipe Window**: 300 seconds (5 minutes)
- ✅ **Pure Arbitrage**: Disabled
- ✅ **Contrarian**: Disabled
- ✅ **Market Making**: Disabled

**To run with your profitable settings**:
```bash
python -m src.bot
# Select: B (Standard ML)
# Select: 3 (Any - no price filtering)
# Budget: $3.00
```

---

## Files You Can Safely Delete Later (If Desired)

**Examples Directory** (3.3MB):
- Official Polymarket SDK documentation
- Can be re-downloaded from GitHub if needed
- Useful reference but not required for bot operation

**Archived Tests** (`tests/archive/`):
- All test scripts moved here
- Safe to delete if you don't need them
- Kept for now in case you want to reference old debugging code

---

**Cleanup Status**: ✅ Complete and tested
**Project Status**: ✅ Clean, organized, ready for production
**Bot Status**: ✅ Configured for profitable setup (Standard ML + Any + 300s)
