#!/usr/bin/env python3
"""
Order Tool - Order management (open, close, list)
Handles order lifecycle using CCXT
"""
import ccxt
import os
from typing import Dict, Any
from datetime import datetime
from strands import tool


@tool
def order(
    action: str,
    symbol: str = None,
    side: str = None,
    amount: float = None,
    price: float = None,
    order_type: str = "market",
    order_id: str = None,
    exchange: str = "bybit",
) -> Dict[str, Any]:
    """
    Order management tool.
    
    Args:
        action: "open" (create order), "close" (cancel order), "list" (list orders), "close_all" (close all positions)
        symbol: Trading pair (e.g., "BTC/USDT:USDT")
        side: "buy" or "sell"
        amount: Order amount
        price: Limit price (optional, for limit orders)
        order_type: "market" or "limit" (default: market)
        order_id: Order ID (for close action)
        exchange: Exchange name (default: bybit)
    
    Returns:
        Dict with status and order data
    
    Examples:
        # Open market buy
        order(action="open", symbol="BTC/USDT:USDT", side="buy", amount=0.001)
        
        # Open limit sell
        order(action="open", symbol="BTC/USDT:USDT", side="sell", amount=0.001, price=95000, order_type="limit")
        
        # List open orders
        order(action="list", symbol="BTC/USDT:USDT")
        
        # Close specific order
        order(action="close", symbol="BTC/USDT:USDT", order_id="123456")
        
        # Close all positions
        order(action="close_all")
    """
    try:
        # Get API credentials
        api_key = os.getenv("BYBIT_API_KEY")
        api_secret = os.getenv("BYBIT_API_SECRET")
        testnet = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
        
        if not api_key or not api_secret:
            return {
                "status": "error",
                "content": [{"text": "API credentials not found. Set BYBIT_API_KEY and BYBIT_API_SECRET"}]
            }
        
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
        
        if action == "open":
            if not symbol or not side or amount is None:
                return {
                    "status": "error",
                    "content": [{"text": "Missing required parameters: symbol, side, amount"}]
                }
            
            # Create order
            if order_type == "market":
                result = exchange_instance.create_market_order(symbol, side, amount)
            elif order_type == "limit":
                if price is None:
                    return {
                        "status": "error",
                        "content": [{"text": "Price required for limit orders"}]
                    }
                result = exchange_instance.create_limit_order(symbol, side, amount, price)
            else:
                return {
                    "status": "error",
                    "content": [{"text": f"Unknown order_type: {order_type}. Valid: market, limit"}]
                }
            
            return {
                "status": "success",
                "content": [{
                    "text": f"✅ Order opened:\n\n"
                            f"📊 Symbol: {result.get('symbol')}\n"
                            f"🔄 Side: {result.get('side')}\n"
                            f"💰 Amount: {result.get('amount')}\n"
                            f"💵 Price: {result.get('price')}\n"
                            f"📝 Order ID: {result.get('id')}\n"
                            f"🕐 Timestamp: {result.get('datetime')}"
                }]
            }
        
        elif action == "close":
            if not symbol or not order_id:
                return {
                    "status": "error",
                    "content": [{"text": "Missing required parameters: symbol, order_id"}]
                }
            
            result = exchange_instance.cancel_order(order_id, symbol)
            
            return {
                "status": "success",
                "content": [{
                    "text": f"✅ Order closed:\n\n"
                            f"📝 Order ID: {result.get('id')}\n"
                            f"📊 Symbol: {result.get('symbol')}"
                }]
            }
        
        elif action == "list":
            if symbol:
                # List orders for specific symbol
                open_orders = exchange_instance.fetch_open_orders(symbol)
            else:
                # List all open orders
                open_orders = exchange_instance.fetch_open_orders()
            
            if not open_orders:
                return {
                    "status": "success",
                    "content": [{"text": "No open orders"}]
                }
            
            text = f"📋 Open Orders ({len(open_orders)}):\n\n"
            for i, o in enumerate(open_orders, 1):
                text += f"{i}. {o['symbol']} | {o['side']} {o['amount']} @ {o.get('price', 'market')}\n"
                text += f"   ID: {o['id']} | Status: {o['status']}\n\n"
            
            return {
                "status": "success",
                "content": [{"text": text}]
            }
        
        elif action == "close_all":
            # Get all positions
            positions = exchange_instance.fetch_positions()
            active_positions = [p for p in positions if float(p.get('contracts', 0)) != 0]
            
            if not active_positions:
                return {
                    "status": "success",
                    "content": [{"text": "No active positions to close"}]
                }
            
            closed = []
            for position in active_positions:
                try:
                    symbol = position['symbol']
                    size = abs(float(position['contracts']))
                    side = 'sell' if float(position['contracts']) > 0 else 'buy'
                    
                    # Close position with market order
                    result = exchange_instance.create_market_order(symbol, side, size, {'reduceOnly': True})
                    closed.append(f"{symbol}: {side} {size}")
                except Exception as e:
                    closed.append(f"{symbol}: ERROR - {str(e)}")
            
            return {
                "status": "success",
                "content": [{
                    "text": f"✅ Closed {len(closed)} positions:\n\n" + "\n".join(closed)
                }]
            }
        
        else:
            return {
                "status": "error",
                "content": [{"text": f"Unknown action: {action}. Valid: open, close, list, close_all"}]
            }
    
    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"Order tool error: {str(e)}"}]
        }
