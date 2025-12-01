"""
Analysis Tool - Smart Money Concepts Analysis
Market structure, Order Blocks, FVG, Liquidity detection
"""
import os
import json
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from strands import tool


def calculate_ema(closes: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average"""
    if len(closes) < period:
        return []

    ema = [sum(closes[:period]) / period]  # SMA for first value
    multiplier = 2 / (period + 1)

    for price in closes[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])

    # Pad with None for alignment
    return [None] * (period - 1) + ema


def calculate_rsi(closes: List[float], period: int = 14) -> List[float]:
    """Calculate Relative Strength Index"""
    if len(closes) < period + 1:
        return []

    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]

    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsi = []
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100 - (100 / (1 + rs)))

    return [None] * (period + 1) + rsi


def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    """Calculate Average True Range"""
    if len(closes) < period + 1:
        return []

    tr = []
    for i in range(1, len(closes)):
        high_low = highs[i] - lows[i]
        high_close = abs(highs[i] - closes[i-1])
        low_close = abs(lows[i] - closes[i-1])
        tr.append(max(high_low, high_close, low_close))

    atr = [sum(tr[:period]) / period]
    for i in range(period, len(tr)):
        atr.append((atr[-1] * (period - 1) + tr[i]) / period)

    return [None] * period + atr


def find_swing_points(highs: List[float], lows: List[float], lookback: int = 3) -> Dict[str, List]:
    """Find swing highs and swing lows"""
    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(highs) - lookback):
        # Swing High: higher than lookback candles on both sides
        is_swing_high = all(highs[i] >= highs[i-j] for j in range(1, lookback+1)) and \
                        all(highs[i] >= highs[i+j] for j in range(1, lookback+1))
        if is_swing_high:
            swing_highs.append({"index": i, "price": highs[i]})

        # Swing Low: lower than lookback candles on both sides
        is_swing_low = all(lows[i] <= lows[i-j] for j in range(1, lookback+1)) and \
                       all(lows[i] <= lows[i+j] for j in range(1, lookback+1))
        if is_swing_low:
            swing_lows.append({"index": i, "price": lows[i]})

    return {"swing_highs": swing_highs, "swing_lows": swing_lows}


def detect_market_structure(swing_highs: List[Dict], swing_lows: List[Dict]) -> Dict[str, Any]:
    """
    Detect market structure: Uptrend (HH, HL) or Downtrend (LH, LL)
    """
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {"trend": "undefined", "structure": []}

    structure = []

    # Check last 2 swing highs
    last_highs = swing_highs[-2:]
    if last_highs[1]["price"] > last_highs[0]["price"]:
        structure.append("HH")  # Higher High
    else:
        structure.append("LH")  # Lower High

    # Check last 2 swing lows
    last_lows = swing_lows[-2:]
    if last_lows[1]["price"] > last_lows[0]["price"]:
        structure.append("HL")  # Higher Low
    else:
        structure.append("LL")  # Lower Low

    # Determine trend
    if "HH" in structure and "HL" in structure:
        trend = "uptrend"
    elif "LH" in structure and "LL" in structure:
        trend = "downtrend"
    else:
        trend = "ranging"

    return {
        "trend": trend,
        "structure": structure,
        "last_swing_high": swing_highs[-1] if swing_highs else None,
        "last_swing_low": swing_lows[-1] if swing_lows else None
    }


def find_order_blocks(opens: List[float], highs: List[float], lows: List[float],
                      closes: List[float], lookback: int = 50) -> List[Dict]:
    """
    Find Order Blocks - Last bullish/bearish candle before a strong move
    """
    order_blocks = []

    # Only look at recent candles
    start_idx = max(0, len(closes) - lookback)

    for i in range(start_idx + 2, len(closes) - 1):
        # Bullish Order Block: Bearish candle followed by strong bullish move
        if closes[i-1] < opens[i-1]:  # Previous candle is bearish
            # Check for strong bullish move after
            move_size = (closes[i] - closes[i-1]) / closes[i-1] * 100
            if move_size > 0.3:  # At least 0.3% move
                order_blocks.append({
                    "type": "bullish",
                    "index": i - 1,
                    "top": opens[i-1],
                    "bottom": closes[i-1],
                    "strength": move_size
                })

        # Bearish Order Block: Bullish candle followed by strong bearish move
        if closes[i-1] > opens[i-1]:  # Previous candle is bullish
            # Check for strong bearish move after
            move_size = (closes[i-1] - closes[i]) / closes[i-1] * 100
            if move_size > 0.3:  # At least 0.3% move
                order_blocks.append({
                    "type": "bearish",
                    "index": i - 1,
                    "top": closes[i-1],
                    "bottom": opens[i-1],
                    "strength": move_size
                })

    # Return most recent order blocks
    return order_blocks[-5:] if len(order_blocks) > 5 else order_blocks


def find_fair_value_gaps(highs: List[float], lows: List[float], lookback: int = 50) -> List[Dict]:
    """
    Find Fair Value Gaps (FVG) - Imbalance between 3 candles
    """
    fvgs = []

    start_idx = max(0, len(highs) - lookback)

    for i in range(start_idx + 2, len(highs)):
        # Bullish FVG: Gap between candle 1's high and candle 3's low
        if lows[i] > highs[i-2]:
            gap_size = (lows[i] - highs[i-2]) / highs[i-2] * 100
            if gap_size > 0.1:  # At least 0.1% gap
                fvgs.append({
                    "type": "bullish",
                    "index": i - 1,
                    "top": lows[i],
                    "bottom": highs[i-2],
                    "gap_pct": gap_size
                })

        # Bearish FVG: Gap between candle 1's low and candle 3's high
        if highs[i] < lows[i-2]:
            gap_size = (lows[i-2] - highs[i]) / lows[i-2] * 100
            if gap_size > 0.1:  # At least 0.1% gap
                fvgs.append({
                    "type": "bearish",
                    "index": i - 1,
                    "top": lows[i-2],
                    "bottom": highs[i],
                    "gap_pct": gap_size
                })

    return fvgs[-5:] if len(fvgs) > 5 else fvgs


def detect_liquidity_sweep(highs: List[float], lows: List[float], closes: List[float],
                           swing_highs: List[Dict], swing_lows: List[Dict]) -> Dict[str, Any]:
    """
    Detect liquidity sweep - Price takes out swing high/low then reverses
    """
    if not swing_highs or not swing_lows or len(closes) < 3:
        return {"detected": False}

    current_high = highs[-1]
    current_low = lows[-1]
    current_close = closes[-1]
    prev_close = closes[-2]

    # Check for sweep of recent swing high
    for sh in reversed(swing_highs[-3:]):
        if current_high > sh["price"] and current_close < sh["price"]:
            # Swept high but closed below = bearish sweep
            return {
                "detected": True,
                "type": "bearish_sweep",
                "level": sh["price"],
                "description": f"Liquidity sweep above {sh['price']:.2f}, closed below"
            }

    # Check for sweep of recent swing low
    for sl in reversed(swing_lows[-3:]):
        if current_low < sl["price"] and current_close > sl["price"]:
            # Swept low but closed above = bullish sweep
            return {
                "detected": True,
                "type": "bullish_sweep",
                "level": sl["price"],
                "description": f"Liquidity sweep below {sl['price']:.2f}, closed above"
            }

    return {"detected": False}


def find_entry_zone(current_price: float, trend: str, order_blocks: List[Dict],
                    fvgs: List[Dict]) -> Dict[str, Any]:
    """
    Find valid entry zone based on trend direction
    """
    valid_zones = []

    if trend == "uptrend":
        # Look for bullish OBs and FVGs below current price
        for ob in order_blocks:
            if ob["type"] == "bullish" and ob["top"] < current_price:
                distance_pct = (current_price - ob["top"]) / current_price * 100
                if distance_pct < 2:  # Within 2% of current price
                    valid_zones.append({
                        "type": "order_block",
                        "zone_type": "bullish",
                        "entry": ob["top"],
                        "stop": ob["bottom"],
                        "distance_pct": distance_pct
                    })

        for fvg in fvgs:
            if fvg["type"] == "bullish" and fvg["top"] < current_price:
                distance_pct = (current_price - fvg["top"]) / current_price * 100
                if distance_pct < 2:
                    valid_zones.append({
                        "type": "fvg",
                        "zone_type": "bullish",
                        "entry": fvg["top"],
                        "stop": fvg["bottom"],
                        "distance_pct": distance_pct
                    })

    elif trend == "downtrend":
        # Look for bearish OBs and FVGs above current price
        for ob in order_blocks:
            if ob["type"] == "bearish" and ob["bottom"] > current_price:
                distance_pct = (ob["bottom"] - current_price) / current_price * 100
                if distance_pct < 2:
                    valid_zones.append({
                        "type": "order_block",
                        "zone_type": "bearish",
                        "entry": ob["bottom"],
                        "stop": ob["top"],
                        "distance_pct": distance_pct
                    })

        for fvg in fvgs:
            if fvg["type"] == "bearish" and fvg["bottom"] > current_price:
                distance_pct = (fvg["bottom"] - current_price) / current_price * 100
                if distance_pct < 2:
                    valid_zones.append({
                        "type": "fvg",
                        "zone_type": "bearish",
                        "entry": fvg["bottom"],
                        "stop": fvg["top"],
                        "distance_pct": distance_pct
                    })

    # Sort by distance (closest first)
    valid_zones.sort(key=lambda x: x["distance_pct"])

    return {
        "has_zone": len(valid_zones) > 0,
        "zones": valid_zones[:3]  # Top 3 closest zones
    }


@tool
def analyze_market(
    symbol: str,
    klines: str = None,
    timeframe: str = "15"
) -> Dict[str, Any]:
    """
    Comprehensive market analysis using Smart Money Concepts.

    Args:
        symbol: Trading pair (e.g., BTCUSDT, BTC/USDT:USDT, or BTC)
        klines: JSON string of kline data (optional - will auto-fetch)
        timeframe: Timeframe for analysis (default: 15m)

    Returns:
        Dict with market analysis: structure, order blocks, FVG, indicators
    """
    try:
        # Normalize symbol format for Bybit
        clean_symbol = symbol.upper().replace("/", "").replace(":USDT", "").replace("-", "")
        if not clean_symbol.endswith("USDT"):
            clean_symbol = clean_symbol + "USDT"

        # Parse klines if provided as string
        klines_data = None
        if klines:
            if isinstance(klines, str):
                try:
                    klines_data = json.loads(klines)
                except json.JSONDecodeError:
                    klines_data = None
            else:
                klines_data = klines

        # Fetch klines if not provided
        if not klines_data:
            from .bybit_v5 import bybit_v5
            result = bybit_v5(
                action="get_kline",
                symbol=clean_symbol,
                kwargs=json.dumps({"interval": timeframe, "limit": 200})
            )

            if result.get("status") == "error":
                error_msg = result.get("content", [{}])[0].get("text", "Unknown error")
                return {
                    "status": "error",
                    "symbol": clean_symbol,
                    "content": [{"text": f"Failed to fetch klines for {clean_symbol}: {error_msg}"}]
                }

            klines_data = result.get("klines", [])

            if not klines_data:
                return {
                    "status": "error",
                    "symbol": clean_symbol,
                    "content": [{"text": f"No kline data returned for {clean_symbol}. Check if symbol is valid."}]
                }

        if not klines_data or len(klines_data) < 50:
            return {
                "status": "error",
                "content": [{"text": f"Insufficient kline data for {symbol}. Need at least 50 candles."}]
            }

        # Parse OHLCV data (Bybit format: [timestamp, open, high, low, close, volume])
        # Bybit returns newest first, so reverse
        klines_data = list(reversed(klines_data))

        timestamps = [int(k[0]) for k in klines_data]
        opens = [float(k[1]) for k in klines_data]
        highs = [float(k[2]) for k in klines_data]
        lows = [float(k[3]) for k in klines_data]
        closes = [float(k[4]) for k in klines_data]
        volumes = [float(k[5]) for k in klines_data]

        current_price = closes[-1]

        # Calculate indicators
        ema_20 = calculate_ema(closes, 20)
        ema_50 = calculate_ema(closes, 50)
        rsi = calculate_rsi(closes, 14)
        atr = calculate_atr(highs, lows, closes, 14)

        # Get latest indicator values
        current_ema_20 = ema_20[-1] if ema_20 and ema_20[-1] else None
        current_ema_50 = ema_50[-1] if ema_50 and ema_50[-1] else None
        current_rsi = rsi[-1] if rsi and rsi[-1] else None
        current_atr = atr[-1] if atr and atr[-1] else None

        # Find swing points
        swings = find_swing_points(highs, lows, lookback=3)

        # Detect market structure
        structure = detect_market_structure(swings["swing_highs"], swings["swing_lows"])

        # Find order blocks
        order_blocks = find_order_blocks(opens, highs, lows, closes)

        # Find fair value gaps
        fvgs = find_fair_value_gaps(highs, lows)

        # Detect liquidity sweep
        liquidity = detect_liquidity_sweep(highs, lows, closes,
                                           swings["swing_highs"], swings["swing_lows"])

        # Find entry zones
        entry_zones = find_entry_zone(current_price, structure["trend"], order_blocks, fvgs)

        # Volume analysis
        avg_volume = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes)
        current_volume = volumes[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

        # EMA trend confirmation
        ema_trend = None
        if current_ema_20 and current_ema_50:
            if current_price > current_ema_20 > current_ema_50:
                ema_trend = "bullish"
            elif current_price < current_ema_20 < current_ema_50:
                ema_trend = "bearish"
            else:
                ema_trend = "neutral"

        # Build summary
        summary_parts = [
            f"Symbol: {symbol} | Price: ${current_price:.2f}",
            f"Structure: {structure['trend'].upper()} ({', '.join(structure['structure'])})",
            f"EMA Trend: {ema_trend or 'N/A'}",
            f"RSI: {current_rsi:.1f}" if current_rsi else "RSI: N/A",
            f"ATR: ${current_atr:.2f}" if current_atr else "ATR: N/A",
            f"Volume: {volume_ratio:.1f}x avg",
        ]

        if liquidity["detected"]:
            summary_parts.append(f"LIQUIDITY SWEEP: {liquidity['type']}")

        if entry_zones["has_zone"]:
            zone = entry_zones["zones"][0]
            summary_parts.append(f"Entry Zone: {zone['type']} @ ${zone['entry']:.2f} (SL: ${zone['stop']:.2f})")

        return {
            "status": "success",
            "symbol": symbol,
            "current_price": current_price,
            "structure": structure,
            "indicators": {
                "ema_20": current_ema_20,
                "ema_50": current_ema_50,
                "ema_trend": ema_trend,
                "rsi": current_rsi,
                "atr": current_atr,
                "atr_pct": (current_atr / current_price * 100) if current_atr else None,
                "volume_ratio": volume_ratio
            },
            "order_blocks": order_blocks,
            "fair_value_gaps": fvgs,
            "liquidity_sweep": liquidity,
            "entry_zones": entry_zones,
            "swing_points": {
                "recent_high": swings["swing_highs"][-1] if swings["swing_highs"] else None,
                "recent_low": swings["swing_lows"][-1] if swings["swing_lows"] else None
            },
            "content": [{"text": "\n".join(summary_parts)}]
        }

    except Exception as e:
        import traceback
        return {
            "status": "error",
            "content": [{"text": f"Analysis error: {str(e)}\n\n{traceback.format_exc()}"}]
        }


@tool
def check_entry_signal(
    symbol: str,
    analysis: str = None
) -> Dict[str, Any]:
    """
    Check if there's a valid entry signal based on Smart Money strategy.

    Args:
        symbol: Trading pair
        analysis: JSON string of previous analyze_market result (optional)

    Returns:
        Dict with entry signal details or no-trade recommendation
    """
    try:
        # Get fresh analysis if not provided
        if analysis:
            data = json.loads(analysis) if isinstance(analysis, str) else analysis
        else:
            data = analyze_market(symbol=symbol)

        if data.get("status") == "error":
            return data

        structure = data.get("structure", {})
        indicators = data.get("indicators", {})
        liquidity = data.get("liquidity_sweep", {})
        entry_zones = data.get("entry_zones", {})
        current_price = data.get("current_price", 0)

        # Check entry criteria
        signals = []
        score = 0

        # 1. Clear trend (required)
        trend = structure.get("trend")
        if trend in ["uptrend", "downtrend"]:
            signals.append(f"Trend: {trend}")
            score += 2
        else:
            return {
                "status": "success",
                "signal": "NO_TRADE",
                "reason": "No clear trend - market is ranging",
                "content": [{"text": f"NO TRADE | {symbol} | Reason: No clear trend structure"}]
            }

        # 2. EMA confirmation
        ema_trend = indicators.get("ema_trend")
        if (trend == "uptrend" and ema_trend == "bullish") or \
           (trend == "downtrend" and ema_trend == "bearish"):
            signals.append("EMA confirms trend")
            score += 1

        # 3. RSI not extreme
        rsi = indicators.get("rsi")
        if rsi:
            if trend == "uptrend" and rsi < 70:
                signals.append(f"RSI OK ({rsi:.0f})")
                score += 1
            elif trend == "downtrend" and rsi > 30:
                signals.append(f"RSI OK ({rsi:.0f})")
                score += 1

        # 4. Liquidity sweep (strong signal)
        if liquidity.get("detected"):
            sweep_type = liquidity.get("type")
            if (trend == "uptrend" and sweep_type == "bullish_sweep") or \
               (trend == "downtrend" and sweep_type == "bearish_sweep"):
                signals.append("Liquidity sweep detected")
                score += 3

        # 5. Entry zone available
        if entry_zones.get("has_zone"):
            zone = entry_zones["zones"][0]
            signals.append(f"Entry zone: {zone['type']} @ ${zone['entry']:.2f}")
            score += 2

            # Calculate SL distance
            sl_distance_pct = abs(zone["entry"] - zone["stop"]) / zone["entry"] * 100
        else:
            sl_distance_pct = indicators.get("atr_pct", 1) * 1.5  # 1.5x ATR as default SL

        # 6. Volume confirmation
        volume_ratio = indicators.get("volume_ratio", 1)
        if volume_ratio > 1.2:
            signals.append(f"Volume above avg ({volume_ratio:.1f}x)")
            score += 1

        # Decision threshold
        if score >= 5:
            direction = "LONG" if trend == "uptrend" else "SHORT"

            # Get entry and stop levels
            if entry_zones.get("has_zone"):
                zone = entry_zones["zones"][0]
                entry_price = zone["entry"]
                stop_loss = zone["stop"]
            else:
                # Use current price and ATR-based stop
                entry_price = current_price
                atr = indicators.get("atr", current_price * 0.01)
                if direction == "LONG":
                    stop_loss = entry_price - (atr * 1.5)
                else:
                    stop_loss = entry_price + (atr * 1.5)

            return {
                "status": "success",
                "signal": "ENTRY",
                "direction": direction,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "sl_distance_pct": abs(entry_price - stop_loss) / entry_price * 100,
                "score": score,
                "signals": signals,
                "content": [{
                    "text": f"ENTRY SIGNAL | {symbol} | {direction}\n"
                            f"Entry: ${entry_price:.2f} | SL: ${stop_loss:.2f}\n"
                            f"Score: {score}/10 | Signals: {', '.join(signals)}"
                }]
            }
        else:
            return {
                "status": "success",
                "signal": "NO_TRADE",
                "reason": f"Score too low ({score}/10). Need at least 5.",
                "score": score,
                "signals": signals,
                "content": [{
                    "text": f"NO TRADE | {symbol} | Score: {score}/10\n"
                            f"Signals: {', '.join(signals) if signals else 'None'}"
                }]
            }

    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"Signal check error: {str(e)}"}]
        }
