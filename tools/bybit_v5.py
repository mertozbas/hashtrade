"""
Bybit V5 API Tool
Comprehensive trading operations with proper signature and parsing
"""

from typing import Dict, Any, Optional
import os
import time
import hmac
import hashlib
import requests
from strands import tool


def _get_config():
    """Get API configuration from environment"""
    api_key = os.getenv("BYBIT_API_KEY", "")
    api_secret = os.getenv("BYBIT_API_SECRET", "")
    testnet = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
    base_url = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
    return api_key, api_secret, base_url


def _generate_signature(api_secret: str, params: str, timestamp: str, recv_window: str = "5000") -> str:
    """
    Generate HMAC SHA256 signature for Bybit V5 API
    Format: timestamp + api_key + recv_window + params
    """
    api_key, _, _ = _get_config()
    param_str = f"{timestamp}{api_key}{recv_window}{params}"
    return hmac.new(
        api_secret.encode('utf-8'),
        param_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def _make_request(
    method: str,
    endpoint: str,
    params: Optional[Dict] = None,
    signed: bool = True
) -> Dict[str, Any]:
    """Make authenticated API request with proper error handling"""
    api_key, api_secret, base_url = _get_config()

    url = f"{base_url}{endpoint}"
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"

    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "Content-Type": "application/json"
    }

    if signed and api_key and api_secret:
        params_str = ""
        if params:
            if method == "GET":
                params_str = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
            else:
                import json
                params_str = json.dumps(params)

        signature = _generate_signature(api_secret, params_str, timestamp, recv_window)
        headers["X-BAPI-SIGN"] = signature

    try:
        if method == "GET":
            response = requests.get(url, params=params, headers=headers, timeout=10)
        else:
            response = requests.post(url, json=params, headers=headers, timeout=10)

        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        return {
            "retCode": -1,
            "retMsg": "Request timeout - API took too long to respond",
            "error_type": "timeout"
        }
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        if status_code == 429:
            return {
                "retCode": -1,
                "retMsg": "Rate limit exceeded - wait 60 seconds",
                "error_type": "rate_limit"
            }
        elif status_code == 401:
            return {
                "retCode": -1,
                "retMsg": "Authentication failed - check API keys",
                "error_type": "auth_failed"
            }
        elif status_code == 403:
            return {
                "retCode": -1,
                "retMsg": "Permission denied - check API key permissions",
                "error_type": "permission_denied"
            }
        else:
            return {
                "retCode": -1,
                "retMsg": f"HTTP error {status_code}: {str(e)}",
                "error_type": "http_error"
            }
    except Exception as e:
        return {
            "retCode": -1,
            "retMsg": str(e),
            "error_type": "unknown"
        }


@tool
def bybit_v5(
    action: str,
    symbol: str = None,
    category: str = "linear",
    kwargs: str = ""
) -> Dict[str, Any]:
    """
    Bybit V5 API comprehensive trading tool

    Actions:
    - get_balance: Get account balance (parsed for USDT)
    - get_positions: Get open positions (parsed and filtered)
    - get_ticker: Get market ticker (requires symbol)
    - get_kline: Get candlestick data (requires symbol, interval)
    - place_order: Place order (requires symbol, side, orderType, qty)
    - cancel_order: Cancel order (requires symbol, orderId)
    - set_leverage: Set leverage (requires symbol, buyLeverage, sellLeverage)
    - set_trading_stop: Set TP/SL (requires symbol, positionIdx, stopLoss, takeProfit)
    - update_trailing_stop: Update trailing stop to breakeven (requires symbol, current_price)

    Args:
        action: API action to perform
        symbol: Trading pair (e.g., BTCUSDT)
        category: Product type (linear, inverse, spot, option)
        kwargs: JSON string of additional parameters

    Returns:
        Dict with status and parsed data

    Examples:
        bybit_v5(action="get_balance")
        bybit_v5(action="get_positions", category="linear")
        bybit_v5(action="place_order", symbol="BTCUSDT", category="linear",
                 kwargs='{"side":"Buy","orderType":"Market","qty":"0.001","positionIdx":0}')
    """
    import json

    # Get config for credential checks
    api_key, api_secret, _ = _get_config()

    # Parse kwargs string to dict
    try:
        extra_params = json.loads(kwargs) if kwargs else {}
    except json.JSONDecodeError:
        return {
            "status": "error",
            "content": [{"text": f"Invalid JSON in kwargs: {kwargs}"}]
        }

    # Check credentials for signed endpoints
    actions_requiring_auth = [
        "get_balance", "get_positions", "place_order",
        "cancel_order", "set_leverage", "set_trading_stop",
        "update_trailing_stop"
    ]

    if action in actions_requiring_auth:
        if not api_key or not api_secret:
            return {
                "status": "error",
                "content": [{"text": "BYBIT_API_KEY and BYBIT_API_SECRET required in .env"}]
            }

    # Action routing with proper parsing
    if action == "get_balance":
        result = _make_request("GET", "/v5/account/wallet-balance", {
            "accountType": extra_params.get("accountType", "UNIFIED")
        })

        if result.get("retCode") == 0:
            # Parse USDT balance
            try:
                balance_list = result["result"]["list"]
                if balance_list:
                    coins = balance_list[0]["coin"]
                    usdt = next((c for c in coins if c["coin"] == "USDT"), None)

                    if usdt:
                        return {
                            "status": "success",
                            "balance_usdt": float(usdt["walletBalance"]),
                            "available_usdt": float(usdt.get("availableToWithdraw") or usdt["walletBalance"]),
                            "equity": float(usdt.get("equity", usdt["walletBalance"])),
                            "unrealized_pnl": float(usdt.get("unrealisedPnl", 0)),
                            "content": [{
                                "text": f"Balance: ${float(usdt['walletBalance']):.2f} USDT | Available: ${float(usdt.get('availableToWithdraw') or usdt['walletBalance']):.2f} USDT"
                            }]
                        }
            except (KeyError, IndexError, StopIteration):
                pass

            return {
                "status": "error",
                "content": [{"text": "USDT balance not found in account"}]
            }
        else:
            return {
                "status": "error",
                "content": [{"text": f"API Error: {result.get('retMsg', 'Unknown error')}"}]
            }

    elif action == "get_positions":
        params = {"category": category}
        if symbol:
            params["symbol"] = symbol
        else:
            params["settleCoin"] = "USDT"

        result = _make_request("GET", "/v5/position/list", params)

        if result.get("retCode") == 0:
            # Parse and filter open positions
            all_positions = result["result"]["list"]
            open_positions = []

            for p in all_positions:
                size = float(p.get("size", 0))
                if size > 0:  # Only open positions
                    open_positions.append({
                        "symbol": p["symbol"],
                        "side": p["side"],
                        "size": size,
                        "entry_price": float(p["avgPrice"]),
                        "current_price": float(p["markPrice"]),
                        "unrealized_pnl": float(p["unrealisedPnl"]),
                        "unrealized_pnl_pct": float(p.get("unrealisedPnl", 0)) / float(p.get("positionValue", 1)) * 100,
                        "leverage": float(p["leverage"]),
                        "position_value": float(p["positionValue"]),
                        "liquidation_price": float(p.get("liqPrice", 0)),
                        "stop_loss": float(p.get("stopLoss", 0)) if p.get("stopLoss") else None,
                        "take_profit": float(p.get("takeProfit", 0)) if p.get("takeProfit") else None,
                        "position_idx": int(p.get("positionIdx", 0))
                    })

            summary = f"Open Positions: {len(open_positions)}/3"
            if open_positions:
                total_pnl = sum(p["unrealized_pnl"] for p in open_positions)
                summary += f" | Total PnL: ${total_pnl:.2f}"

            return {
                "status": "success",
                "open_positions": open_positions,
                "count": len(open_positions),
                "content": [{"text": summary}]
            }
        else:
            return {
                "status": "error",
                "content": [{"text": f"API Error: {result.get('retMsg', 'Unknown error')}"}]
            }

    elif action == "get_ticker":
        if not symbol:
            return {"status": "error", "content": [{"text": "symbol required"}]}

        result = _make_request("GET", "/v5/market/tickers", {
            "category": category,
            "symbol": symbol
        }, signed=False)

        if result.get("retCode") == 0:
            tickers = result["result"]["list"]
            if tickers:
                ticker = tickers[0]
                return {
                    "status": "success",
                    "symbol": ticker["symbol"],
                    "last_price": float(ticker["lastPrice"]),
                    "bid": float(ticker.get("bid1Price", 0)),
                    "ask": float(ticker.get("ask1Price", 0)),
                    "volume_24h": float(ticker.get("volume24h", 0)),
                    "price_change_24h_pct": float(ticker.get("price24hPcnt", 0)) * 100,
                    "content": [{
                        "text": f"{symbol}: ${float(ticker['lastPrice'])} | 24h Change: {float(ticker.get('price24hPcnt', 0)) * 100:.2f}%"
                    }]
                }

        return {
            "status": "error",
            "content": [{"text": f"Failed to get ticker for {symbol}"}]
        }

    elif action == "get_kline":
        if not symbol:
            return {"status": "error", "content": [{"text": "symbol required"}]}

        result = _make_request("GET", "/v5/market/kline", {
            "category": category,
            "symbol": symbol,
            "interval": extra_params.get("interval", "15"),
            "limit": extra_params.get("limit", 200)
        }, signed=False)

        if result.get("retCode") == 0:
            klines = result["result"]["list"]
            return {
                "status": "success",
                "symbol": symbol,
                "interval": extra_params.get("interval", "15"),
                "klines_count": len(klines),
                "klines": klines,
                "content": [{
                    "text": f"Fetched {len(klines)} candles for {symbol}"
                }]
            }

        return {
            "status": "error",
            "content": [{"text": f"Failed to get kline data"}]
        }

    elif action == "place_order":
        if not symbol:
            return {"status": "error", "content": [{"text": "symbol required"}]}

        required = ["side", "orderType", "qty"]
        missing = [k for k in required if k not in extra_params]
        if missing:
            return {
                "status": "error",
                "content": [{"text": f"Missing required parameters: {missing}"}]
            }

        params = {
            "category": category,
            "symbol": symbol,
            "side": extra_params["side"],
            "orderType": extra_params["orderType"],
            "qty": str(extra_params["qty"])
        }

        # Optional parameters
        optional = ["price", "timeInForce", "positionIdx", "orderLinkId",
                   "stopLoss", "takeProfit", "reduceOnly"]
        for key in optional:
            if key in extra_params:
                params[key] = str(extra_params[key])

        result = _make_request("POST", "/v5/order/create", params)

        if result.get("retCode") == 0:
            order = result["result"]
            return {
                "status": "success",
                "order_id": order["orderId"],
                "order_link_id": order.get("orderLinkId"),
                "content": [{
                    "text": f"Order placed: {extra_params['side']} {symbol} | Qty: {extra_params['qty']} | Order ID: {order['orderId']}"
                }]
            }
        else:
            return {
                "status": "error",
                "content": [{"text": f"Order failed: {result.get('retMsg', 'Unknown error')}"}]
            }

    elif action == "cancel_order":
        if not symbol:
            return {"status": "error", "content": [{"text": "symbol required"}]}
        if "orderId" not in extra_params and "orderLinkId" not in extra_params:
            return {
                "status": "error",
                "content": [{"text": "orderId or orderLinkId required"}]
            }

        params = {"category": category, "symbol": symbol}
        if "orderId" in extra_params:
            params["orderId"] = extra_params["orderId"]
        if "orderLinkId" in extra_params:
            params["orderLinkId"] = extra_params["orderLinkId"]

        result = _make_request("POST", "/v5/order/cancel", params)

        if result.get("retCode") == 0:
            return {
                "status": "success",
                "content": [{"text": f"Order cancelled: {symbol}"}]
            }
        else:
            return {
                "status": "error",
                "content": [{"text": f"Cancel failed: {result.get('retMsg', 'Unknown error')}"}]
            }

    elif action == "set_leverage":
        if not symbol:
            return {"status": "error", "content": [{"text": "symbol required"}]}

        params = {
            "category": category,
            "symbol": symbol,
            "buyLeverage": str(extra_params.get("buyLeverage", 10)),
            "sellLeverage": str(extra_params.get("sellLeverage", 10))
        }

        result = _make_request("POST", "/v5/position/set-leverage", params)

        if result.get("retCode") == 0:
            return {
                "status": "success",
                "content": [{
                    "text": f"Leverage set: {symbol} | Buy: {params['buyLeverage']}x | Sell: {params['sellLeverage']}x"
                }]
            }
        else:
            return {
                "status": "error",
                "content": [{"text": f"Set leverage failed: {result.get('retMsg', 'Unknown error')}"}]
            }

    elif action == "set_trading_stop":
        if not symbol:
            return {"status": "error", "content": [{"text": "symbol required"}]}

        params = {"category": category, "symbol": symbol}

        if "positionIdx" in extra_params:
            params["positionIdx"] = str(extra_params["positionIdx"])

        if "stopLoss" in extra_params:
            params["stopLoss"] = str(extra_params["stopLoss"])
        if "takeProfit" in extra_params:
            params["takeProfit"] = str(extra_params["takeProfit"])

        if "stopLoss" not in params and "takeProfit" not in params:
            return {
                "status": "error",
                "content": [{"text": "stopLoss or takeProfit required"}]
            }

        result = _make_request("POST", "/v5/position/trading-stop", params)

        if result.get("retCode") == 0:
            msg = f"TP/SL set: {symbol}"
            if "stopLoss" in params:
                msg += f" | SL: ${params['stopLoss']}"
            if "takeProfit" in params:
                msg += f" | TP: ${params['takeProfit']}"

            return {
                "status": "success",
                "content": [{"text": msg}]
            }
        else:
            return {
                "status": "error",
                "content": [{"text": f"Set TP/SL failed: {result.get('retMsg', 'Unknown error')}"}]
            }

    elif action == "update_trailing_stop":
        # Update trailing stop to breakeven after 1% profit
        if not symbol:
            return {"status": "error", "content": [{"text": "symbol required"}]}

        # Get current position
        pos_result = _make_request("GET", "/v5/position/list", {
            "category": category,
            "symbol": symbol
        })

        if pos_result.get("retCode") != 0:
            return {
                "status": "error",
                "content": [{"text": "Failed to get position"}]
            }

        positions = pos_result["result"]["list"]
        if not positions or float(positions[0].get("size", 0)) == 0:
            return {
                "status": "error",
                "content": [{"text": f"No open position found for {symbol}"}]
            }

        position = positions[0]
        entry_price = float(position["avgPrice"])
        current_price = float(extra_params.get("current_price", 0))
        if current_price == 0:
            current_price = float(position["markPrice"])

        side = position["side"]

        # Calculate profit percentage
        if side == "Buy":
            profit_pct = (current_price - entry_price) / entry_price * 100
        else:  # Sell
            profit_pct = (entry_price - current_price) / entry_price * 100

        # Only move to breakeven if profit >= 1%
        if profit_pct >= 1.0:
            result = _make_request("POST", "/v5/position/trading-stop", {
                "category": category,
                "symbol": symbol,
                "positionIdx": str(position.get("positionIdx", 0)),
                "stopLoss": str(entry_price)
            })

            if result.get("retCode") == 0:
                return {
                    "status": "success",
                    "content": [{
                        "text": f"Trailing stop updated: {symbol} SL moved to breakeven ${entry_price} (profit: {profit_pct:.2f}%)"
                    }]
                }
            else:
                return {
                    "status": "error",
                    "content": [{"text": f"Failed to update trailing stop: {result.get('retMsg')}"}]
                }
        else:
            return {
                "status": "success",
                "content": [{
                    "text": f"No update needed: {symbol} profit {profit_pct:.2f}% < 1% threshold"
                }]
            }

    else:
        return {
            "status": "error",
            "content": [{
                "text": f"Unknown action: {action}. Valid actions: get_balance, get_positions, get_ticker, get_kline, place_order, cancel_order, set_leverage, set_trading_stop, update_trailing_stop"
            }]
        }
