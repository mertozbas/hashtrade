#!/usr/bin/env python3
"""
HashTrade Dashboard - Standalone Trading Agent Server

A minimal WebSocket server with real-time streaming for a trading dashboard.
Uses Strands Agent with CCXT and history tools only.
"""

import traceback
import asyncio
import json
import time
import uuid
import os
import sys
from typing import Any, Dict, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

import websockets
from strands import Agent, tool

# Import tools
from tools.history import history
from tools.use_ccxt import use_ccxt
from tools.interface import interface

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

    def __init__(self, websocket, loop, turn_id: str):
        self.ws = websocket
        self.loop = loop
        self.turn_id = turn_id
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


def create_trading_agent() -> Agent:
    """Create a trading agent with CCXT and history tools."""

    # Model selection (same logic as devduck)
    provider = os.getenv("MODEL_PROVIDER")

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
            if os.getenv("ANTHROPIC_API_KEY"):
                provider = "anthropic"
            elif os.getenv("OPENAI_API_KEY"):
                provider = "openai"
            else:
                provider = "ollama"

    # Create model
    if provider == "ollama":
        from strands.models.ollama import OllamaModel

        model = OllamaModel(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model_id=os.getenv("STRANDS_MODEL_ID", "qwen3:1.7b"),
            temperature=1,
            keep_alive="5m",
        )
    else:
        try:
            from strands_tools.utils.models.model import create_model

            model = create_model(provider=provider)
        except ImportError:
            from strands.models.ollama import OllamaModel

            model = OllamaModel(
                host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
                model_id=os.getenv("STRANDS_MODEL_ID", "qwen3:1.7b"),
                temperature=1,
                keep_alive="5m",
            )

    system_prompt = """You are a cryptocurrency trading assistant with real-time market access.

## Available Tools:
1. **use_ccxt** - Unified crypto exchange interface
   - fetch_ticker, fetch_ohlcv, fetch_balance
   - create_order, cancel_order, fetch_orders
   - Supports: Bybit, Binance, OKX, etc.

2. **history** - Action logging for dashboard
   - action="add" to log trades, signals, notes
   - action="tail" to view recent history

3. **interface** - Dynamic UI & Theme control
   Theme Actions:
   - action="set_theme", preset="cyberpunk" (or: ocean_blue, sunset_orange, gold_luxury, matrix_green, dark_minimal, neon_green)
   - action="update_color", color_name="neon", color_value="#ff00ff"
   - action="list_presets" to see all themes
   - action="reset_theme" for default neon green
   
   UI Render Actions:
   - action="render_card", title="...", content="...", target="timeline"
   - action="render_table", title="...", data=[{...}]
   - action="render_chart", title="...", data=[{"label": "BTC", "value": 100}]
   - action="render_alert", content="Order filled!", style={"type": "success"}
   - action="render_html", html="<div>Custom HTML</div>"
   - action="render_progress", title="Loading...", data={"value": 75, "max": 100}
   - action="clear_ui" to remove dynamic components

## Trading Commands:
- "buy 0.001 BTC" → Create market buy order
- "sell 100 USDT worth of ETH" → Market sell
- "limit buy BTC at 50000" → Limit order
- "check balance" → Show account balances
- "price of ETH" → Get current ticker

## Theme Customization:
Users can ask to change colors/themes:
- "change to cyberpunk theme" → interface(action="set_theme", preset="cyberpunk")
- "make it blue" → interface(action="set_theme", preset="ocean_blue")
- "I want gold colors" → interface(action="set_theme", preset="gold_luxury")
- "change accent color to purple" → interface(action="update_color", color_name="neon", color_value="#9933ff")

## Important:
- Always confirm order details before executing
- Log all trades to history for the dashboard
- Be concise but informative
- Use use_ccxt for all exchange operations
- Use interface for UI rendering and theme changes
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


async def run_turn(agent, websocket, loop, user_text: str, turn_id: str):
    """Process a user message with streaming."""
    try:
        await websocket.send(
            StreamMsg("turn_start", turn_id, time.time(), user_text).dumps()
        )
    except websockets.exceptions.ConnectionClosed:
        return

    cb = WSCallback(websocket, loop, turn_id)
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
        await websocket.send(StreamMsg("turn_end", turn_id, time.time()).dumps())
    except websockets.exceptions.ConnectionClosed:
        pass


# ============================================================================
# Client Handler
# ============================================================================


async def handle_client(websocket):
    """Handle a WebSocket client connection."""
    loop = asyncio.get_running_loop()

    # Change to project root
    proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(proj_root)

    # Create agent for this connection
    agent = create_trading_agent()

    # Client credentials
    client_creds = {
        "exchange": os.getenv("DASH_EXCHANGE", "bybit"),
        "apiKey": "",
        "apiSecret": "",
    }

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

    active_tasks = set()

    try:
        async for raw in websocket:
            raw = (raw or "").strip()
            if not raw:
                continue

            # Handle JSON messages
            if raw.startswith("{"):
                try:
                    payload = json.loads(raw)

                    # Credentials update
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
                except Exception:
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
    host = os.getenv("DASH_HOST", "127.0.0.1")
    port = int(os.getenv("DASH_PORT", "8090"))

    async with websockets.serve(handle_client, host, port):
        print(f"🚀 HashTrade Server running: ws://{host}:{port}")
        print(f"📊 Open web/index.html and click Connect")
        await asyncio.Future()


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()
