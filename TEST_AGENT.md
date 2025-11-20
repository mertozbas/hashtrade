# 🦆 Hashtrade Agent - Quick Test Guide

## ✅ System Created

**New Tools:**
- `tools/balance.py` - Balance tracking → `data/balance.json`
- `tools/ccxt_generic.py` - Full CCXT access
- `tools/order.py` - Order management

**Agent:**
- `agent.py` - Autonomous DevDuck-powered trading agent

## 🧪 Quick Tests

### Test 1: Balance Tool
```bash
cd /Users/macmert/hashtrade
python3 << 'PYTHON'
from tools.balance import balance
print(balance(action="get"))
PYTHON
```

### Test 2: Market Data (CCXT)
```bash
python3 << 'PYTHON'
from tools.ccxt_generic import ccxt_generic
print(ccxt_generic(exchange="bybit", method="fetch_ticker", args='["BTC/USDT:USDT"]'))
PYTHON
```

### Test 3: List Orders
```bash
python3 << 'PYTHON'
from tools.order import order
print(order(action="list"))
PYTHON
```

### Test 4: Run Agent (Single Cycle)
```bash
python agent.py --once
```

## 📊 Expected Workflow

Agent will:
1. ✅ Check balance → Save to `data/balance.json`
2. 📊 Analyze BTC/ETH/SOL markets
3. 📋 List current positions
4. 🤔 Make decisions (max 2% risk)
5. 📝 Log to journal

## 🚀 Start Autonomous Trading
```bash
# Continuous mode (5 min intervals)
python agent.py

# Custom interval (10 min)
python agent.py --interval 10
```

## 📁 Output Files
- `data/balance.json` - Balance history
- DevDuck logs - Tool usage history
- Journal entries - Trading activities

