"""
Liquidity Tool - Multi-Timeframe Liquidity Analysis
Identifies liquidity pools, detects sweeps, and finds opposing liquidity targets
"""
import json
import threading
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from strands import tool

# Store recent liquidations (in-memory cache)
_liquidation_cache = defaultdict(list)
_cache_lock = threading.Lock()


def get_klines_data(symbol: str, interval: str, limit: int = 100) -> List:
    """Fetch klines from Bybit"""
    try:
        from tools.bybit_v5 import bybit_v5
    except ImportError:
        from bybit_v5 import bybit_v5

    result = bybit_v5(
        action="get_kline",
        symbol=symbol,
        kwargs=json.dumps({"interval": interval, "limit": limit})
    )

    if result.get("status") == "error":
        return []

    klines = result.get("klines", [])
    # Bybit returns newest first, reverse for chronological order
    return list(reversed(klines)) if klines else []


def find_swing_points(highs: List[float], lows: List[float], lookback: int = 3) -> Dict:
    """Find swing highs and swing lows as liquidity pools"""
    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(highs) - lookback):
        # Swing High
        is_swing_high = all(highs[i] >= highs[i-j] for j in range(1, lookback+1)) and \
                        all(highs[i] >= highs[i+j] for j in range(1, lookback+1))
        if is_swing_high:
            swing_highs.append({"index": i, "price": highs[i]})

        # Swing Low
        is_swing_low = all(lows[i] <= lows[i-j] for j in range(1, lookback+1)) and \
                       all(lows[i] <= lows[i+j] for j in range(1, lookback+1))
        if is_swing_low:
            swing_lows.append({"index": i, "price": lows[i]})

    return {"swing_highs": swing_highs, "swing_lows": swing_lows}


def detect_market_bias(swing_highs: List[Dict], swing_lows: List[Dict]) -> str:
    """Determine market bias from structure"""
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "neutral"

    # Check last swing points
    hh = swing_highs[-1]["price"] > swing_highs[-2]["price"]  # Higher High
    hl = swing_lows[-1]["price"] > swing_lows[-2]["price"]    # Higher Low
    lh = swing_highs[-1]["price"] < swing_highs[-2]["price"]  # Lower High
    ll = swing_lows[-1]["price"] < swing_lows[-2]["price"]    # Lower Low

    if hh and hl:
        return "bullish"
    elif lh and ll:
        return "bearish"
    else:
        return "neutral"


@tool
def find_liquidity_pools(
    symbol: str,
    timeframe: str = "60",
    lookback: int = 50
) -> Dict[str, Any]:
    """
    Find liquidity pools (swing highs/lows) on specified timeframe.

    Liquidity pools are areas where stop losses cluster:
    - Buy-side liquidity (BSL): Above swing highs (short SLs)
    - Sell-side liquidity (SSL): Below swing lows (long SLs)

    Args:
        symbol: Trading pair (e.g., BTCUSDT)
        timeframe: Candle interval (1, 5, 15, 60, 240, D)
        lookback: Number of candles to analyze

    Returns:
        Dict with liquidity pools and current price context
    """
    try:
        # Normalize symbol
        clean_symbol = symbol.upper().replace("/", "").replace(":USDT", "")
        if not clean_symbol.endswith("USDT"):
            clean_symbol += "USDT"

        # Fetch klines
        klines = get_klines_data(clean_symbol, timeframe, lookback + 10)

        if len(klines) < lookback:
            return {
                "status": "error",
                "content": [{"text": f"Insufficient data for {clean_symbol} on {timeframe}m"}]
            }

        # Parse OHLCV
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        closes = [float(k[4]) for k in klines]
        current_price = closes[-1]

        # Find swing points
        swings = find_swing_points(highs, lows, lookback=3)

        # Separate into BSL and SSL relative to current price
        buy_side_liquidity = []  # Above price (targets for longs)
        sell_side_liquidity = []  # Below price (targets for shorts)

        for sh in swings["swing_highs"]:
            pool = {
                "price": sh["price"],
                "type": "BSL",
                "distance_pct": round((sh["price"] - current_price) / current_price * 100, 2)
            }
            if sh["price"] > current_price:
                buy_side_liquidity.append(pool)

        for sl in swings["swing_lows"]:
            pool = {
                "price": sl["price"],
                "type": "SSL",
                "distance_pct": round((current_price - sl["price"]) / current_price * 100, 2)
            }
            if sl["price"] < current_price:
                sell_side_liquidity.append(pool)

        # Sort by distance (closest first)
        buy_side_liquidity.sort(key=lambda x: x["distance_pct"])
        sell_side_liquidity.sort(key=lambda x: x["distance_pct"])

        # Get market bias
        bias = detect_market_bias(swings["swing_highs"], swings["swing_lows"])

        # Nearest pools
        nearest_bsl = buy_side_liquidity[0] if buy_side_liquidity else None
        nearest_ssl = sell_side_liquidity[0] if sell_side_liquidity else None

        summary = f"{clean_symbol} {timeframe}m | Price: ${current_price:.2f} | Bias: {bias.upper()}\n"
        if nearest_bsl:
            summary += f"Nearest BSL: ${nearest_bsl['price']:.2f} (+{nearest_bsl['distance_pct']:.2f}%)\n"
        if nearest_ssl:
            summary += f"Nearest SSL: ${nearest_ssl['price']:.2f} (-{nearest_ssl['distance_pct']:.2f}%)"

        return {
            "status": "success",
            "symbol": clean_symbol,
            "timeframe": timeframe,
            "price": current_price,
            "bias": bias,
            "bsl": buy_side_liquidity[:5],  # Top 5 closest
            "ssl": sell_side_liquidity[:5],
            "nearest_bsl": nearest_bsl,
            "nearest_ssl": nearest_ssl,
            "content": [{"text": summary}]
        }

    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"Liquidity pool error: {str(e)}"}]
        }


@tool
def detect_liquidity_sweep(
    symbol: str,
    timeframe: str = "15",
    lookback_candles: int = 5
) -> Dict[str, Any]:
    """
    Detect if a liquidity sweep occurred in recent candles.

    A sweep happens when:
    1. Price takes out a swing high/low (sweeps liquidity)
    2. Then closes back inside the range (rejection)
    3. Followed by a reversal candle (confirmation)

    Multi-candle detection: Checks the last N candles for sweep patterns,
    not just the most recent candle.

    Args:
        symbol: Trading pair
        timeframe: Timeframe to check (default: 15m)
        lookback_candles: Number of recent candles to check for sweeps (default: 5)

    Returns:
        Dict with sweep detection results
    """
    try:
        clean_symbol = symbol.upper().replace("/", "").replace(":USDT", "")
        if not clean_symbol.endswith("USDT"):
            clean_symbol += "USDT"

        # Fetch recent klines
        klines = get_klines_data(clean_symbol, timeframe, 60)

        if len(klines) < 20:
            return {
                "status": "error",
                "content": [{"text": f"Insufficient data for sweep detection"}]
            }

        # Parse OHLCV
        opens = [float(k[1]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        closes = [float(k[4]) for k in klines]

        current_price = closes[-1]

        # Find swing points (excluding last few candles)
        swings = find_swing_points(highs[:-3], lows[:-3], lookback=3)

        sweep_detected = False
        sweep_type = None
        sweep_level = None
        sweep_wick = None
        sweep_candle_idx = None
        confirmation = False

        # Multi-candle sweep detection: check last N candles
        for candle_offset in range(lookback_candles):
            if sweep_detected:
                break

            idx = -(candle_offset + 1)  # -1, -2, -3, etc.
            if abs(idx) >= len(closes):
                break

            candle_high = highs[idx]
            candle_low = lows[idx]
            candle_open = opens[idx]
            candle_close = closes[idx]

            # Check for bearish sweep (price swept above swing high then rejected)
            for sh in reversed(swings["swing_highs"][-5:]):
                # Did this candle wick above swing high but close below?
                if candle_high > sh["price"] and candle_close < sh["price"]:
                    sweep_detected = True
                    sweep_type = "bearish"
                    sweep_level = sh["price"]
                    sweep_wick = candle_high
                    sweep_candle_idx = idx

                    # Confirmation check: for older sweeps, check if subsequent candles confirmed
                    if candle_offset == 0:
                        # Most recent candle - check if it's bearish
                        confirmation = candle_close < candle_open
                    else:
                        # Older sweep - check if the following candle was bearish
                        next_idx = idx + 1
                        if next_idx < 0:
                            confirmation = closes[next_idx] < opens[next_idx]
                        else:
                            confirmation = closes[-1] < current_price  # Current below sweep
                    break

            # Check for bullish sweep (price swept below swing low then rejected)
            if not sweep_detected:
                for sl in reversed(swings["swing_lows"][-5:]):
                    # Did this candle wick below swing low but close above?
                    if candle_low < sl["price"] and candle_close > sl["price"]:
                        sweep_detected = True
                        sweep_type = "bullish"
                        sweep_level = sl["price"]
                        sweep_wick = candle_low
                        sweep_candle_idx = idx

                        # Confirmation check
                        if candle_offset == 0:
                            confirmation = candle_close > candle_open
                        else:
                            next_idx = idx + 1
                            if next_idx < 0:
                                confirmation = closes[next_idx] > opens[next_idx]
                            else:
                                confirmation = closes[-1] > current_price
                        break

        if sweep_detected:
            # Calculate SL distance (from current price to sweep wick)
            if sweep_type == "bullish":
                sl_distance_pct = round((current_price - sweep_wick) / current_price * 100, 2)
            else:
                sl_distance_pct = round((sweep_wick - current_price) / current_price * 100, 2)

            candles_ago = abs(sweep_candle_idx)
            summary = f"SWEEP DETECTED | {clean_symbol} | {sweep_type.upper()}\n"
            summary += f"Level: ${sweep_level:.2f} | Wick: ${sweep_wick:.2f}\n"
            summary += f"Candles ago: {candles_ago} | SL distance: {sl_distance_pct:.2f}%\n"
            summary += f"Confirmation: {'YES' if confirmation else 'WAITING'}"

            return {
                "status": "success",
                "sweep_detected": True,
                "sweep_type": sweep_type,
                "sweep_level": sweep_level,
                "sweep_wick": sweep_wick,
                "sweep_candles_ago": candles_ago,
                "sl_distance_pct": sl_distance_pct,
                "confirmation": confirmation,
                "current_price": current_price,
                "content": [{"text": summary}]
            }
        else:
            return {
                "status": "success",
                "sweep_detected": False,
                "current_price": current_price,
                "content": [{"text": f"NO SWEEP | {clean_symbol} {timeframe}m | Price: ${current_price:.2f}"}]
            }

    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"Sweep detection error: {str(e)}"}]
        }


@tool
def get_opposing_liquidity(
    symbol: str,
    direction: str,
    entry_price: float
) -> Dict[str, Any]:
    """
    Find the opposing liquidity pool for TP target.

    For LONG trades: Target is nearest BSL (buy-side liquidity above)
    For SHORT trades: Target is nearest SSL (sell-side liquidity below)

    Args:
        symbol: Trading pair
        direction: Trade direction ("LONG" or "SHORT")
        entry_price: Entry price of the trade

    Returns:
        Dict with TP target and R:R calculation
    """
    try:
        clean_symbol = symbol.upper().replace("/", "").replace(":USDT", "")
        if not clean_symbol.endswith("USDT"):
            clean_symbol += "USDT"

        # Get liquidity pools from 1H timeframe for major levels
        pools = find_liquidity_pools(symbol=clean_symbol, timeframe="60", lookback=100)

        if pools.get("status") == "error":
            return pools

        direction = direction.upper()

        if direction == "LONG":
            # Target BSL above entry
            targets = [p for p in pools.get("bsl", []) if p["price"] > entry_price]
            if not targets:
                return {
                    "status": "error",
                    "content": [{"text": f"No BSL targets found above entry ${entry_price:.2f}"}]
                }
            target = targets[0]  # Nearest BSL
            tp_price = target["price"]
            tp_distance_pct = (tp_price - entry_price) / entry_price * 100

        elif direction == "SHORT":
            # Target SSL below entry
            targets = [p for p in pools.get("ssl", []) if p["price"] < entry_price]
            if not targets:
                return {
                    "status": "error",
                    "content": [{"text": f"No SSL targets found below entry ${entry_price:.2f}"}]
                }
            target = targets[0]  # Nearest SSL
            tp_price = target["price"]
            tp_distance_pct = (entry_price - tp_price) / entry_price * 100
        else:
            return {
                "status": "error",
                "content": [{"text": f"Invalid direction: {direction}. Use LONG or SHORT."}]
            }

        summary = f"TP TARGET | {direction} {clean_symbol}\n"
        summary += f"Entry: ${entry_price:.2f}\n"
        summary += f"Target: ${tp_price:.2f} ({tp_distance_pct:.2f}%)"

        return {
            "status": "success",
            "direction": direction,
            "entry_price": entry_price,
            "tp_price": tp_price,
            "tp_distance_pct": round(tp_distance_pct, 2),
            "target_type": target["type"],
            "content": [{"text": summary}]
        }

    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"Opposing liquidity error: {str(e)}"}]
        }


@tool
def mtf_liquidity_scan(
    symbol: str
) -> Dict[str, Any]:
    """
    Multi-Timeframe Liquidity Scan for entry signals.

    Analyzes:
    - 1H: Major liquidity pools + market bias
    - 15m: Sweep detection + confirmation
    - 5m: Entry zone refinement

    Args:
        symbol: Trading pair

    Returns:
        Dict with MTF analysis and trade setup if valid
    """
    try:
        clean_symbol = symbol.upper().replace("/", "").replace(":USDT", "")
        if not clean_symbol.endswith("USDT"):
            clean_symbol += "USDT"

        results = {
            "symbol": clean_symbol,
            "timestamp": datetime.now().isoformat(),
            "htf": {},
            "mtf": {},
            "ltf": {},
            "signal": None,
            "setup": None
        }

        # === 1H ANALYSIS (Higher Timeframe - Bias + Major Liquidity) ===
        htf_pools = find_liquidity_pools(symbol=clean_symbol, timeframe="60", lookback=100)

        if htf_pools.get("status") == "error":
            return htf_pools

        results["htf"] = {
            "bias": htf_pools.get("bias"),
            "price": htf_pools.get("price"),
            "nearest_bsl": htf_pools.get("nearest_bsl"),
            "nearest_ssl": htf_pools.get("nearest_ssl")
        }

        # === 15m ANALYSIS (Medium Timeframe - Sweep Detection) ===
        mtf_sweep = detect_liquidity_sweep(symbol=clean_symbol, timeframe="15")

        results["mtf"] = {
            "sweep_detected": mtf_sweep.get("sweep_detected", False),
            "sweep_type": mtf_sweep.get("sweep_type"),
            "sweep_level": mtf_sweep.get("sweep_level"),
            "sweep_wick": mtf_sweep.get("sweep_wick"),
            "confirmation": mtf_sweep.get("confirmation", False)
        }

        # === 5m ANALYSIS (Lower Timeframe - Entry Refinement) ===
        ltf_sweep = detect_liquidity_sweep(symbol=clean_symbol, timeframe="5")

        results["ltf"] = {
            "sweep_detected": ltf_sweep.get("sweep_detected", False),
            "sweep_type": ltf_sweep.get("sweep_type"),
            "current_price": ltf_sweep.get("current_price")
        }

        # === SIGNAL GENERATION ===
        htf_bias = results["htf"]["bias"]
        mtf_sweep_detected = results["mtf"]["sweep_detected"]
        mtf_sweep_type = results["mtf"]["sweep_type"]
        mtf_confirmation = results["mtf"]["confirmation"]
        current_price = results["ltf"]["current_price"] or results["htf"]["price"]

        # Valid setup conditions
        valid_setup = False
        direction = None

        # Bullish setup: Bullish/neutral bias + bullish sweep + confirmation
        if htf_bias in ["bullish", "neutral"] and mtf_sweep_type == "bullish" and mtf_confirmation:
            valid_setup = True
            direction = "LONG"

        # Bearish setup: Bearish/neutral bias + bearish sweep + confirmation
        elif htf_bias in ["bearish", "neutral"] and mtf_sweep_type == "bearish" and mtf_confirmation:
            valid_setup = True
            direction = "SHORT"

        if valid_setup:
            # Get opposing liquidity for TP
            opposing = get_opposing_liquidity(
                symbol=clean_symbol,
                direction=direction,
                entry_price=current_price
            )

            sweep_wick = results["mtf"]["sweep_wick"]

            # Calculate SL (beyond sweep wick with buffer)
            if direction == "LONG":
                sl_price = sweep_wick * 0.998  # 0.2% buffer below wick
                sl_distance_pct = (current_price - sl_price) / current_price * 100
            else:
                sl_price = sweep_wick * 1.002  # 0.2% buffer above wick
                sl_distance_pct = (sl_price - current_price) / current_price * 100

            tp_price = opposing.get("tp_price", current_price * (1.02 if direction == "LONG" else 0.98))
            tp_distance_pct = opposing.get("tp_distance_pct", 2.0)

            # Calculate R:R
            rr_ratio = tp_distance_pct / sl_distance_pct if sl_distance_pct > 0 else 0

            results["signal"] = "ENTRY"
            results["setup"] = {
                "direction": direction,
                "entry": current_price,
                "sl": round(sl_price, 2),
                "sl_pct": round(sl_distance_pct, 2),
                "tp": round(tp_price, 2),
                "tp_pct": round(tp_distance_pct, 2),
                "rr_ratio": round(rr_ratio, 2),
                "sweep_level": results["mtf"]["sweep_level"]
            }

            summary = f"ENTRY SIGNAL | {clean_symbol} {direction}\n"
            summary += f"1H Bias: {htf_bias} | 15m Sweep: {mtf_sweep_type} + CONFIRMED\n"
            summary += f"Entry: ${current_price:.2f}\n"
            summary += f"SL: ${sl_price:.2f} ({sl_distance_pct:.2f}%)\n"
            summary += f"TP: ${tp_price:.2f} ({tp_distance_pct:.2f}%)\n"
            summary += f"R:R = 1:{rr_ratio:.1f}"
        else:
            results["signal"] = "NO_TRADE"

            reasons = []
            if not mtf_sweep_detected:
                reasons.append("No sweep on 15m")
            elif not mtf_confirmation:
                reasons.append("Sweep not confirmed")
            elif htf_bias == "bullish" and mtf_sweep_type == "bearish":
                reasons.append("Sweep against HTF bias")
            elif htf_bias == "bearish" and mtf_sweep_type == "bullish":
                reasons.append("Sweep against HTF bias")

            summary = f"NO TRADE | {clean_symbol}\n"
            summary += f"1H Bias: {htf_bias} | 15m Sweep: {mtf_sweep_detected}\n"
            summary += f"Reason: {', '.join(reasons) if reasons else 'No valid setup'}"

        results["content"] = [{"text": summary}]
        results["status"] = "success"

        return results

    except Exception as e:
        import traceback
        return {
            "status": "error",
            "content": [{"text": f"MTF scan error: {str(e)}\n{traceback.format_exc()}"}]
        }


@tool
def get_liquidation_levels(
    symbol: str
) -> Dict[str, Any]:
    """
    Get recent liquidation activity from Bybit.
    Uses REST API to get open interest changes as proxy for liquidation levels.

    Args:
        symbol: Trading pair

    Returns:
        Dict with liquidation level estimates
    """
    try:
        clean_symbol = symbol.upper().replace("/", "").replace(":USDT", "")
        if not clean_symbol.endswith("USDT"):
            clean_symbol += "USDT"

        try:
            from tools.bybit_v5 import bybit_v5
        except ImportError:
            from bybit_v5 import bybit_v5

        # Get open interest data
        # This gives us an idea of where positions are concentrated
        result = bybit_v5(
            action="get_open_interest",
            symbol=clean_symbol,
            kwargs=json.dumps({"intervalTime": "5min", "limit": 50})
        )

        if result.get("status") == "error":
            # Fallback: Use swing points as liquidation level estimates
            pools = find_liquidity_pools(symbol=clean_symbol, timeframe="15", lookback=50)
            return {
                "status": "success",
                "source": "swing_points",
                "symbol": clean_symbol,
                "estimated_levels": {
                    "long_liquidations": pools.get("ssl", [])[:3],
                    "short_liquidations": pools.get("bsl", [])[:3]
                },
                "content": [{"text": f"Liquidation estimates from swing points for {clean_symbol}"}]
            }

        # Process open interest data
        oi_data = result.get("open_interest", [])

        return {
            "status": "success",
            "source": "bybit_oi",
            "symbol": clean_symbol,
            "open_interest": oi_data[-5:] if oi_data else [],
            "content": [{"text": f"Open interest data for {clean_symbol}"}]
        }

    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"Liquidation levels error: {str(e)}"}]
        }
