#!/usr/bin/env python3
"""
Universal CCXT Tool for Strands Agents

A unified tool for interacting with cryptocurrency exchanges via CCXT.
Supports REST API calls, WebSocket streaming (ccxt.pro), and multi-exchange operations.

Licensed under the Apache License, Version 2.0
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import traceback
from typing import Any, Dict, List, Optional

from strands import tool

# Sensitive keys to redact from output
SENSITIVE_KEYS = {
    "apiKey",
    "secret",
    "password",
    "uid",
    "token",
    "privateKey",
    "walletAddress",
    "mnemonic",
    "api_key",
    "api_secret",
    "apikey",
    "apisecret",
}


def _redact(obj: Any) -> Any:
    """Recursively redact sensitive data from output."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key_lower = str(k).lower()
            if str(k) in SENSITIVE_KEYS or any(
                s in key_lower for s in ["secret", "apikey", "password", "token"]
            ):
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def _parse_json(value: Any, default: Any = None) -> Any:
    """Parse JSON string or return value as-is if already parsed."""
    if value is None:
        return default
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return default
        if (s.startswith("{") and s.endswith("}")) or (
            s.startswith("[") and s.endswith("]")
        ):
            return json.loads(s)
        return value
    return value


def _get_secret_env_keys(prefix: str) -> List[str]:
    """Get common environment variable names for API secrets."""
    return [
        f"{prefix}_API_SECRET",
        f"{prefix}_API_SECRET_KEY",
        f"{prefix}_SECRET",
        f"{prefix}_SECRET_KEY",
    ]


def _env_get_first(keys: List[str]) -> Optional[str]:
    """Get first available environment variable from list."""
    for k in keys:
        v = os.getenv(k)
        if v:
            return v
    return None


def _discover_exchange_from_env() -> tuple[Optional[str], List[str]]:
    """Auto-detect exchange from environment variables."""
    candidates: set[str] = set()
    for k in os.environ.keys():
        if not k.endswith("_API_KEY"):
            continue
        prefix = k[:-8]
        if not prefix:
            continue
        if _env_get_first(_get_secret_env_keys(prefix)):
            candidates.add(prefix.lower())
    out = sorted(candidates)
    return (out[0] if len(out) == 1 else None), out


def _resolve_credentials(
    exchange_id: str, user_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Resolve API credentials with priority:
    1. Explicit user_config
    2. CCXT_API_KEY / CCXT_SECRET (generic)
    3. {EXCHANGE}_API_KEY / {EXCHANGE}_API_SECRET (exchange-specific)
    """
    cfg: Dict[str, Any] = {}

    # 1. From user config
    if user_config:
        for k in ("apiKey", "secret", "password", "uid", "token"):
            if user_config.get(k):
                cfg[k] = user_config[k]

    # 2. Generic CCXT env vars
    if "apiKey" not in cfg and os.getenv("CCXT_API_KEY"):
        cfg["apiKey"] = os.getenv("CCXT_API_KEY")
    if "secret" not in cfg and os.getenv("CCXT_SECRET"):
        cfg["secret"] = os.getenv("CCXT_SECRET")

    # 3. Exchange-specific env vars
    prefix = exchange_id.upper()
    if "apiKey" not in cfg and os.getenv(f"{prefix}_API_KEY"):
        cfg["apiKey"] = os.getenv(f"{prefix}_API_KEY")
    if "secret" not in cfg:
        secret = _env_get_first(_get_secret_env_keys(prefix))
        if secret:
            cfg["secret"] = secret

    # Optional credentials
    for env_key, cfg_key in [
        ("CCXT_PASSWORD", "password"),
        ("CCXT_UID", "uid"),
        ("CCXT_TOKEN", "token"),
    ]:
        if cfg_key not in cfg and os.getenv(env_key):
            cfg[cfg_key] = os.getenv(env_key)

    return cfg


def _build_exchange(
    exchange_id: str, config: Optional[Dict[str, Any]] = None, use_pro: bool = False
):
    """Build and configure a CCXT exchange instance."""
    import ccxt

    exchange_id = exchange_id.strip().lower()

    # Select ccxt or ccxt.pro
    if use_pro:
        try:
            import ccxt.pro as ccxtpro

            module = ccxtpro
        except ImportError:
            raise ImportError(
                "ccxt.pro not installed. Install with: pip install ccxt[pro]"
            )
    else:
        module = ccxt

    if not hasattr(module, exchange_id):
        raise ValueError(
            f"Unknown exchange '{exchange_id}'. Use action='list_exchanges' to see available."
        )

    cls = getattr(module, exchange_id)

    # Base config
    cfg: Dict[str, Any] = {
        "enableRateLimit": True,
        "timeout": int(os.getenv("CCXT_TIMEOUT", "30000")),
    }

    # Add credentials
    cfg.update(_resolve_credentials(exchange_id, config))

    # Default type (spot/swap/future)
    default_type = os.getenv("CCXT_DEFAULT_TYPE")
    if default_type:
        cfg.setdefault("options", {})
        cfg["options"]["defaultType"] = default_type

    # Merge user config
    if config:
        cfg.update(config)

    ex = cls(cfg)

    # Sandbox mode
    if os.getenv("CCXT_SANDBOX", "false").lower() == "true":
        if hasattr(ex, "set_sandbox_mode"):
            ex.set_sandbox_mode(True)

    return ex


def _resolve_exchange_id(exchange: Optional[str]) -> str:
    """Resolve exchange ID from parameter or environment."""
    exchange_id = exchange or os.getenv("CCXT_EXCHANGE")

    if not exchange_id:
        inferred, candidates = _discover_exchange_from_env()
        if inferred:
            return inferred
        if candidates:
            raise ValueError(
                f"Multiple exchanges detected in env: {candidates}. "
                "Please specify exchange parameter explicitly."
            )
        raise ValueError("exchange required (or set CCXT_EXCHANGE env var)")

    return exchange_id.strip().lower()


@tool
def use_ccxt(
    action: str,
    exchange: Optional[str] = None,
    method: Optional[str] = None,
    symbol: Optional[str] = None,
    args: Optional[str] = None,
    kwargs: Optional[str] = None,
    config: Optional[str] = None,
    # Order parameters
    side: Optional[str] = None,
    order_type: Optional[str] = None,
    amount: Optional[float] = None,
    price: Optional[float] = None,
    order_id: Optional[str] = None,
    # Multi-exchange
    exchanges: Optional[str] = None,
    # WebSocket parameters
    max_messages: int = 5,
    max_seconds: int = 15,
    # OHLCV parameters
    timeframe: str = "1m",
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Universal CCXT client tool for cryptocurrency exchange operations.

    Provides unified access to 100+ exchanges via REST API and WebSocket streaming.
    Supports market data, trading, account management, and multi-exchange operations.

    Args:
        action: Operation to perform:
            Discovery:
            - "list_exchanges" - List all supported exchanges
            - "describe" - Get exchange capabilities and info
            - "list_methods" - List available methods on exchange
            - "load_markets" - Load and return market symbols

            Market Data:
            - "fetch_ticker" - Get ticker for symbol
            - "fetch_tickers" - Get all tickers
            - "fetch_orderbook" - Get order book for symbol
            - "fetch_ohlcv" - Get OHLCV candles
            - "fetch_trades" - Get recent trades

            Trading:
            - "create_order" - Create new order
            - "cancel_order" - Cancel existing order
            - "fetch_order" - Get order details
            - "fetch_orders" - Get all orders
            - "fetch_open_orders" - Get open orders
            - "fetch_closed_orders" - Get closed orders

            Account:
            - "fetch_balance" - Get account balance
            - "fetch_positions" - Get open positions (derivatives)
            - "fetch_my_trades" - Get trade history

            Multi-Exchange:
            - "multi_orderbook" - Compare orderbooks across exchanges

            WebSocket (requires ccxt.pro):
            - "watch_ticker" - Stream ticker updates
            - "watch_orderbook" - Stream orderbook updates
            - "watch_trades" - Stream trade updates
            - "watch_ohlcv" - Stream OHLCV updates

            Generic:
            - "call" - Call any exchange method directly

        exchange: Exchange ID (e.g., "bybit", "binance", "okx").
                  Falls back to CCXT_EXCHANGE env var.
        method: Method name for "call" action
        symbol: Trading pair (e.g., "BTC/USDT", "ETH/USDT:USDT")
        args: JSON array of positional arguments for method calls
        kwargs: JSON object of keyword arguments for method calls
        config: JSON object for exchange constructor overrides

        Order Parameters:
        - side: "buy" or "sell"
        - order_type: "market", "limit", etc.
        - amount: Order quantity
        - price: Order price (for limit orders)
        - order_id: Order ID for cancel/fetch operations

        Multi-Exchange:
        - exchanges: JSON array of exchange IDs for multi-exchange operations

        WebSocket:
        - max_messages: Max messages to collect (default: 5)
        - max_seconds: Max seconds to stream (default: 15)

        OHLCV:
        - timeframe: Candle timeframe (default: "1m")
        - limit: Number of candles (default: 100)

    Returns:
        Dict with:
            - status: "success" or "error"
            - content: Response data
            - exchange: Exchange ID used
            - method: Method called
            - ms: Execution time in milliseconds

    Environment Variables:
        - CCXT_EXCHANGE: Default exchange ID
        - CCXT_API_KEY: API key
        - CCXT_SECRET: API secret
        - CCXT_PASSWORD: API password (if required)
        - CCXT_UID: User ID (if required)
        - CCXT_TOKEN: Token (if required)
        - CCXT_DEFAULT_TYPE: Default market type (spot/swap/future)
        - CCXT_TIMEOUT: Request timeout in ms (default: 30000)
        - CCXT_SANDBOX: Enable sandbox mode ("true"/"false")

        Exchange-specific (alternative):
        - {EXCHANGE}_API_KEY: e.g., BYBIT_API_KEY
        - {EXCHANGE}_API_SECRET: e.g., BYBIT_API_SECRET

    Examples:
        # List exchanges
        use_ccxt(action="list_exchanges")

        # Get exchange info
        use_ccxt(action="describe", exchange="bybit")

        # Fetch ticker
        use_ccxt(action="fetch_ticker", exchange="bybit", symbol="BTC/USDT")

        # Fetch OHLCV candles
        use_ccxt(action="fetch_ohlcv", symbol="BTC/USDT", timeframe="1h", limit=50)

        # Create limit order
        use_ccxt(
            action="create_order",
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            amount=0.001,
            price=50000
        )

        # Cancel order
        use_ccxt(action="cancel_order", symbol="BTC/USDT", order_id="12345")

        # Fetch balance
        use_ccxt(action="fetch_balance")

        # Compare orderbooks across exchanges
        use_ccxt(
            action="multi_orderbook",
            exchanges='["binance", "bybit", "okx"]',
            symbol="BTC/USDT"
        )

        # Stream ticker via WebSocket
        use_ccxt(
            action="watch_ticker",
            symbol="BTC/USDT",
            max_messages=10,
            max_seconds=30
        )

        # Call any method directly
        use_ccxt(
            action="call",
            method="fetch_funding_rate",
            args='["BTC/USDT:USDT"]'
        )
    """
    import ccxt

    t0 = time.time()

    try:
        # === LIST EXCHANGES ===
        if action == "list_exchanges":
            exchanges_list = sorted(ccxt.exchanges)
            return {
                "status": "success",
                "content": [
                    {
                        "text": json.dumps(
                            {"count": len(exchanges_list), "exchanges": exchanges_list},
                            indent=2,
                        )
                    }
                ],
                "ms": int((time.time() - t0) * 1000),
            }

        # === DESCRIBE ===
        if action == "describe":
            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            info = {
                "id": ex.id,
                "name": getattr(ex, "name", None),
                "countries": getattr(ex, "countries", None),
                "rateLimit": getattr(ex, "rateLimit", None),
                "has": getattr(ex, "has", None),
                "timeframes": getattr(ex, "timeframes", None),
                "urls": getattr(ex, "urls", None),
                "version": getattr(ex, "version", None),
                "certified": getattr(ex, "certified", False),
                "pro": getattr(ex, "pro", False),
            }

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [{"text": json.dumps(_redact(info), indent=2)}],
                "exchange": exchange_id,
                "ms": int((time.time() - t0) * 1000),
            }

        # === LIST METHODS ===
        if action == "list_methods":
            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            methods = sorted(
                [
                    m
                    for m in dir(ex)
                    if not m.startswith("_") and callable(getattr(ex, m, None))
                ]
            )

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [
                    {
                        "text": json.dumps(
                            {"exchange": ex.id, "methods": methods}, indent=2
                        )
                    }
                ],
                "exchange": exchange_id,
                "ms": int((time.time() - t0) * 1000),
            }

        # === LOAD MARKETS ===
        if action == "load_markets":
            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            markets = ex.load_markets()
            symbols = sorted(markets.keys())

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [
                    {
                        "text": json.dumps(
                            {
                                "exchange": ex.id,
                                "count": len(symbols),
                                "symbols": symbols[:500],  # Limit output
                            },
                            indent=2,
                        )
                    }
                ],
                "exchange": exchange_id,
                "ms": int((time.time() - t0) * 1000),
            }

        # === MARKET DATA: FETCH_TICKER ===
        if action == "fetch_ticker":
            if not symbol:
                raise ValueError("symbol required for fetch_ticker")

            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            result = ex.fetch_ticker(symbol)

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [{"text": json.dumps(_redact(result), indent=2)}],
                "exchange": exchange_id,
                "method": "fetch_ticker",
                "symbol": symbol,
                "ms": int((time.time() - t0) * 1000),
            }

        # === MARKET DATA: FETCH_TICKERS ===
        if action == "fetch_tickers":
            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            symbols_list = _parse_json(args) if args else None
            result = ex.fetch_tickers(symbols_list)

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [{"text": json.dumps(_redact(result), indent=2)[:12000]}],
                "exchange": exchange_id,
                "method": "fetch_tickers",
                "count": len(result),
                "ms": int((time.time() - t0) * 1000),
            }

        # === MARKET DATA: FETCH_ORDERBOOK ===
        if action == "fetch_orderbook":
            if not symbol:
                raise ValueError("symbol required for fetch_orderbook")

            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            result = ex.fetch_order_book(symbol, limit)

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [{"text": json.dumps(_redact(result), indent=2)}],
                "exchange": exchange_id,
                "method": "fetch_order_book",
                "symbol": symbol,
                "ms": int((time.time() - t0) * 1000),
            }

        # === MARKET DATA: FETCH_OHLCV ===
        if action == "fetch_ohlcv":
            if not symbol:
                raise ValueError("symbol required for fetch_ohlcv")

            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            result = ex.fetch_ohlcv(symbol, timeframe, limit=limit)

            try:
                ex.close()
            except:
                pass

            # Format OHLCV for readability
            formatted = [
                {
                    "timestamp": candle[0],
                    "open": candle[1],
                    "high": candle[2],
                    "low": candle[3],
                    "close": candle[4],
                    "volume": candle[5],
                }
                for candle in result
            ]

            return {
                "status": "success",
                "content": [
                    {
                        "text": json.dumps(
                            {
                                "symbol": symbol,
                                "timeframe": timeframe,
                                "count": len(formatted),
                                "candles": formatted,
                            },
                            indent=2,
                        )
                    }
                ],
                "exchange": exchange_id,
                "method": "fetch_ohlcv",
                "symbol": symbol,
                "ms": int((time.time() - t0) * 1000),
            }

        # === MARKET DATA: FETCH_TRADES ===
        if action == "fetch_trades":
            if not symbol:
                raise ValueError("symbol required for fetch_trades")

            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            result = ex.fetch_trades(symbol, limit=limit)

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [{"text": json.dumps(_redact(result), indent=2)[:12000]}],
                "exchange": exchange_id,
                "method": "fetch_trades",
                "symbol": symbol,
                "count": len(result),
                "ms": int((time.time() - t0) * 1000),
            }

        # === TRADING: CREATE_ORDER ===
        if action == "create_order":
            if not symbol:
                raise ValueError("symbol required for create_order")
            if not side:
                raise ValueError("side required for create_order (buy/sell)")
            if not order_type:
                raise ValueError("order_type required for create_order (market/limit)")
            if amount is None:
                raise ValueError("amount required for create_order")

            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            params = _parse_json(kwargs, {})
            result = ex.create_order(symbol, order_type, side, amount, price, params)

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [{"text": json.dumps(_redact(result), indent=2)}],
                "exchange": exchange_id,
                "method": "create_order",
                "order_id": result.get("id"),
                "ms": int((time.time() - t0) * 1000),
            }

        # === TRADING: CANCEL_ORDER ===
        if action == "cancel_order":
            if not order_id:
                raise ValueError("order_id required for cancel_order")

            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            result = ex.cancel_order(order_id, symbol)

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [{"text": json.dumps(_redact(result), indent=2)}],
                "exchange": exchange_id,
                "method": "cancel_order",
                "order_id": order_id,
                "ms": int((time.time() - t0) * 1000),
            }

        # === TRADING: FETCH_ORDER ===
        if action == "fetch_order":
            if not order_id:
                raise ValueError("order_id required for fetch_order")

            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            result = ex.fetch_order(order_id, symbol)

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [{"text": json.dumps(_redact(result), indent=2)}],
                "exchange": exchange_id,
                "method": "fetch_order",
                "order_id": order_id,
                "ms": int((time.time() - t0) * 1000),
            }

        # === TRADING: FETCH_ORDERS ===
        if action in ("fetch_orders", "fetch_open_orders", "fetch_closed_orders"):
            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            method_name = action
            fn = getattr(ex, method_name)
            result = fn(symbol, limit=limit) if symbol else fn()

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [{"text": json.dumps(_redact(result), indent=2)[:12000]}],
                "exchange": exchange_id,
                "method": method_name,
                "count": len(result),
                "ms": int((time.time() - t0) * 1000),
            }

        # === ACCOUNT: FETCH_BALANCE ===
        if action == "fetch_balance":
            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            result = ex.fetch_balance()

            # Filter to non-zero balances for cleaner output
            filtered = {
                "info": "***REDACTED***",
                "timestamp": result.get("timestamp"),
                "datetime": result.get("datetime"),
            }
            for currency, balance in result.items():
                if isinstance(balance, dict) and (balance.get("total", 0) or 0) > 0:
                    filtered[currency] = balance

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [{"text": json.dumps(filtered, indent=2)}],
                "exchange": exchange_id,
                "method": "fetch_balance",
                "ms": int((time.time() - t0) * 1000),
            }

        # === ACCOUNT: FETCH_POSITIONS ===
        if action == "fetch_positions":
            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            symbols_list = [symbol] if symbol else None
            result = ex.fetch_positions(symbols_list)

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [{"text": json.dumps(_redact(result), indent=2)[:12000]}],
                "exchange": exchange_id,
                "method": "fetch_positions",
                "count": len(result),
                "ms": int((time.time() - t0) * 1000),
            }

        # === ACCOUNT: FETCH_MY_TRADES ===
        if action == "fetch_my_trades":
            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            result = ex.fetch_my_trades(symbol, limit=limit)

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [{"text": json.dumps(_redact(result), indent=2)[:12000]}],
                "exchange": exchange_id,
                "method": "fetch_my_trades",
                "count": len(result),
                "ms": int((time.time() - t0) * 1000),
            }

        # === MULTI-EXCHANGE: MULTI_ORDERBOOK ===
        if action == "multi_orderbook":
            if not symbol:
                raise ValueError("symbol required for multi_orderbook")

            exchanges_list = _parse_json(exchanges)
            if not isinstance(exchanges_list, list) or not exchanges_list:
                raise ValueError("exchanges must be JSON array of exchange IDs")

            rows = []
            for ex_id in exchanges_list:
                try:
                    ex = _build_exchange(str(ex_id).strip(), _parse_json(config))
                    ob = ex.fetch_order_book(symbol, limit)
                    bid = ob["bids"][0][0] if ob.get("bids") else None
                    ask = ob["asks"][0][0] if ob.get("asks") else None
                    rows.append({"exchange": ex.id, "bid": bid, "ask": ask})
                    try:
                        ex.close()
                    except:
                        pass
                except Exception as e:
                    rows.append({"exchange": ex_id, "error": str(e)})

            # Find best prices
            bids = [r["bid"] for r in rows if r.get("bid")]
            asks = [r["ask"] for r in rows if r.get("ask")]
            best_bid = max(bids) if bids else None
            best_ask = min(asks) if asks else None
            best_bid_ex = next(
                (r["exchange"] for r in rows if r.get("bid") == best_bid), None
            )
            best_ask_ex = next(
                (r["exchange"] for r in rows if r.get("ask") == best_ask), None
            )

            spread = (
                ((best_ask - best_bid) / best_bid * 100)
                if best_bid and best_ask
                else None
            )

            return {
                "status": "success",
                "content": [
                    {
                        "text": json.dumps(
                            {
                                "symbol": symbol,
                                "exchanges": rows,
                                "best_bid": {
                                    "price": best_bid,
                                    "exchange": best_bid_ex,
                                },
                                "best_ask": {
                                    "price": best_ask,
                                    "exchange": best_ask_ex,
                                },
                                "spread_percent": round(spread, 4) if spread else None,
                                "arbitrage_opportunity": best_bid
                                and best_ask
                                and best_bid > best_ask,
                            },
                            indent=2,
                        )
                    }
                ],
                "ms": int((time.time() - t0) * 1000),
            }

        # === WEBSOCKET: WATCH_* ===
        if action.startswith("watch_"):
            exchange_id = _resolve_exchange_id(exchange)
            ws_method = action  # e.g., watch_ticker, watch_orderbook

            async def _stream():
                ex = _build_exchange(exchange_id, _parse_json(config), use_pro=True)
                try:
                    if not hasattr(ex, ws_method):
                        return {
                            "ok": False,
                            "error": f"Exchange has no method: {ws_method}",
                        }

                    fn = getattr(ex, ws_method)
                    messages = []
                    started = time.time()

                    for _ in range(max_messages):
                        if time.time() - started > max_seconds:
                            break

                        # Build args based on method
                        if symbol:
                            msg = await fn(symbol)
                        else:
                            msg = await fn()

                        messages.append(
                            {"ts": int(time.time() * 1000), "data": _redact(msg)}
                        )

                    return {
                        "ok": True,
                        "exchange": exchange_id,
                        "method": ws_method,
                        "count": len(messages),
                        "messages": messages,
                    }
                finally:
                    try:
                        await ex.close()
                    except:
                        pass

            result = asyncio.run(_stream())

            if not result.get("ok"):
                return {
                    "status": "error",
                    "content": [{"text": json.dumps(result, indent=2)}],
                    "ms": int((time.time() - t0) * 1000),
                }

            return {
                "status": "success",
                "content": [{"text": json.dumps(result, indent=2)[:12000]}],
                "exchange": exchange_id,
                "method": ws_method,
                "ms": int((time.time() - t0) * 1000),
            }

        # === GENERIC: CALL ===
        if action == "call":
            if not method:
                raise ValueError("method required for action='call'")

            exchange_id = _resolve_exchange_id(exchange)
            ex = _build_exchange(exchange_id, _parse_json(config))

            parsed_args = _parse_json(args, [])
            parsed_kwargs = _parse_json(kwargs, {})

            if isinstance(parsed_args, str):
                parsed_args = [parsed_args]
            if not isinstance(parsed_args, list):
                raise ValueError("args must be JSON array")
            if not isinstance(parsed_kwargs, dict):
                raise ValueError("kwargs must be JSON object")

            if not hasattr(ex, method):
                raise AttributeError(f"Exchange '{ex.id}' has no method '{method}'")

            fn = getattr(ex, method)
            result = fn(*parsed_args, **parsed_kwargs)

            try:
                ex.close()
            except:
                pass

            return {
                "status": "success",
                "content": [{"text": json.dumps(_redact(result), indent=2)[:12000]}],
                "exchange": exchange_id,
                "method": method,
                "ms": int((time.time() - t0) * 1000),
            }

        # === UNKNOWN ACTION ===
        return {
            "status": "error",
            "content": [
                {
                    "text": f"Unknown action: {action}. Valid actions: "
                    "list_exchanges, describe, list_methods, load_markets, "
                    "fetch_ticker, fetch_tickers, fetch_orderbook, fetch_ohlcv, fetch_trades, "
                    "create_order, cancel_order, fetch_order, fetch_orders, fetch_open_orders, fetch_closed_orders, "
                    "fetch_balance, fetch_positions, fetch_my_trades, "
                    "multi_orderbook, watch_*, call"
                }
            ],
            "ms": int((time.time() - t0) * 1000),
        }

    except Exception as e:
        return {
            "status": "error",
            "content": [
                {"text": f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"}
            ],
            "ms": int((time.time() - t0) * 1000),
        }


if __name__ == "__main__":
    # Test
    print("Testing use_ccxt tool...")

    # List exchanges
    result = use_ccxt(action="list_exchanges")
    print(f"Exchanges: {result['content'][0]['text'][:200]}...")

    # Describe
    result = use_ccxt(action="describe", exchange="bybit")
    print(f"\nBybit: {result['content'][0]['text'][:500]}...")
