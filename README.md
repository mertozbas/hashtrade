# HashTrade

A real-time cryptocurrency trading dashboard powered by [Strands Agents](https://github.com/strands-agents/strands-agents) with AI-driven trading assistance, multi-exchange support via CCXT, and dynamic UI customization.

🚀 **[Try the Live Dashboard](https://hashtrade.ai/)** | 📦 **[Install from PyPI](https://pypi.org/project/hashtrade/)**

![HashTrade Dashboard](https://img.shields.io/badge/HashTrade-Dashboard-00ff88?style=for-the-badge&logo=bitcoin&logoColor=white)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://badge.fury.io/py/hashtrade.svg)](https://pypi.org/project/hashtrade/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Dashboard](https://img.shields.io/badge/Live-Dashboard-brightgreen)](https://hashtrade.ai/)

## ✨ Features

- **🤖 AI Trading Assistant** - Natural language interface for trading operations
- **📊 Real-time Market Data** - Live OHLCV charts with WebSocket streaming
- **💱 Multi-Exchange Support** - Bybit, Binance, OKX, KuCoin, Kraken, Coinbase, and 100+ more via CCXT
- **🎨 Dynamic Theming** - 7 built-in themes + custom color picker
- **📜 Action History** - Persistent timeline of trades, signals, and events
- **🔧 Dynamic UI Rendering** - Agent can render cards, tables, charts, alerts on-the-fly
- **⚡ WebSocket Streaming** - Real-time agent responses with tool execution visibility

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     HashTrade Dashboard                          │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (docs/index.html)                                     │
│  ├── Market Graph (OHLCV Chart)                                 │
│  ├── History of Actions (Timeline)                              │
│  ├── Agent Screen (Chat with streaming)                         │
│  └── Theme Customization                                        │
├─────────────────────────────────────────────────────────────────┤
│  WebSocket Server (server/main.py)                              │
│  ├── Strands Agent with callback streaming                      │
│  ├── Direct CCXT for UI actions (fast path)                     │
│  └── History sync & persistence                                 │
├─────────────────────────────────────────────────────────────────┤
│  Tools                                                           │
│  ├── use_ccxt - Universal exchange interface                    │
│  ├── history  - Action logging & persistence                    │
│  └── interface - Dynamic UI & theme control                     │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Installation

```bash
# Install from PyPI
pip install hashtrade

# Or clone the repository
git clone https://github.com/mertozbas/hashtrade.git
cd hashtrade

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .
```

### Configuration

Set your model provider (choose one):

```bash
# AWS Bedrock (recommended)
export MODEL_PROVIDER=bedrock
# Requires AWS credentials configured

# Anthropic
export MODEL_PROVIDER=anthropic
export ANTHROPIC_API_KEY=your_key

# OpenAI
export MODEL_PROVIDER=openai
export OPENAI_API_KEY=your_key

# Ollama (local, free)
export MODEL_PROVIDER=ollama
export STRANDS_MODEL_ID=qwen3:1.7b
```

Set exchange credentials (optional, for trading):

```bash
# Generic CCXT credentials
export CCXT_EXCHANGE=bybit
export CCXT_API_KEY=your_api_key
export CCXT_SECRET=your_api_secret

# Or exchange-specific
export BYBIT_API_KEY=your_api_key
export BYBIT_API_SECRET=your_api_secret
```

### Running

```bash
# Start the server
python server/main.py

# Or use the CLI command
hashtrade
```

Then open the [HashTrade](https://hashtrade.ai/) in your browser and click **Connect**.

## 💬 Usage Examples

### Natural Language Trading

```
"buy 0.001 BTC"           → Creates market buy order
"sell 100 USDT of ETH"    → Market sell
"limit buy BTC at 50000"  → Limit order
"check balance"           → Shows account balances
"price of ETH"            → Gets current ticker
"show me ETH/USDT chart"  → Fetches OHLCV data
```

### Theme Customization

```
"change to cyberpunk theme"      → Magenta/cyan theme
"make it blue"                   → Ocean blue theme
"I want gold colors"             → Gold luxury theme
"change accent color to purple"  → Custom accent color
```

### Dynamic UI

The agent can render interactive components:

```
"show me a table of top 10 coins"
"display a progress bar for my portfolio"
"create an alert for when BTC hits 70000"
```

## 🛠️ Tools Reference

### use_ccxt

Universal CCXT client for cryptocurrency exchange operations.

**Actions:**
| Action | Description | Required Params |
|--------|-------------|-----------------|
| `list_exchanges` | List all 100+ supported exchanges | - |
| `describe` | Get exchange capabilities | `exchange` |
| `fetch_ticker` | Get ticker for symbol | `symbol` |
| `fetch_ohlcv` | Get OHLCV candles | `symbol`, `timeframe`, `limit` |
| `fetch_balance` | Get account balance | - |
| `create_order` | Create new order | `symbol`, `side`, `order_type`, `amount` |
| `cancel_order` | Cancel existing order | `order_id` |
| `multi_orderbook` | Compare orderbooks across exchanges | `exchanges`, `symbol` |

**Example:**
```python
use_ccxt(
    action="create_order",
    exchange="bybit",
    symbol="BTC/USDT",
    side="buy",
    order_type="limit",
    amount=0.001,
    price=50000
)
```

### history

Persist and fetch dashboard action history.

**Actions:**
| Action | Description | Params |
|--------|-------------|--------|
| `add` | Add history entry | `event_type`, `data` |
| `tail` | Get recent entries | `limit` |
| `clear` | Clear all history | - |

**Event Types:** `order`, `trade`, `signal`, `note`, `theme`

### interface

Dynamic UI rendering and theme control.

**Theme Actions:**
| Action | Description | Params |
|--------|-------------|--------|
| `set_theme` | Apply preset theme | `preset` |
| `update_color` | Change single color | `color_name`, `color_value` |
| `list_presets` | List available themes | - |
| `reset_theme` | Reset to default | - |

**Preset Themes:**
- `neon_green` (default)
- `cyberpunk` (magenta/cyan)
- `ocean_blue` (blue/teal)
- `sunset_orange` (orange/amber)
- `gold_luxury` (gold/black)
- `matrix_green` (pure green)
- `dark_minimal` (white/gray)

**UI Render Actions:**
| Action | Description | Params |
|--------|-------------|--------|
| `render_card` | Styled card component | `title`, `content` |
| `render_table` | Data table | `title`, `data` |
| `render_chart` | Bar chart widget | `title`, `data` |
| `render_alert` | Toast notification | `content`, `style` |
| `render_progress` | Progress indicator | `title`, `data` |
| `render_html` | Raw HTML injection | `html` |
| `clear_ui` | Clear dynamic components | `target` |

## 📁 Project Structure

```
hashtrade/
├── server/
│   ├── main.py              # WebSocket server & agent
│   ├── data/
│   │   └── history.jsonl    # Persisted history (auto-created)
│   └── tools/
│       ├── use_ccxt.py      # CCXT exchange tool
│       ├── history.py       # Action history tool
│       └── interface.py     # UI/theme tool
├── docs/
│   └── index.html           # Dashboard frontend (GitHub Pages)
├── pyproject.toml           # Package configuration
└── README.md
```

## ⚙️ Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DASH_HOST` | Server bind host | `127.0.0.1` |
| `DASH_PORT` | Server port | `8090` |
| `DASH_EXCHANGE` | Default exchange | `bybit` |
| `DASH_DATA_DIR` | Data directory | `./data` |
| `DASH_CUSTOM_PROMPT` | Custom system prompt | - |
| `DASH_CUSTOM_PROMPT_FILE` | Path to custom prompt file | - |
| `MODEL_PROVIDER` | LLM provider | auto-detect |
| `STRANDS_MODEL_ID` | Model identifier | provider-specific |
| `CCXT_EXCHANGE` | Default exchange for CCXT | - |
| `CCXT_API_KEY` | API key | - |
| `CCXT_SECRET` | API secret | - |
| `CCXT_SANDBOX` | Enable sandbox mode | `false` |
| `CCXT_DEFAULT_TYPE` | Market type (spot/swap) | - |

### Frontend Settings

The dashboard stores settings in localStorage:
- Exchange selection
- API credentials (stored locally only)
- Symbol and timeframe
- Live update interval
- Theme preferences

## 🔒 Security Notes

- API credentials are stored in browser localStorage only
- Server logs redact sensitive information
- Use sandbox/testnet mode for development: `CCXT_SANDBOX=true`
- Never commit API keys to version control

## 🧪 Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Adding New Tools

1. Create tool file in `server/tools/`
2. Use `@tool` decorator from strands
3. Import and add to agent in `server/main.py`

```python
from strands import tool

@tool
def my_tool(action: str, param: str = None) -> dict:
    """Tool description for the agent."""
    # Implementation
    return {"status": "success", "content": [{"text": "result"}]}
```

### Custom System Prompt

Create a file with your custom instructions:

```bash
export DASH_CUSTOM_PROMPT_FILE=/path/to/my_prompt.txt
```

Or set directly:

```bash
export DASH_CUSTOM_PROMPT="Always confirm orders. Focus on risk management."
```

## 📄 License

Apache License 2.0

## 🙏 Acknowledgments

- [Strands Agents](https://github.com/strands-agents/strands-agents) - AI agent framework
- [CCXT](https://github.com/ccxt/ccxt) - Cryptocurrency exchange library
- [websockets](https://websockets.readthedocs.io/) - WebSocket implementation

---

**#trade**
