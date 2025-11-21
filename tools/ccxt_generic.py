#!/usr/bin/env python3
"""
CCXT Generic Tool - Full CCXT package access with advanced features
Provides access to all CCXT functionality for any exchange
"""
import ccxt
import os
import asyncio
from typing import Dict, Any, List, Optional
from strands import tool

@tool
def ccxt_generic(
    exchange: str = "bybit",
    method: str = None,
    args: str = "[]",
    kwargs: str = "{}",
    api_key: str = None,
    api_secret: str = None,
    async_mode: bool = False,
) -> Dict[str, Any]:
    """
    Generic CCXT tool - call any CCXT method on any exchange.
    
    Returns:
        Dict with status and result
    
    Examples:
        # Fetch ticker
        ccxt_generic(exchange="bybit", method="fetch_ticker", args='["BTC/USDT"]')
        
        # Fetch balance
        ccxt_generic(exchange="bybit", method="fetch_balance")
        
        # Create order
        ccxt_generic(exchange="bybit", method="create_order", args='["BTC/USDT", "limit", "buy", 0.001, 50000]')
        
        # Fetch OHLCV with limit
        ccxt_generic(exchange="bybit", method="fetch_ohlcv", args='["BTC/USDT", "1h", null, 100]')
        
        # Fetch positions (futures)
        ccxt_generic(exchange="bybit", method="fetch_positions")
        
        # Transfer between accounts
        ccxt_generic(exchange="bybit", method="transfer", args='["USDT", 100, "spot", "future"]')
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
        
        # Initialize exchange (sync only - CCXT 4.x changed async structure)
        exchange_class = getattr(ccxt, exchange)
        exchange_instance = exchange_class({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'testnet': testnet,
                'recvWindow': 10000,
            }
        })
        
        # If no method specified, list available methods
        if not method:
            methods = [m for m in dir(exchange_instance) if not m.startswith('_') and callable(getattr(exchange_instance, m))]
            
            # Categorize methods
            public_methods = [m for m in methods if not m.startswith('private') and not 'sign' in m.lower()]
            fetch_methods = [m for m in public_methods if m.startswith('fetch_')]
            create_methods = [m for m in public_methods if m.startswith('create_')]
            watch_methods = [m for m in public_methods if m.startswith('watch_')]
            other_methods = [m for m in public_methods if m not in fetch_methods + create_methods + watch_methods]
            
            return {
                "status": "success",
                "content": [{
                    "text": f"📚 Available CCXT methods for {exchange}:\n\n"
                            f"**Fetch Methods ({len(fetch_methods)}):**\n" + 
                            "\n".join(f"  • {m}" for m in fetch_methods[:15]) +
                            f"\n  ... and {len(fetch_methods) - 15} more\n\n" +
                            f"**Create Methods ({len(create_methods)}):**\n" + 
                            "\n".join(f"  • {m}" for m in create_methods) +
                            f"\n\n**Watch Methods ({len(watch_methods)}):**\n" + 
                            "\n".join(f"  • {m}" for m in watch_methods[:10]) +
                            f"\n\n**Other Methods ({len(other_methods)}):**\n" + 
                            "\n".join(f"  • {m}" for m in other_methods[:10]) +
                            f"\n\nUsage: ccxt_generic(exchange='{exchange}', method='fetch_ticker', args='[\"BTC/USDT\"]')"
                }]
            }
        
        # Call the method
        method_func = getattr(exchange_instance, method)
        result = method_func(*args_list, **kwargs_dict)
        
        # Format result
        result_str = json.dumps(result, indent=2, default=str)
        
        # Truncate if too long
        max_length = 8000
        if len(result_str) > max_length:
            result_str = result_str[:max_length] + f"\n\n... (truncated, showing first {max_length} chars of {len(result_str)})"
        
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
            "content": [{"text": f"CCXT error: {str(e)}\n\nType: {type(e).__name__}"}]
        }


@tool
def ccxt_multi_exchange_orderbook(
    exchanges: str = '["binance", "bybit", "okx"]',
    symbol: str = "BTC/USDT",
) -> Dict[str, Any]:
    """
    Fetch orderbook from multiple exchanges simultaneously for arbitrage analysis.
    
    Args:
        exchanges: JSON array of exchange names
        symbol: Trading pair symbol
    
    Returns:
        Dict with orderbooks from all exchanges
    """
    import json
    
    try:
        exchanges_list = json.loads(exchanges) if isinstance(exchanges, str) else exchanges
        results = []
        
        # Fetch orderbooks sequentially (CCXT 4.x doesn't have async_support)
        for exchange_id in exchanges_list:
            try:
                exchange_class = getattr(ccxt, exchange_id)
                exchange = exchange_class({'enableRateLimit': True})
                
                exchange.load_markets()
                orderbook = exchange.fetch_order_book(symbol)
                
                results.append({
                    'exchange': exchange_id,
                    'symbol': symbol,
                    'best_bid': orderbook['bids'][0] if orderbook['bids'] else None,
                    'best_ask': orderbook['asks'][0] if orderbook['asks'] else None,
                    'bid_depth': len(orderbook['bids']),
                    'ask_depth': len(orderbook['asks']),
                })
            except Exception as e:
                results.append({
                    'exchange': exchange_id,
                    'error': str(e)
                })
        
        # Calculate arbitrage opportunities
        valid_results = [r for r in results if 'error' not in r]
        if len(valid_results) >= 2:
            # Find best bid and best ask across exchanges
            best_bid_exchange = max(valid_results, key=lambda x: x['best_bid'][0] if x['best_bid'] else 0)
            best_ask_exchange = min(valid_results, key=lambda x: x['best_ask'][0] if x['best_ask'] else float('inf'))
            
            spread = best_bid_exchange['best_bid'][0] - best_ask_exchange['best_ask'][0] if best_bid_exchange['best_bid'] and best_ask_exchange['best_ask'] else 0
            spread_pct = (spread / best_ask_exchange['best_ask'][0] * 100) if best_ask_exchange['best_ask'] and best_ask_exchange['best_ask'][0] > 0 else 0
            
            arbitrage_info = f"\n\n🎯 **Arbitrage Opportunity:**\n"
            arbitrage_info += f"Buy on {best_ask_exchange['exchange']} @ ${best_ask_exchange['best_ask'][0]:.2f}\n"
            arbitrage_info += f"Sell on {best_bid_exchange['exchange']} @ ${best_bid_exchange['best_bid'][0]:.2f}\n"
            arbitrage_info += f"Potential profit: ${spread:.2f} ({spread_pct:.3f}%)"
        else:
            arbitrage_info = ""
        
        result_text = "📚 Multi-Exchange Orderbook Comparison:\n\n"
        for r in results:
            if 'error' in r:
                result_text += f"❌ {r['exchange']}: {r['error']}\n"
            else:
                result_text += f"✅ {r['exchange']}: Best bid ${r['best_bid'][0]:.2f}, "
                result_text += f"Best ask ${r['best_ask'][0]:.2f}\n"
        
        result_text += arbitrage_info
        
        return {
            "status": "success",
            "content": [{"text": result_text}]
        }
    
    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"Multi-exchange fetch error: {str(e)}"}]
        }
