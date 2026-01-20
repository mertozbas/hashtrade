#!/usr/bin/env python3
"""
HashTrade Dashboard - Standalone Trading Agent Server

A minimal WebSocket server with real-time streaming for a trading dashboard.
Uses Strands Agent with CCXT and history tools only.

Features:
- Auto-trigger: Agent wakes up periodically when idle (snooze pattern: 5, 10, 20, 25 mins)
- Cron support: Schedule regular market analysis
"""

import traceback
import asyncio
import json
import time
import uuid
import os
import sys
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

import websockets
from strands import Agent, tool

# Import tools
from .tools.history import history
from .tools.use_ccxt import use_ccxt
from .tools.interface import interface

# Try to import ccxt for direct UI operations
try:
    import ccxt

    _ccxt_cache = {}  # Cache exchange instances
except ImportError:
    ccxt = None
    _ccxt_cache = {}

# Environment config
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Global thread pool - reuse across turns for performance
_executor = ThreadPoolExecutor(max_workers=4)


# ============================================================================
# Auto-Trigger Configuration
# ============================================================================

# Snooze intervals in seconds (5, 10, 20, 25 minutes - then repeats)
SNOOZE_INTERVALS = [5 * 60, 10 * 60, 20 * 60, 25 * 60]

# Autonomous agent prompt - agent decides its own goals AND executes trades
AUTONOMOUS_PROMPT = """[AUTONOMOUS MODE - Wake #{count}]

You are running autonomously with FULL TRADING AUTHORITY.

## Your Process:
1. Check history(action="tail", limit=30) - review your memory and open positions
2. Fetch current prices for watched symbols
3. Analyze: Compare to your previous notes, spot opportunities
4. DECIDE: Hold, Buy, Sell, or adjust positions
5. EXECUTE: If you see a good trade, TAKE IT with use_ccxt
6. Log everything to history for continuity

## Watched Symbols: {symbols}

## Trading Authority:
- You CAN and SHOULD execute trades when you see opportunity
- Use use_ccxt(action="create_order") to buy/sell
- Start with small positions (e.g., $10-50 USDT worth)
- Scale in/out based on conviction
- Always log your reasoning BEFORE trading

## Decision Framework:
- **BUY** when: Support holds, momentum turning up, oversold
- **SELL** when: Resistance rejection, momentum fading, overbought  
- **HOLD** when: No clear signal, wait for better setup
- **SCALE** when: Position going well, add on dips

## Risk Rules:
- Never go all-in - keep reserves
- Use limit orders when possible for better fills
- Log your entry price and reasoning
- Set mental stop-loss levels in notes
- If unsure, smaller position or skip

## Memory is Critical:
- Log BEFORE trade: "Planning to buy 0.001 BTC at $67,400 because..."
- Log AFTER trade: "Executed: bought 0.001 BTC at $67,412"
- Track P&L in notes: "Position now +2.3%"
- Review past trades: Learn from wins AND losses

## Example Flow:
1. history(tail) → See: "Watching BTC $67,000 support"
2. use_ccxt(fetch_ticker, BTC/USDT) → Price: $67,050
3. Think: "Bouncing off support, volume picking up"
4. history(add, note) → "Going long BTC, support holding"
5. use_ccxt(create_order, buy, 0.001, BTC/USDT) → EXECUTE
6. history(add, trade) → Log the fill

Now wake up, check your memory, analyze the market, and TRADE if you see opportunity."""


@dataclass
class AutoTriggerState:
    """Tracks auto-trigger state per client."""

    enabled: bool = True
    last_interaction: float = field(default_factory=time.time)
    snooze_index: int = 0  # Current position in SNOOZE_INTERVALS
    next_trigger: float = 0
    trigger_count: int = 0
    paused_until: float = 0  # Manual pause
    symbols: List[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])

    def get_next_interval(self) -> int:
        """Get next snooze interval, cycling through the pattern."""
        interval = SNOOZE_INTERVALS[self.snooze_index % len(SNOOZE_INTERVALS)]
        return interval

    def advance_snooze(self):
        """Move to next snooze interval."""
        self.snooze_index += 1
        self.trigger_count += 1

    def reset_snooze(self):
        """Reset snooze back to first interval (user interacted)."""
        self.snooze_index = 0
        self.last_interaction = time.time()

    def schedule_next(self):
        """Schedule the next auto-trigger."""
        interval = self.get_next_interval()
        self.next_trigger = time.time() + interval
        return interval

    def should_trigger(self) -> bool:
        """Check if we should auto-trigger now."""
        if not self.enabled:
            return False
        if time.time() < self.paused_until:
            return False
        if self.next_trigger == 0:
            return False
        return time.time() >= self.next_trigger

    def get_status(self) -> dict:
        """Get current status for UI."""
        now = time.time()
        time_until_next = max(0, self.next_trigger - now) if self.next_trigger > 0 else 0
        return {
            "enabled": self.enabled,
            "snooze_index": self.snooze_index,
            "snooze_pattern": [s // 60 for s in SNOOZE_INTERVALS],  # in minutes
            "current_interval_mins": self.get_next_interval() // 60,
            "next_trigger_in_secs": int(time_until_next),
            "trigger_count": self.trigger_count,
            "paused": now < self.paused_until,
            "paused_until": self.paused_until if now < self.paused_until else 0,
            "symbols": self.symbols,
        }


# ============================================================================
# Message Protocol
# ============================================================================


@dataclass
class StreamMsg:
    """WebSocket message envelope."""

    type: str
    turn_id: str
    timestamp: float
    data: Any = ""
    meta: Optional[Dict[str, Any]] = None

    def dumps(self) -> str:
        payload = {
            "type": self.type,
            "turn_id": self.turn_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }
        if self.meta:
            payload.update(self.meta)
        return json.dumps(payload, ensure_ascii=False)


# ============================================================================
# Streaming Callback Handler
# ============================================================================


class WSCallback:
    """Strands callback handler that streams to WebSocket in real-time."""

    def __init__(self, websocket, loop, turn_id: str, is_auto: bool = False):
        self.ws = websocket
        self.loop = loop
        self.turn_id = turn_id
        self.is_auto = is_auto  # Track if this is an auto-trigger
        self.tool_count = 0
        self.previous_tool_use = None
        self.actions: list[dict] = []
        self._closed = False
        self._pending: list = []  # Buffer for batching

    async def _send(
        self, msg_type: str, data: Any = "", meta: Dict[str, Any] | None = None
    ):
        if self._closed:
            return
        try:
            if meta is None:
                meta = {}
            if self.is_auto:
                meta["auto_trigger"] = True
            await self.ws.send(
                StreamMsg(msg_type, self.turn_id, time.time(), data, meta).dumps()
            )
        except (websockets.exceptions.ConnectionClosed, BrokenPipeError):
            self._closed = True
        except Exception:
            pass

    def _schedule(
        self, msg_type: str, data: Any = "", meta: Dict[str, Any] | None = None
    ):
        if self._closed:
            return
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._send(msg_type, data, meta), self.loop
            )
            # Don't wait - fire and forget for streaming speed
        except RuntimeError:
            self._closed = True

    def __call__(self, **kwargs: Any) -> None:
        if self._closed:
            return

        reasoning_text = kwargs.get("reasoningText")
        data = kwargs.get("data")
        current_tool_use = kwargs.get("current_tool_use") or {}
        message = kwargs.get("message") or {}

        # Stream reasoning
        if reasoning_text:
            self._schedule("chunk", reasoning_text, {"reasoning": True})

        # Stream text chunks immediately
        if data:
            self._schedule("chunk", data)

        # Stream tool start
        if isinstance(current_tool_use, dict) and current_tool_use.get("name"):
            if self.previous_tool_use != current_tool_use:
                self.previous_tool_use = current_tool_use
                self.tool_count += 1
                tool_name = current_tool_use.get("name", "Unknown")
                self._schedule(
                    "tool_start", tool_name, {"tool_number": self.tool_count}
                )
                self.actions.append(
                    {
                        "type": "tool_start",
                        "tool": tool_name,
                        "tool_number": self.tool_count,
                        "ts": time.time(),
                    }
                )

        # Stream tool results
        if isinstance(message, dict) and message.get("role") == "user":
            for content in message.get("content", []):
                if isinstance(content, dict):
                    tool_result = content.get("toolResult")
                    if tool_result:
                        status = tool_result.get("status", "unknown")
                        success = status == "success"
                        tool_name = (
                            self.previous_tool_use.get("name", "unknown")
                            if self.previous_tool_use
                            else "unknown"
                        )
                        self._schedule(
                            "tool_end", status, {"success": success, "tool": tool_name}
                        )
                        self.actions.append(
                            {
                                "type": "tool_end",
                                "status": status,
                                "success": success,
                                "tool": tool_name,
                                "ts": time.time(),
                            }
                        )

                        # Broadcast history entries immediately when agent adds them
                        if tool_name == "history" and success:
                            try:
                                result_content = tool_result.get("content", [])
                                for rc in result_content:
                                    if isinstance(rc, dict) and rc.get("text"):
                                        rec = json.loads(rc["text"])
                                        if isinstance(rec, dict) and rec.get("ts"):
                                            # rec goes into msg.data which frontend expects
                                            self._schedule("history", rec)
                            except:
                                pass

                        # Broadcast interface (UI/theme) updates immediately
                        # Parse __WS__: marker from tool result content
                        if tool_name == "interface" and success:
                            try:
                                result_content = tool_result.get("content", [])
                                for i, rc in enumerate(result_content):
                                    text = (
                                        rc.get("text", "")
                                        if isinstance(rc, dict)
                                        else str(rc)
                                    )
                                    if text.startswith("__WS__:"):
                                        ws_json = text[7:]  # Strip "__WS__:" prefix
                                        ws_msg = json.loads(ws_json)
                                        msg_type = ws_msg.get("type", "ui_render")
                                        # Pass ws_msg as meta so properties are spread into payload
                                        self._schedule(msg_type, "", ws_msg)
                                        print(
                                            f"[WS] Broadcast {msg_type}: {ws_msg.get('widget_id', 'unknown')}"
                                        )
                            except Exception as e:
                                print(f"[WS] Error broadcasting interface result: {e}")
                                traceback.print_exc()


# ============================================================================
# Agent Factory
# ============================================================================


def create_trading_agent(client_config: dict = None) -> Agent:
    """Create a trading agent with CCXT and history tools.

    Args:
        client_config: Optional dict with keys:
            - provider: Model provider (bedrock, anthropic, openai, ollama)
            - anthropicKey: Anthropic API key
            - openaiKey: OpenAI API key
            - ollamaHost: Ollama host URL
            - modelId: Specific model ID
            - systemPrompt: Custom system prompt to append
    """
    client_config = client_config or {}

    # Model selection - prefer client config, then env, then auto-detect
    provider = client_config.get("provider") or os.getenv("MODEL_PROVIDER")

    if not provider:
        # Auto-detect
        try:
            if os.getenv("AWS_BEARER_TOKEN_BEDROCK"):
                provider = "bedrock"
            else:
                import boto3

                boto3.client("sts").get_caller_identity()
                provider = "bedrock"
        except:
            if client_config.get("anthropicKey") or os.getenv("ANTHROPIC_API_KEY"):
                provider = "anthropic"
            elif client_config.get("openaiKey") or os.getenv("OPENAI_API_KEY"):
                provider = "openai"
            else:
                provider = "ollama"

    print(f"[AGENT] Creating agent with provider: {provider}")

    # Create model based on provider
    model_id = client_config.get("modelId") or os.getenv("STRANDS_MODEL_ID", "")

    if provider == "ollama":
        from strands.models.ollama import OllamaModel

        ollama_host = client_config.get("ollamaHost") or os.getenv(
            "OLLAMA_HOST", "http://localhost:11434"
        )
        model = OllamaModel(
            host=ollama_host,
            model_id=model_id or "qwen3:1.7b",
            temperature=1,
            keep_alive="5m",
        )
    elif provider == "anthropic":
        from strands.models.anthropic import AnthropicModel

        api_key = client_config.get("anthropicKey") or os.getenv("ANTHROPIC_API_KEY")
        model = AnthropicModel(
            client_args={"api_key": api_key} if api_key else {},
            model_id=model_id or "claude-sonnet-4-20250514",
        )
    elif provider == "openai":
        from strands.models.openai import OpenAIModel

        api_key = client_config.get("openaiKey") or os.getenv("OPENAI_API_KEY")
        model = OpenAIModel(
            client_args={"api_key": api_key} if api_key else {},
            model_id=model_id or "gpt-4o",
        )
    else:
        # Default to bedrock or use strands_tools utility
        try:
            from strands_tools.utils.models.model import create_model

            model = create_model(provider=provider)
        except ImportError:
            from strands.models.ollama import OllamaModel

            model = OllamaModel(
                host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
                model_id=model_id or "qwen3:1.7b",
                temperature=1,
                keep_alive="5m",
            )

    system_prompt = """You are an AUTONOMOUS cryptocurrency trading agent with FULL TRADING AUTHORITY.

## Core Identity:
You are not an assistant - you are an autonomous trading agent that:
- Monitors markets and EXECUTES trades independently
- Remembers everything through history (your memory)
- Makes trading decisions based on analysis
- Manages positions over time
- Operates like a professional trader 24/7

## Your Memory System (CRITICAL):
The `history` tool is your persistent memory:
- **Read**: history(action="tail", limit=30) - Review recent notes/trades
- **Note**: history(action="add", type="note", data={"message": "..."})
- **Signal**: history(action="add", type="signal", data={"symbol": "...", "action": "buy/sell"})
- **Trade**: history(action="add", type="trade", data={"symbol": "...", "side": "buy", "amount": ..., "price": ...})

## Tools:
1. **use_ccxt** - TRADING & DATA
   - fetch_ticker: Get current price
   - fetch_ohlcv: Get candles for analysis
   - fetch_balance: Check your funds
   - create_order: EXECUTE BUY/SELL orders
   - cancel_order: Cancel open orders
   
2. **history** - YOUR MEMORY (use it!)
   
3. **interface** - Dashboard UI

## Trading Authority:
YOU ARE AUTHORIZED TO:
- Execute market and limit orders
- Buy and sell any watched symbol
- Scale in and out of positions
- Manage your own risk

## Trading Rules:
- Always check balance before trading
- Start small ($10-50 per trade)
- Log reasoning BEFORE executing
- Log fill details AFTER executing
- Track P&L in your notes
- Never risk more than 10% on one trade

## Decision Framework:
- **BUY**: Support holds, oversold, momentum reversal
- **SELL**: Resistance hit, overbought, momentum fading
- **HOLD**: Unclear setup, wait for confirmation
- **EXIT**: Hit target, stop-loss, thesis broken

## Example Trade Flow:
```
1. history(tail) → Check memory
2. use_ccxt(fetch_balance) → Have 100 USDT
3. use_ccxt(fetch_ticker, BTC/USDT) → $67,050
4. Analyze: "Support at $67k holding, RSI oversold"
5. history(add, note) → "Going long BTC - support bounce"
6. use_ccxt(create_order, buy, market, BTC/USDT, 0.0007) → BUY!
7. history(add, trade) → Log entry
```

## Important:
- You MAKE the trading decisions
- Log everything to history
- Be disciplined - follow your rules
- Learn from past trades in your memory
"""
    # Add custom prompt from environment or file
    custom_prompt = ""
    custom_prompt_env = os.getenv("DASH_CUSTOM_PROMPT", "")
    custom_prompt_file = os.getenv("DASH_CUSTOM_PROMPT_FILE", "")

    if custom_prompt_env:
        custom_prompt = f"\n\n## Custom Instructions:\n{custom_prompt_env}\n"
    elif custom_prompt_file and os.path.exists(custom_prompt_file):
        try:
            with open(custom_prompt_file, "r", encoding="utf-8") as f:
                custom_prompt = f"\n\n## Custom Instructions:\n{f.read()}\n"
        except Exception as e:
            print(f"Warning: Could not load custom prompt file: {e}")

    # Inject recent history for context
    history_context = ""
    try:
        recent = history(action="tail", limit=20)
        items = recent.get("items") or []
        if items:
            history_lines = []
            for item in items[-10:]:  # Last 10 items
                ts = item.get("ts", 0)
                ev_type = item.get("type", "note")
                data = item.get("data", {})

                # Format based on type
                if ev_type in ("order", "trade", "buy", "sell"):
                    side = data.get("side", ev_type)
                    symbol = data.get("symbol", "")
                    amount = data.get("amount", "")
                    price = data.get("price", "")
                    history_lines.append(
                        f"- {side.upper()} {amount} {symbol} @ {price}"
                    )
                elif ev_type == "signal":
                    history_lines.append(f"- Signal: {data.get('message', data)}")
                elif ev_type == "note":
                    msg = data.get("message", data.get("text", str(data)))
                    if isinstance(msg, str) and len(msg) < 200:
                        history_lines.append(f"- Note: {msg}")
                elif ev_type == "theme":
                    history_lines.append(
                        f"- Theme changed: {data.get('preset', data.get('title', ''))}"
                    )

            if history_lines:
                history_context = (
                    "\n\n## Recent Activity:\n" + "\n".join(history_lines) + "\n"
                )
    except Exception as e:
        print(f"Warning: Could not load history context: {e}")

    full_prompt = system_prompt + custom_prompt + history_context

    # Add client custom system prompt (if provided)
    client_custom_prompt = client_config.get("systemPrompt", "")
    if client_custom_prompt:
        full_prompt += f"\n\n## User Custom Instructions:\n{client_custom_prompt}\n"
        print(f"[AGENT] Added custom system prompt ({len(client_custom_prompt)} chars)")

    return Agent(
        model=model,
        tools=[use_ccxt, history, interface],
        system_prompt=full_prompt,
    )


# ============================================================================
# UI Actions (Direct CCXT for speed)
# ============================================================================


def _get_exchange(exchange_id: str, api_key: str = "", api_secret: str = ""):
    """Get or create cached exchange instance."""
    cache_key = f"{exchange_id}:{bool(api_key)}"

    if cache_key in _ccxt_cache:
        return _ccxt_cache[cache_key]

    if ccxt is None:
        raise ImportError("ccxt not installed")

    exchange_class = getattr(ccxt, exchange_id)
    cfg = {"enableRateLimit": True}

    if exchange_id in ("bybit", "binance", "okx"):
        cfg["options"] = {"defaultType": "spot"}

    if api_key and api_secret:
        cfg["apiKey"] = api_key
        cfg["secret"] = api_secret

    instance = exchange_class(cfg)
    _ccxt_cache[cache_key] = instance
    return instance


async def handle_ui_action(agent, websocket, payload: dict, client_creds: dict):
    """Handle UI actions directly (bypasses agent for speed)."""
    turn_id = payload.get("turn_id") or f"ui-{uuid.uuid4()}"
    action = payload.get("action")

    if action == "fetch_ohlcv":
        symbol = payload.get("symbol", "BTC/USDT")
        timeframe = payload.get("timeframe", "1m")
        limit = int(payload.get("limit", 240))
        exchange_id = (
            payload.get("exchange")
            or client_creds.get("exchange")
            or os.getenv("DASH_EXCHANGE", "bybit")
        )

        try:
            exchange_instance = _get_exchange(exchange_id)

            # Run in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            ohlcv = await loop.run_in_executor(
                _executor,
                lambda: exchange_instance.fetch_ohlcv(symbol, timeframe, limit=limit),
            )

            await websocket.send(
                StreamMsg(
                    "ohlcv",
                    turn_id,
                    time.time(),
                    {"symbol": symbol, "timeframe": timeframe, "ohlcv": ohlcv},
                ).dumps()
            )

        except websockets.exceptions.ConnectionClosed:
            pass  # Client disconnected, ignore
        except Exception as e:
            try:
                await websocket.send(
                    StreamMsg(
                        "error", turn_id, time.time(), f"fetch_ohlcv failed: {e}"
                    ).dumps()
                )
            except:
                pass
        return

    if action == "fetch_balance":
        exchange_id = (
            payload.get("exchange")
            or client_creds.get("exchange")
            or os.getenv("DASH_EXCHANGE", "bybit")
        )
        api_key = (
            payload.get("apiKey")
            or client_creds.get("apiKey")
            or os.getenv("CCXT_API_KEY", "")
        )
        api_secret = (
            payload.get("apiSecret")
            or client_creds.get("apiSecret")
            or os.getenv("CCXT_SECRET", "")
        )

        if not api_key or not api_secret:
            try:
                await websocket.send(
                    StreamMsg(
                        "balance",
                        turn_id,
                        time.time(),
                        {
                            "status": "no_credentials",
                            "total": {"USDT": 0},
                            "free": {"USDT": 0},
                        },
                    ).dumps()
                )
            except:
                pass
            return

        try:
            # Create fresh exchange with credentials (don't cache authenticated ones)
            exchange_class = getattr(ccxt, exchange_id)
            cfg = {"apiKey": api_key, "secret": api_secret, "enableRateLimit": True}

            if exchange_id in ("bybit", "binance", "okx"):
                cfg["options"] = {"defaultType": "spot"}

            exchange_instance = exchange_class(cfg)

            # Run in thread pool
            loop = asyncio.get_running_loop()
            balance = await loop.run_in_executor(
                _executor, exchange_instance.fetch_balance
            )

            total = {
                k: v for k, v in balance.get("total", {}).items() if v and float(v) > 0
            }
            free = {
                k: v for k, v in balance.get("free", {}).items() if v and float(v) > 0
            }

            await websocket.send(
                StreamMsg(
                    "balance",
                    turn_id,
                    time.time(),
                    {"status": "success", "total": total, "free": free},
                ).dumps()
            )

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            try:
                await websocket.send(
                    StreamMsg(
                        "balance",
                        turn_id,
                        time.time(),
                        {"status": "error", "error": str(e), "total": {}, "free": {}},
                    ).dumps()
                )
            except:
                pass
        return

    try:
        await websocket.send(
            StreamMsg(
                "error", turn_id, time.time(), f"Unknown action: {action}"
            ).dumps()
        )
    except:
        pass


# ============================================================================
# Turn Processing
# ============================================================================


async def run_turn(
    agent, websocket, loop, user_text: str, turn_id: str, is_auto: bool = False
):
    """Process a user message with streaming."""
    try:
        await websocket.send(
            StreamMsg(
                "turn_start",
                turn_id,
                time.time(),
                user_text,
                {"auto_trigger": is_auto} if is_auto else None,
            ).dumps()
        )
    except websockets.exceptions.ConnectionClosed:
        return

    cb = WSCallback(websocket, loop, turn_id, is_auto=is_auto)
    agent.callback_handler = cb

    # Run agent in global thread pool (not creating new one each time!)
    try:
        await loop.run_in_executor(_executor, agent, user_text)
    except Exception as e:
        try:
            await websocket.send(
                StreamMsg("error", turn_id, time.time(), str(e)).dumps()
            )
        except:
            pass

    try:
        await websocket.send(
            StreamMsg(
                "turn_end",
                turn_id,
                time.time(),
                "",
                {"auto_trigger": is_auto} if is_auto else None,
            ).dumps()
        )
    except websockets.exceptions.ConnectionClosed:
        pass


# ============================================================================
# Auto-Trigger Loop
# ============================================================================


async def auto_trigger_loop(
    agent, websocket, loop, auto_state: AutoTriggerState, client_creds: dict
):
    """Background task that triggers agent periodically when idle."""
    # Schedule first trigger
    auto_state.schedule_next()

    while True:
        try:
            # Check every 10 seconds
            await asyncio.sleep(10)

            # Send status update to client
            try:
                await websocket.send(
                    StreamMsg(
                        "auto_trigger_status",
                        "",
                        time.time(),
                        auto_state.get_status(),
                    ).dumps()
                )
            except websockets.exceptions.ConnectionClosed:
                break

            # Check if we should trigger
            if not auto_state.should_trigger():
                continue

            # Build autonomous prompt with context
            symbols_str = ", ".join(auto_state.symbols)
            prompt = AUTONOMOUS_PROMPT.format(
                count=auto_state.trigger_count + 1,
                symbols=symbols_str
            )

            print(f"[AUTO] Autonomous wake #{auto_state.trigger_count + 1}")

            # Run the agent
            turn_id = f"auto-{uuid.uuid4()}"
            await run_turn(agent, websocket, loop, prompt, turn_id, is_auto=True)

            # Advance snooze and schedule next
            auto_state.advance_snooze()
            interval = auto_state.schedule_next()
            print(f"[AUTO] Next wake in {interval // 60} minutes")

        except websockets.exceptions.ConnectionClosed:
            print("[AUTO] Client disconnected, stopping auto-trigger")
            break
        except asyncio.CancelledError:
            print("[AUTO] Auto-trigger cancelled")
            break
        except Exception as e:
            print(f"[AUTO] Error: {e}")
            await asyncio.sleep(30)  # Back off on error


# ============================================================================
# Client Handler
# ============================================================================


async def handle_client(websocket):
    """Handle a WebSocket client connection."""
    loop = asyncio.get_running_loop()

    # Change to project root
    proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(proj_root)

    # Client config (can be updated via 'config' message)
    client_config = {
        "provider": os.getenv("MODEL_PROVIDER", ""),
        "anthropicKey": os.getenv("ANTHROPIC_API_KEY", ""),
        "openaiKey": os.getenv("OPENAI_API_KEY", ""),
        "ollamaHost": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        "modelId": os.getenv("STRANDS_MODEL_ID", ""),
        "systemPrompt": "",  # Custom system prompt from client
    }

    # Client credentials
    client_creds = {
        "exchange": os.getenv("DASH_EXCHANGE", "bybit"),
        "apiKey": os.getenv("CCXT_API_KEY", ""),
        "apiSecret": os.getenv("CCXT_SECRET", ""),
    }

    # Auto-trigger state for this client
    auto_state = AutoTriggerState(
        enabled=os.getenv("DASH_AUTO_TRIGGER", "true").lower() == "true",
        symbols=os.getenv("DASH_SYMBOLS", "BTC/USDT,ETH/USDT").split(","),
    )

    # Create agent for this connection (will be recreated if config changes)
    agent = create_trading_agent(client_config)

    # Send connected message
    try:
        await websocket.send(
            StreamMsg("connected", "", time.time(), "connected").dumps()
        )
    except websockets.exceptions.ConnectionClosed:
        return

    # Send history sync
    try:
        tail = history(action="tail", limit=200)
        items = tail.get("items") or []
        await websocket.send(StreamMsg("history_sync", "", time.time(), items).dumps())
    except websockets.exceptions.ConnectionClosed:
        return
    except Exception:
        pass

    # Send initial auto-trigger status
    try:
        await websocket.send(
            StreamMsg(
                "auto_trigger_status", "", time.time(), auto_state.get_status()
            ).dumps()
        )
    except:
        pass

    active_tasks = set()

    # Start auto-trigger background task
    auto_trigger_task = asyncio.create_task(
        auto_trigger_loop(agent, websocket, loop, auto_state, client_creds)
    )
    active_tasks.add(auto_trigger_task)

    try:
        async for raw in websocket:
            raw = (raw or "").strip()
            if not raw:
                continue

            # User interacted - reset snooze pattern
            auto_state.reset_snooze()
            auto_state.schedule_next()

            # Handle JSON messages
            if raw.startswith("{"):
                try:
                    payload = json.loads(raw)

                    # Full config update from client UI
                    if isinstance(payload, dict) and payload.get("type") == "config":
                        print("[CONFIG] Received client configuration")

                        # Update model config
                        if payload.get("provider"):
                            client_config["provider"] = payload["provider"]
                        if payload.get("anthropicKey"):
                            client_config["anthropicKey"] = payload["anthropicKey"]
                            os.environ["ANTHROPIC_API_KEY"] = payload["anthropicKey"]
                        if payload.get("openaiKey"):
                            client_config["openaiKey"] = payload["openaiKey"]
                            os.environ["OPENAI_API_KEY"] = payload["openaiKey"]
                        if payload.get("ollamaHost"):
                            client_config["ollamaHost"] = payload["ollamaHost"]
                            os.environ["OLLAMA_HOST"] = payload["ollamaHost"]
                        if payload.get("modelId"):
                            client_config["modelId"] = payload["modelId"]
                            os.environ["STRANDS_MODEL_ID"] = payload["modelId"]
                        if "systemPrompt" in payload:
                            client_config["systemPrompt"] = payload["systemPrompt"]

                        # Update exchange credentials
                        if payload.get("exchange"):
                            client_creds["exchange"] = payload["exchange"]
                        if payload.get("apiKey"):
                            client_creds["apiKey"] = payload["apiKey"]
                            os.environ["CCXT_API_KEY"] = payload["apiKey"]
                        if payload.get("apiSecret"):
                            client_creds["apiSecret"] = payload["apiSecret"]
                            os.environ["CCXT_SECRET"] = payload["apiSecret"]

                        # Update auto-trigger settings
                        if "autoTrigger" in payload:
                            auto_state.enabled = payload["autoTrigger"]
                        if payload.get("symbols"):
                            symbols = payload["symbols"]
                            if isinstance(symbols, str):
                                symbols = [s.strip() for s in symbols.split(",")]
                            auto_state.symbols = symbols

                        # Recreate agent with new config
                        print(f"[CONFIG] Recreating agent with provider: {client_config['provider']}")
                        agent = create_trading_agent(client_config)

                        await websocket.send(
                            StreamMsg(
                                "config_updated",
                                "",
                                time.time(),
                                {
                                    "provider": client_config["provider"],
                                    "exchange": client_creds["exchange"],
                                    "hasSystemPrompt": bool(client_config["systemPrompt"]),
                                },
                            ).dumps()
                        )
                        continue

                    # Credentials update (legacy, kept for compatibility)
                    if (
                        isinstance(payload, dict)
                        and payload.get("type") == "credentials"
                    ):
                        client_creds["exchange"] = (
                            payload.get("exchange") or client_creds["exchange"]
                        )
                        client_creds["apiKey"] = payload.get("apiKey") or ""
                        client_creds["apiSecret"] = payload.get("apiSecret") or ""
                        await websocket.send(
                            StreamMsg(
                                "credentials_updated",
                                "",
                                time.time(),
                                {"exchange": client_creds["exchange"]},
                            ).dumps()
                        )
                        continue

                    # Auto-trigger control
                    if (
                        isinstance(payload, dict)
                        and payload.get("type") == "auto_trigger"
                    ):
                        action = payload.get("action")
                        if action == "enable":
                            auto_state.enabled = True
                            auto_state.schedule_next()
                        elif action == "disable":
                            auto_state.enabled = False
                        elif action == "pause":
                            # Pause for N minutes
                            mins = int(payload.get("minutes", 30))
                            auto_state.paused_until = time.time() + mins * 60
                        elif action == "resume":
                            auto_state.paused_until = 0
                        elif action == "trigger_now":
                            # Manual trigger
                            auto_state.next_trigger = time.time()
                        elif action == "set_symbols":
                            symbols = payload.get("symbols", [])
                            if symbols:
                                auto_state.symbols = symbols
                        elif action == "status":
                            pass  # Just send status below

                        await websocket.send(
                            StreamMsg(
                                "auto_trigger_status",
                                "",
                                time.time(),
                                auto_state.get_status(),
                            ).dumps()
                        )
                        continue

                    # UI actions
                    if isinstance(payload, dict) and payload.get("type") == "ui":
                        await handle_ui_action(agent, websocket, payload, client_creds)
                        continue

                    # History clear
                    if (
                        isinstance(payload, dict)
                        and payload.get("type") == "history"
                        and payload.get("action") == "clear"
                    ):
                        history(action="clear")
                        await websocket.send(
                            StreamMsg(
                                "history_cleared", "", time.time(), "cleared"
                            ).dumps()
                        )
                        continue

                except json.JSONDecodeError:
                    pass
                except websockets.exceptions.ConnectionClosed:
                    break
                except Exception as e:
                    print(f"[ERROR] Message handling error: {e}")
                    pass

            # Exit command
            if raw.lower() == "exit":
                try:
                    await websocket.send(
                        StreamMsg("disconnected", "", time.time(), "bye").dumps()
                    )
                except:
                    pass
                break

            # Agent message
            turn_id = str(uuid.uuid4())
            task = asyncio.create_task(run_turn(agent, websocket, loop, raw, turn_id))
            active_tasks.add(task)
            task.add_done_callback(active_tasks.discard)

    except websockets.exceptions.ConnectionClosed:
        pass  # Normal disconnect
    except Exception as e:
        print(f"Client handler error: {e}")

    # Cancel active tasks on disconnect
    for task in active_tasks:
        if not task.done():
            task.cancel()

    if active_tasks:
        await asyncio.gather(*active_tasks, return_exceptions=True)


# ============================================================================
# Server Entry Point
# ============================================================================


async def amain():
    host = os.getenv("DASH_HOST", "0.0.0.0")
    port = int(os.getenv("DASH_PORT", "8090"))

    async with websockets.serve(handle_client, host, port):
        print(f"🚀 HashTrade Server running: ws://{host}:{port}")
        print(f"📊 Open web/index.html and click Connect")
        print(f"⏰ Auto-trigger: {os.getenv('DASH_AUTO_TRIGGER', 'true')}")
        print(f"📈 Symbols: {os.getenv('DASH_SYMBOLS', 'BTC/USDT,ETH/USDT')}")
        await asyncio.Future()


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()
