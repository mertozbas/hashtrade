# Hashtrade Autonomous Trading Agent - Setup

## ✅ Created Files

### Tools (`/tools/`)
1. **balance.py** - Persistent balance tracking
   - `balance(action="get")` - Fetch and save current balance
   - `balance(action="history")` - View balance history
   - `balance(action="clear")` - Clear history
   - Data saved to: `data/balance.json`

2. **ccxt_generic.py** - Generic CCXT wrapper
   - `ccxt_generic(exchange="bybit", method="fetch_ticker", args='["BTC/USDT"]')`
   - Access to ALL CCXT methods
   - Supports all exchanges

3. **order.py** - Order management
   - `order(action="open", symbol="BTC/USDT:USDT", side="buy", amount=0.001)`
   - `order(action="list")` - List open orders
   - `order(action="close", order_id="123")` - Cancel order
   - `order(action="close_all")` - Close all positions

4. **journal** - From strands_tools (auto-imported)

### Agent
- **agent.py** - Autonomous trading agent using DevDuck
  - Auto-loads all tools via hot-reload
  - Trading cycle workflow
  - Risk management

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd /Users/macmert/hashtrade
source .venv/bin/activate  # If using existing venv
pip install -r requirements.txt
```

### 2. Test Tools
```bash
# Test balance tool
python3 -c "
from tools.balance import balance
result = balance(action='get')
print(result)
"

# Test ccxt_generic
python3 -c "
from tools.ccxt_generic import ccxt_generic
result = ccxt_generic(exchange='bybit', method='fetch_ticker', args='[\"BTC/USDT:USDT\"]')
print(result)
"

# Test order tool
python3 -c "
from tools.order import order
result = order(action='list')
print(result)
"
```

### 3. Run Agent

**Single cycle (test):**
```bash
python agent.py --once
```

**Continuous (default 5 min interval):**
```bash
python agent.py
```

**Custom interval:**
```bash
python agent.py --interval 10  # 10 minutes
```

## 🔧 How It Works

1. **Hot-Reload**: Tools in `/tools/` are auto-loaded by DevDuck
2. **Agent Workflow**:
   - Check balance (persistent in `data/balance.json`)
   - Analyze market (BTC, ETH, SOL)
   - List positions
   - Make decisions (risk: max 2% per trade)
   - Execute trades if confident
   - Log to journal

3. **Environment Variables** (`.env`):
   - BYBIT_API_KEY
   - BYBIT_API_SECRET
   - BYBIT_TESTNET (false for mainnet)
   - TELEGRAM_BOT_TOKEN (optional)
   - TELEGRAM_CHAT_ID (optional)

## 📊 Data Persistence

- **Balance History**: `data/balance.json`
- **Journal**: Managed by strands journal tool
- **State**: Managed by state_manager.py

## 🛡️ Safety Features

- Max 2% risk per trade
- Circuit breakers in state_manager
- Cautious autonomous decisions
- All activities logged

## 📝 Next Steps

1. Test tools individually
2. Run `agent.py --once` to verify workflow
3. Monitor first few cycles closely
4. Adjust interval based on strategy
5. Review logs and balance history regularly

## 🦆 DevDuck Integration

Agent uses DevDuck's:
- Tool hot-reload system
- Multi-model support
- Self-healing capabilities
- Knowledge base (if configured)

All tools are automatically available to the agent via DevDuck's tool registry.
