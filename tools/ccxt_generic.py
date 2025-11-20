#!/usr/bin/env python3
"""
CCXT Generic Tool - Full CCXT package access
Provides access to all CCXT functionality for any exchange
"""
import ccxt
import os
from typing import Dict, Any, List
from strands import tool

@tool
def ccxt_generic(
    exchange: str = "bybit",
    method: str = None,
    args: str = "[]",
    kwargs: str = "{}",
    api_key: str = None,
    api_secret: str = None,
) -> Dict[str, Any]:
    """
    Generic CCXT tool - call any CCXT method on any exchange.
    
    Args:
        exchange: Exchange name (e.g., "bybit", "binance", "coinbase")
        method: CCXT method to call (e.g., "fetch_balance", "fetch_ticker", "create_order")
        args: JSON string of positional arguments (e.g., '["BTC/USDT"]')
        kwargs: JSON string of keyword arguments (e.g., '{"type": "future"}')
        api_key: API key (reads from env if not provided)
        api_secret: API secret (reads from env if not provided)
    
    Returns:
        Dict with status and result
    
    Examples:
        # Fetch ticker
        ccxt_generic(exchange="bybit", method="fetch_ticker", args='["BTC/USDT"]')
        
        # Fetch balance
        ccxt_generic(exchange="bybit", method="fetch_balance")
        
        # Create order
        ccxt_generic(exchange="bybit", method="create_order", args='["BTC/USDT", "limit", "buy", 0.001, 50000]')
    """
    import json
    
    try:
        # Parse args and kwargs
        args_list = json.loads(args) if isinstance(args, str) else args
        kwargs_dict = json.loads(kwargs) if isinstance(kwargs, str) else kwargs
        
        # Get API credentials
        if not api_key:
            api_key = os.getenv("BYBIT_API_KEY") if exchange == "bybit" else os.getenv(f"{exchange.upper()}_API_KEY")
        if not api_secret:
            api_secret = os.getenv("BYBIT_API_SECRET") if exchange == "bybit" else os.getenv(f"{exchange.upper()}_API_SECRET")
        
        # Get testnet flag
        testnet = os.getenv("BYBIT_TESTNET", "false").lower() == "true" if exchange == "bybit" else False
        
        # Initialize exchange
        exchange_class = getattr(ccxt, exchange)
        exchange_instance = exchange_class({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'testnet': testnet
            }
        })
        
        # If no method specified, list available methods
        if not method:
            methods = [m for m in dir(exchange_instance) if not m.startswith('_') and callable(getattr(exchange_instance, m))]
            public_methods = [m for m in methods if not m.startswith('private')]
            
            return {
                "status": "success",
                "content": [{
                    "text": f"📚 Available CCXT methods for {exchange}:\n\n"
                            f"Public methods ({len(public_methods)}):\n" + "\n".join(f"  • {m}" for m in public_methods[:20]) +
                            f"\n\n... and {len(methods) - 20} more.\n\n"
                            f"Usage: ccxt_generic(exchange='{exchange}', method='fetch_ticker', args='[\"BTC/USDT\"]')"
                }]
            }
        
        # Call the method
        method_func = getattr(exchange_instance, method)
        result = method_func(*args_list, **kwargs_dict)
        
        # Format result
        result_str = json.dumps(result, indent=2, default=str)
        
        # Truncate if too long
        if len(result_str) > 5000:
            result_str = result_str[:5000] + "\n\n... (truncated, result too large)"
        
        return {
            "status": "success",
            "content": [{
                "text": f"✅ {exchange}.{method}() result:\n\n```json\n{result_str}\n```"
            }]
        }
    
    except AttributeError as e:
        return {
            "status": "error",
            "content": [{"text": f"Method '{method}' not found for exchange '{exchange}'. Use ccxt_generic(exchange='{exchange}') to list available methods."}]
        }
    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"CCXT error: {str(e)}"}]
        }
