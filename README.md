# Hashtrade - Autonomous Crypto Trading System

DevDuck-powered autonomous trading system with multiple AI-driven strategies for Bybit perpetual futures.

---

## Overview

Hashtrade is a collection of autonomous trading agents that use LLM (Large Language Model) capabilities to analyze markets and execute trades. Each agent implements a different trading strategy:

| Agent | Strategy | Risk | Max Positions | Timeframes |
|-------|----------|------|---------------|------------|
| `agent.py` | Smart Money Concepts (SMC) | 5% | 1 | 15m |
| `agent2.py` | Enhanced SMC + Partial Close | 10% | 3 | 15m |
| `agent3.py` | Liquidity Sweep (MTF) | 10% | 3 | 1H/15m/5m |
| `agent_4h_range.py` | 4H Range Breakout | 5% | 1 | 4H/5m |

---

## Agent Details

### agent.py - Smart Money Concepts Strategy

**Entry Criteria:**
- Clear market structure (uptrend/downtrend with HH/HL or LH/LL)
- EMA trend confirmation (20/50 EMA alignment)
- RSI not in extreme zones
- Valid entry zone (Order Block or Fair Value Gap)
- Entry score >= 5/10

**Risk Management:**
- 5% risk per trade
- Leverage: 5-30x (dynamic based on SL distance)
- Single position at a time
- Stop-loss at Order Block/FVG invalidation

**Usage:**
```bash
python agent.py           # Continuous trading (5-min cycles)
python agent.py --once    # Single cycle test
python agent.py --interval 10  # 10-minute cycles
```

---

### agent2.py - Enhanced SMC with Partial Close

**Improvements over agent.py:**
- Higher risk tolerance (10% per trade)
- Up to 3 concurrent positions
- Partial close capability (50% at +1% profit)
- Breakeven stop-loss after partial close

**Entry Criteria:**
- Same as agent.py (SMC-based)
- Score >= 5 required

**Position Management:**
1. Entry with 2x minimum quantity (enables 50% close)
2. At +1% profit: Close 50%, move SL to breakeven
3. Trail remaining 50% to TP2

**Minimum Quantities (for partial close):**
| Symbol | Min Qty |
|--------|---------|
| BTCUSDT | 0.002 |
| ETHUSDT | 0.02 |
| SOLUSDT | 0.2 |
| XRPUSDT | 20 |
| CRVUSDT | 20 |

**Usage:**
```bash
python agent2.py          # Continuous trading
python agent2.py --once   # Single cycle
```

---

### agent3.py - Liquidity Sweep Strategy (MTF)

**Strategy Overview:**
Multi-timeframe analysis focusing on liquidity sweeps - when price takes out swing highs/lows to grab stop-losses, then reverses.

**Timeframe Analysis:**
1. **1H (Higher Timeframe)**: Market bias + major liquidity pools
2. **15m (Medium Timeframe)**: Sweep detection + confirmation
3. **5m (Lower Timeframe)**: Entry timing refinement

**Entry Conditions (ALL required):**
- 1H bias aligns with sweep direction (or neutral)
- 15m liquidity sweep detected (wick beyond swing, close inside)
- Confirmation candle (reversal after sweep)
- R:R ratio >= 1.5

**Stop-Loss Placement:**
- Beyond the sweep wick with 0.2% buffer
- Dynamic (strategy-determined, not fixed %)

**Take-Profit:**
- Opposing liquidity pool from 1H timeframe
- Dynamic target based on market structure

**Position Management:**
1. At 1:1 R:R: Close 50%, move SL to breakeven
2. Trail remaining 50% toward TP
3. Full close at TP or structure break

**Partial Close Tracking:**
- File-based persistence (`data/partial_closed.json`)
- Prevents double partial closes
- Auto-cleans when positions close

**Usage:**
```bash
python agent3.py          # Continuous trading
python agent3.py --once   # Single cycle
```

---

### agent_4h_range.py - 4H Range Breakout Strategy

**Strategy Overview:**
Simple rule-based scalping using the first 4-hour candle of the day (New York time).

**Range Definition:**
- First 4H candle: 00:00-04:00 NY time
- Range High: Candle high
- Range Low: Candle low
- Automatically adjusts for EST/EDT timezone

**Entry Signal:**
1. 4H candle must be CLOSED
2. 5m candle CLOSES outside range (breakout)
3. 5m candle CLOSES back inside range (retest)
4. Must be candle CLOSES, not just wicks

**Trade Setup:**
- **LONG**: Price broke BELOW range, closed back INSIDE
- **SHORT**: Price broke ABOVE range, closed back INSIDE
- **Stop-Loss**: Breakout extreme
- **Take-Profit**: 2:1 R:R (fixed)

**Usage:**
```bash
python agent_4h_range.py          # Continuous trading
python agent_4h_range.py --once   # Single cycle
```

---

## Tools Reference

### Core Trading Tools

| Tool | Description |
|------|-------------|
| `balance.py` | Fetch and track account balance with history |
| `order.py` | Order lifecycle (open, close, list, close_all) |
| `bybit_v5.py` | Direct Bybit V5 API access |
| `ccxt_generic.py` | Universal CCXT wrapper for any exchange |

### Analysis Tools

| Tool | Description |
|------|-------------|
| `analysis.py` | SMC analysis (EMA, RSI, ATR, Order Blocks, FVG) |
| `liquidity.py` | Liquidity pools, sweep detection, MTF scan |
| `range_4h.py` | 4H range detection and breakout checking |

### Position Management

| Tool | Description |
|------|-------------|
| `position.py` | Position sizing, leverage selection, P&L management |

### Key Functions

**analysis.py:**
```python
analyze_market(symbol, timeframe="15")  # Full SMC analysis
check_entry_signal(symbol)              # Entry signal check
```

**liquidity.py:**
```python
find_liquidity_pools(symbol, timeframe="60")  # Find BSL/SSL
detect_liquidity_sweep(symbol, timeframe="15", lookback_candles=5)  # Sweep detection
mtf_liquidity_scan(symbol)              # Multi-TF analysis
get_opposing_liquidity(symbol, direction, entry_price)  # TP target
```

**position.py:**
```python
calculate_position(balance, entry, sl, risk_pct, leverage)  # Position sizing
calculate_position_dynamic(balance, entry, sl, tp, risk_pct, symbol)  # Dynamic sizing
select_leverage(sl_distance_pct, volatility)  # Optimal leverage
manage_position(action, entry, current, sl, qty, direction)  # Position mgmt v1
manage_position_v2(action, entry, current, sl, tp, qty, direction, partial_closed)  # v2 with partial
```

**range_4h.py:**
```python
get_4h_range(symbol)                    # Get today's 4H range
check_range_breakout(symbol, high, low) # Check for breakout setup
scan_4h_range_setups(symbols)           # Scan multiple pairs
```

---

## Configuration

### Environment Variables (.env)

```env
# Model Provider
MODEL_PROVIDER=anthropic
MODEL_ID=claude-sonnet-4-20250514

# API Keys
ANTHROPIC_API_KEY=sk-ant-...

# Bybit Credentials
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
BYBIT_TESTNET=false

# Agent Settings
CYCLE_INTERVAL=5  # minutes between cycles
```

### Supported Coins

All agents trade these pairs by default:
- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- CRVUSDT

---

## Project Structure

```
hashtrade/
├── agent.py              # SMC Strategy v1
├── agent2.py             # SMC Strategy v2 (partial close)
├── agent3.py             # Liquidity Sweep Strategy
├── agent_4h_range.py     # 4H Range Breakout
├── tools/
│   ├── __init__.py       # Tool exports
│   ├── balance.py        # Balance tracking
│   ├── order.py          # Order management
│   ├── bybit_v5.py       # Bybit V5 API
│   ├── ccxt_generic.py   # Universal CCXT
│   ├── analysis.py       # SMC analysis
│   ├── position.py       # Position sizing
│   ├── liquidity.py      # Liquidity analysis
│   └── range_4h.py       # 4H range tools
├── data/
│   ├── balance.json      # Balance history
│   └── partial_closed.json  # Partial close tracking
├── journal/              # Daily activity logs
├── .env                  # Configuration
└── requirements.txt      # Dependencies
```

---

## Installation

```bash
# Clone repository
git clone https://github.com/mertozbas/hashtrade.git
cd hashtrade

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Test tools
python -c "from tools import balance; print(balance(action='get'))"

# Run agent
python agent3.py --once  # Test single cycle
python agent3.py         # Start continuous trading
```

---

## Risk Warning

This is an autonomous trading system that executes real trades with real money. Use at your own risk.

- Always test on testnet first (`BYBIT_TESTNET=true`)
- Start with small position sizes
- Monitor the first few cycles manually
- Understand the strategy before deploying

---

## Strategy Comparison

| Feature | agent.py | agent2.py | agent3.py | agent_4h_range |
|---------|----------|-----------|-----------|----------------|
| Entry Type | SMC Zone | SMC Zone | Liquidity Sweep | Range Breakout |
| Analysis | Single TF | Single TF | Multi-TF | Dual TF |
| SL Method | OB/FVG | OB/FVG | Sweep Wick | Breakout Extreme |
| TP Method | Fixed % | Fixed % | Opposing Liquidity | Fixed 2:1 R:R |
| Partial Close | No | Yes (50%) | Yes (50%) | No |
| Position Tracking | Basic | Basic | File-based | Basic |
| Complexity | Low | Medium | High | Low |

---

## Changelog

### Latest Updates
- Fixed `agent_4h_range.py` position tracking bug
- Fixed `position.py` TP check order
- Added EDT/EST timezone detection for 4H range
- Added file-based partial close tracking in agent3
- Improved multi-candle sweep detection
- Removed hardcoded balance from prompts

---

**Built with:** DevDuck + Strands Agents + CCXT + Bybit V5 API
