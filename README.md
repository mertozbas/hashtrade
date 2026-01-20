# HashTrade

**Your AI trading buddy that never sleeps.** ☕

While you're grabbing coffee, HashTrade is watching the charts. While you're sleeping, it's analyzing support levels. While you're living your life, it's remembering every trade, every pattern, every lesson learned.

This isn't another trading bot. It's an autonomous agent with memory, intuition, and the authority to act.

🚀 **[Try it Live](https://hashtrade.ai/)** | 📦 **[pip install hashtrade](https://pypi.org/project/hashtrade/)** | 📱 **Works on your phone**

![HashTrade](https://img.shields.io/badge/HashTrade-Vibe%20Trading-00ff88?style=for-the-badge&logo=bitcoin&logoColor=white)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://badge.fury.io/py/hashtrade.svg)](https://pypi.org/project/hashtrade/)

---

## 🌊 Vibe Trading

We call it **vibe trading** — let the agent feel the market.

Traditional bots follow rigid rules. HashTrade *thinks*. It wakes up, checks its notes from yesterday, looks at the charts, and asks itself: "Does this feel right?"

```
Agent wakes up...
→ "Last time BTC hit $67k support, it bounced. Let me check..."
→ Fetches current price: $67,050
→ "Support holding. Volume picking up. This feels like the move."
→ Buys 0.001 BTC
→ Logs: "Went long at support. Feeling good about this one."
```

No complicated indicators. No 47 parameters to tune. Just an agent that learns your style and vibes with the market.

---

## 💭 The Vision

We built HashTrade because we were tired of:

- Staring at charts at 3am
- Missing moves because we were busy
- Forgetting why we entered a trade
- Bots that can't adapt

**What if your trading assistant actually remembered things?** What if it could say "Hey, last time we saw this pattern, you said to be careful" — and actually mean it?

HashTrade is that assistant. It's not replacing your judgment. It's extending it. Your trading intuition, running 24/7, learning from every win and loss.

The dream: **Set your vibe, live your life, let the agent trade.**

---

## ✨ What You Get

| | |
|---|---|
| 🧠 **Memory** | Remembers every trade, note, and lesson. Picks up where you left off. |
| ⏰ **Always On** | Wakes up every 5-25 min to check the markets. You set the rhythm. |
| 💬 **Natural Chat** | "Buy some BTC" works. No code needed. |
| 📱 **Mobile First** | Install as an app. Trade from anywhere. |
| 🎨 **Your Style** | 7 themes. Make it yours. |
| 🔐 **Your Keys** | Credentials stay on your device. Always. |

---

## 🚀 Get Started in 60 Seconds

```bash
pip install hashtrade
```

```bash
# Pick your AI (choose one)
export MODEL_PROVIDER=bedrock      # AWS
export MODEL_PROVIDER=anthropic    # Claude  
export MODEL_PROVIDER=openai       # GPT
export MODEL_PROVIDER=ollama       # Free, local

# Add exchange keys (optional, for real trading)
export CCXT_API_KEY=your_key
export CCXT_SECRET=your_secret
```

```bash
hashtrade
```

Open [hashtrade.ai](https://hashtrade.ai) → Connect → Start vibing 🎵

---

## ⏰ The Rhythm

HashTrade follows a natural rhythm — busy when needed, chill when not:

```
Wake → Analyze → Trade (maybe) → Sleep 5 min
Wake → Analyze → Trade (maybe) → Sleep 10 min  
Wake → Analyze → Trade (maybe) → Sleep 20 min
Wake → Analyze → Trade (maybe) → Sleep 25 min
(repeat)
```

**Why this pattern?** Markets don't need constant watching. Big moves take time. The agent checks in, does its thing, and lets the market breathe.

You can:
- **Pause** when you want to take control
- **Trigger Now** when something's happening
- **Disable** to go fully manual
- **Change symbols** to watch different pairs

---

## 💬 Talk to It Like a Friend

```
"buy a little BTC"
"what do you think about ETH right now?"
"show me what happened while I was gone"
"add a note: I think we're in a bull flag"
"change the vibe to cyberpunk"
"how are we doing today?"
```

The agent gets it. No special syntax. No commands to memorize.

---

## 🛠️ Under the Hood

For the curious ones:

**Tools the agent uses:**
- `use_ccxt` — Talks to 100+ exchanges (Bybit, Binance, OKX, Kraken...)
- `history` — Its memory. Trades, notes, signals, all persisted.
- `interface` — Changes the UI, themes, renders custom widgets

**Architecture:**
```
Your Phone/Browser (PWA)
        ↓ WebSocket
HashTrade Server (Python)
        ↓
Strands Agent + Tools
        ↓
Exchanges via CCXT
```

**Stack:**
- [Strands Agents](https://github.com/strands-agents/strands-agents) — The brain
- [CCXT](https://github.com/ccxt/ccxt) — The exchange connector
- Vanilla JS frontend — No framework bloat, just vibes

---

## 🔒 Trust

- **Your keys, your device** — API credentials never leave your browser
- **Open source** — Read every line of code
- **Testnet first** — Use `CCXT_SANDBOX=true` to practice
- **Logs are clean** — Sensitive data is redacted

---

## 🎨 Make It Yours

Built-in vibes:
- `neon_green` — The classic
- `cyberpunk` — Magenta dreams
- `ocean_blue` — Calm waters
- `sunset_orange` — Warm energy
- `gold_luxury` — Big money energy
- `matrix_green` — Neo mode
- `dark_minimal` — Clean & simple

Or just say: *"make it purple"* — the agent figures it out.

---

## 🌍 Join the Vibe

**We're building this in public.**

- Share your setups
- Show us your wins (and losses, we learn from those too)
- Tell us what features you want

**Tag us on X: [#trade](https://x.com/search?q=%23trade)**

Post your HashTrade moments. Your autonomous agent making moves. Your custom themes. Your journey.

Let's vibe together. 🤝

---

## 📁 Project Layout

```
hashtrade/
├── server/
│   ├── main.py           # The brain
│   └── tools/            # What the agent can do
├── docs/
│   └── index.html        # The face (PWA)
└── data/
    └── history.jsonl     # The memory
```

---

## 🤝 Contributing

Found a bug? Have an idea? Want to add a tool?

PRs welcome. Issues welcome. Vibes welcome.

---

## 📄 License

Apache 2.0 — Use it, modify it, build on it.

---

<p align="center">
  <b>Trade autonomously. Sleep peacefully. Vibe eternally.</b>
  <br><br>
  <a href="https://hashtrade.ai">hashtrade.ai</a> · <a href="https://x.com/search?q=%23trade">#trade</a>
</p>
