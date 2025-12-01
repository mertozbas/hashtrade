"""
4H Range Tool - 4-Hour Range Breakout Strategy
Based on the first 4-hour candle of the day (New York time)
"""
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from strands import tool


def get_ny_midnight_utc() -> datetime:
    """Get today's midnight in New York time, converted to UTC"""
    # New York is UTC-5 (EST) or UTC-4 (EDT)
    # For simplicity, assume UTC-5
    now_utc = datetime.utcnow()

    # NY midnight in UTC is 05:00 UTC (during EST)
    ny_midnight_utc = now_utc.replace(hour=5, minute=0, second=0, microsecond=0)

    # If current time is before NY midnight, use previous day
    if now_utc.hour < 5:
        ny_midnight_utc -= timedelta(days=1)

    return ny_midnight_utc


@tool
def get_4h_range(
    symbol: str,
    klines_4h: str = None
) -> Dict[str, Any]:
    """
    Get the 4-hour range (high/low of first 4H candle of the day).

    Args:
        symbol: Trading pair (e.g., BTCUSDT)
        klines_4h: JSON string of 4H kline data (optional, will fetch if not provided)

    Returns:
        Dict with range_high, range_low, and status

    The 4H range is based on New York time:
    - First 4H candle: 00:00 - 04:00 NY time
    - In UTC: 05:00 - 09:00 UTC (during EST)
    """
    try:
        # Parse or fetch klines
        if klines_4h and isinstance(klines_4h, str):
            klines = json.loads(klines_4h)
        elif klines_4h:
            klines = klines_4h
        else:
            # Fetch from bybit
            from .bybit_v5 import bybit_v5
            result = bybit_v5(
                action="get_kline",
                symbol=symbol.replace("/", "").replace(":USDT", ""),
                kwargs=json.dumps({"interval": "240", "limit": 10})  # 240 = 4 hours
            )
            if result.get("status") == "error":
                return result
            klines = result.get("klines", [])

        if not klines or len(klines) < 1:
            return {
                "status": "error",
                "content": [{"text": f"No 4H kline data for {symbol}"}]
            }

        # Bybit returns newest first, so reverse for chronological order
        klines = list(reversed(klines))

        # Find the first 4H candle of today (NY time)
        ny_midnight = get_ny_midnight_utc()
        first_candle_start = int(ny_midnight.timestamp() * 1000)

        # Find the candle that starts at or after NY midnight
        first_candle = None
        for k in klines:
            candle_time = int(k[0])
            if candle_time >= first_candle_start:
                first_candle = k
                break

        # If not found, use the most recent completed candle
        if not first_candle:
            # Use second-to-last candle (last one might be forming)
            first_candle = klines[-2] if len(klines) > 1 else klines[-1]

        # Parse candle: [timestamp, open, high, low, close, volume]
        timestamp = int(first_candle[0])
        open_price = float(first_candle[1])
        high_price = float(first_candle[2])
        low_price = float(first_candle[3])
        close_price = float(first_candle[4])
        volume = float(first_candle[5])

        candle_time = datetime.utcfromtimestamp(timestamp / 1000)
        range_size = high_price - low_price
        range_pct = (range_size / low_price) * 100

        # Check if candle is closed
        now = datetime.utcnow()
        candle_end = candle_time + timedelta(hours=4)
        is_closed = now >= candle_end

        return {
            "status": "success",
            "symbol": symbol,
            "range_high": high_price,
            "range_low": low_price,
            "range_size": range_size,
            "range_pct": range_pct,
            "candle_time": candle_time.isoformat(),
            "is_closed": is_closed,
            "open": open_price,
            "close": close_price,
            "volume": volume,
            "content": [{
                "text": f"4H Range for {symbol}:\n"
                        f"High: ${high_price:,.2f}\n"
                        f"Low: ${low_price:,.2f}\n"
                        f"Range: ${range_size:,.2f} ({range_pct:.2f}%)\n"
                        f"Time: {candle_time.strftime('%Y-%m-%d %H:%M')} UTC\n"
                        f"Status: {'CLOSED' if is_closed else 'FORMING'}"
            }]
        }

    except Exception as e:
        import traceback
        return {
            "status": "error",
            "content": [{"text": f"4H Range error: {str(e)}\n{traceback.format_exc()}"}]
        }


@tool
def check_range_breakout(
    symbol: str,
    range_high: float,
    range_low: float,
    klines_5m: str = None
) -> Dict[str, Any]:
    """
    Check for breakout and retest setup on 5m timeframe.

    Strategy:
    1. Price breaks OUTSIDE range (candle CLOSES outside)
    2. Price re-enters and CLOSES back INSIDE range
    3. Entry signal generated

    Args:
        symbol: Trading pair
        range_high: 4H range high
        range_low: 4H range low
        klines_5m: JSON string of 5m kline data (optional)

    Returns:
        Dict with signal (LONG, SHORT, or NO_SIGNAL)
    """
    try:
        # Parse or fetch 5m klines
        if klines_5m and isinstance(klines_5m, str):
            klines = json.loads(klines_5m)
        elif klines_5m:
            klines = klines_5m
        else:
            # Fetch from bybit
            from .bybit_v5 import bybit_v5
            result = bybit_v5(
                action="get_kline",
                symbol=symbol.replace("/", "").replace(":USDT", ""),
                kwargs=json.dumps({"interval": "5", "limit": 100})
            )
            if result.get("status") == "error":
                return result
            klines = result.get("klines", [])

        if not klines or len(klines) < 10:
            return {
                "status": "error",
                "content": [{"text": f"Insufficient 5m data for {symbol}"}]
            }

        # Reverse for chronological order (oldest first)
        klines = list(reversed(klines))

        # Parse klines: [timestamp, open, high, low, close, volume]
        closes = [float(k[4]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]

        current_price = closes[-1]

        # Look for breakout + retest pattern in recent candles
        # We need: 1) Close outside range, 2) Close back inside range

        breakout_high = None  # For SHORT setup
        breakout_low = None   # For LONG setup

        # Scan last 50 candles for breakout
        for i in range(len(closes) - 50, len(closes) - 1):
            if i < 0:
                continue

            close = closes[i]

            # Breakout above range high
            if close > range_high:
                breakout_high = {
                    "index": i,
                    "price": close,
                    "extreme": max(highs[i:i+5]) if i+5 <= len(highs) else highs[i]
                }

            # Breakout below range low
            if close < range_low:
                breakout_low = {
                    "index": i,
                    "price": close,
                    "extreme": min(lows[i:i+5]) if i+5 <= len(lows) else lows[i]
                }

        # Check for retest (current candle back inside range)
        current_inside = range_low <= current_price <= range_high
        prev_close = closes[-2] if len(closes) > 1 else current_price

        signal = "NO_SIGNAL"
        entry_price = None
        stop_loss = None
        direction = None

        # SHORT setup: Broke above, now back inside
        if breakout_high and current_inside and prev_close > range_high:
            signal = "SHORT"
            direction = "SHORT"
            entry_price = current_price
            stop_loss = breakout_high["extreme"]

        # LONG setup: Broke below, now back inside
        elif breakout_low and current_inside and prev_close < range_low:
            signal = "LONG"
            direction = "LONG"
            entry_price = current_price
            stop_loss = breakout_low["extreme"]

        # Check if currently breaking out (potential future setup)
        elif current_price > range_high:
            signal = "BREAKING_HIGH"
        elif current_price < range_low:
            signal = "BREAKING_LOW"

        # Calculate R:R if we have a setup
        if entry_price and stop_loss:
            sl_distance = abs(entry_price - stop_loss)
            sl_pct = (sl_distance / entry_price) * 100

            # TP at 2:1 R:R
            if direction == "LONG":
                take_profit = entry_price + (sl_distance * 2)
            else:
                take_profit = entry_price - (sl_distance * 2)

            return {
                "status": "success",
                "signal": signal,
                "direction": direction,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "sl_distance": sl_distance,
                "sl_pct": sl_pct,
                "rr_ratio": 2.0,
                "range_high": range_high,
                "range_low": range_low,
                "content": [{
                    "text": f"SIGNAL: {signal} {symbol}\n"
                            f"Entry: ${entry_price:,.2f}\n"
                            f"SL: ${stop_loss:,.2f} ({sl_pct:.2f}%)\n"
                            f"TP: ${take_profit:,.2f} (2:1 R:R)\n"
                            f"Range: ${range_low:,.2f} - ${range_high:,.2f}"
                }]
            }

        return {
            "status": "success",
            "signal": signal,
            "current_price": current_price,
            "range_high": range_high,
            "range_low": range_low,
            "inside_range": current_inside,
            "content": [{
                "text": f"NO SETUP | {symbol}\n"
                        f"Price: ${current_price:,.2f}\n"
                        f"Range: ${range_low:,.2f} - ${range_high:,.2f}\n"
                        f"Inside range: {current_inside}\n"
                        f"Status: {signal}"
            }]
        }

    except Exception as e:
        import traceback
        return {
            "status": "error",
            "content": [{"text": f"Breakout check error: {str(e)}\n{traceback.format_exc()}"}]
        }


@tool
def scan_4h_range_setups(
    symbols: str = '["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "CRVUSDT"]'
) -> Dict[str, Any]:
    """
    Scan multiple symbols for 4H range breakout setups.

    Args:
        symbols: JSON array of symbols to scan

    Returns:
        Dict with all setups found
    """
    try:
        symbol_list = json.loads(symbols) if isinstance(symbols, str) else symbols

        setups = []
        scanned = []

        for symbol in symbol_list:
            # Get 4H range
            range_result = get_4h_range(symbol=symbol)

            if range_result.get("status") == "error":
                scanned.append({"symbol": symbol, "error": "Failed to get 4H range"})
                continue

            if not range_result.get("is_closed", False):
                scanned.append({"symbol": symbol, "status": "4H candle still forming"})
                continue

            range_high = range_result["range_high"]
            range_low = range_result["range_low"]

            # Check for breakout setup
            breakout_result = check_range_breakout(
                symbol=symbol,
                range_high=range_high,
                range_low=range_low
            )

            if breakout_result.get("status") == "error":
                scanned.append({"symbol": symbol, "error": "Failed to check breakout"})
                continue

            signal = breakout_result.get("signal", "NO_SIGNAL")

            if signal in ["LONG", "SHORT"]:
                setups.append({
                    "symbol": symbol,
                    "signal": signal,
                    "entry": breakout_result.get("entry_price"),
                    "sl": breakout_result.get("stop_loss"),
                    "tp": breakout_result.get("take_profit"),
                    "sl_pct": breakout_result.get("sl_pct")
                })

            scanned.append({
                "symbol": symbol,
                "signal": signal,
                "range": f"${range_low:,.2f} - ${range_high:,.2f}"
            })

        # Build summary
        summary_lines = [f"Scanned {len(symbol_list)} symbols:"]

        for s in scanned:
            if "error" in s:
                summary_lines.append(f"  {s['symbol']}: ERROR - {s['error']}")
            elif "status" in s:
                summary_lines.append(f"  {s['symbol']}: {s['status']}")
            else:
                summary_lines.append(f"  {s['symbol']}: {s['signal']} | Range: {s['range']}")

        if setups:
            summary_lines.append(f"\nSETUPS FOUND: {len(setups)}")
            for setup in setups:
                summary_lines.append(
                    f"  {setup['signal']} {setup['symbol']} @ ${setup['entry']:,.2f} "
                    f"| SL: ${setup['sl']:,.2f} | TP: ${setup['tp']:,.2f}"
                )
        else:
            summary_lines.append("\nNo valid setups found.")

        return {
            "status": "success",
            "setups": setups,
            "setups_count": len(setups),
            "scanned": scanned,
            "content": [{"text": "\n".join(summary_lines)}]
        }

    except Exception as e:
        import traceback
        return {
            "status": "error",
            "content": [{"text": f"Scan error: {str(e)}\n{traceback.format_exc()}"}]
        }
