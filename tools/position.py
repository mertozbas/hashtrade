"""
Position Tool - Risk-based position sizing and management
Calculates position size based on risk percentage and stop-loss distance
"""
import os
import json
from typing import Dict, Any, Optional
from strands import tool


@tool
def calculate_position(
    balance: float,
    entry_price: float,
    stop_loss: float,
    risk_percent: float = 5.0,
    leverage: int = 20
) -> Dict[str, Any]:
    """
    Calculate position size based on risk management rules.

    Risk Formula:
    - Risk Amount = Balance × Risk%
    - SL Distance = |Entry - SL| / Entry
    - Position Margin = Risk Amount / (SL Distance × Leverage)
    - Real Position = Position Margin × Leverage

    Args:
        balance: Account balance in USDT
        entry_price: Entry price for the trade
        stop_loss: Stop-loss price
        risk_percent: Percentage of balance to risk (default: 5%)
        leverage: Leverage multiplier (default: 20x)

    Returns:
        Dict with position sizing details

    Example:
        calculate_position(balance=100, entry_price=95000, stop_loss=94050, risk_percent=5, leverage=20)
        # Entry: $95000, SL: $94050 (1% away)
        # Risk: $5 (5% of $100)
        # Position margin: $5 / (0.01 × 20) = $25
        # Real position: $25 × 20 = $500
    """
    try:
        if balance <= 0:
            return {
                "status": "error",
                "content": [{"text": "Balance must be positive"}]
            }

        if entry_price <= 0 or stop_loss <= 0:
            return {
                "status": "error",
                "content": [{"text": "Entry price and stop-loss must be positive"}]
            }

        # Determine direction
        if entry_price > stop_loss:
            direction = "LONG"
        elif entry_price < stop_loss:
            direction = "SHORT"
        else:
            return {
                "status": "error",
                "content": [{"text": "Entry price and stop-loss cannot be the same"}]
            }

        # Calculate SL distance percentage
        sl_distance = abs(entry_price - stop_loss)
        sl_distance_pct = sl_distance / entry_price

        # Calculate risk amount
        risk_amount = balance * (risk_percent / 100)

        # Calculate position margin (the amount you put up)
        # Risk = Position × SL% × Leverage
        # Position = Risk / (SL% × Leverage)
        position_margin = risk_amount / (sl_distance_pct * leverage)

        # Real position value
        real_position = position_margin * leverage

        # Calculate quantity (for the asset)
        quantity = real_position / entry_price

        # Calculate potential profit at 1% move
        profit_at_1pct = real_position * 0.01

        # Calculate TP levels
        # TP1: 1% move (equal to SL distance in many cases)
        # TP2: 2% move (2:1 R:R)
        if direction == "LONG":
            tp1_price = entry_price * 1.01
            tp2_price = entry_price * 1.02
        else:
            tp1_price = entry_price * 0.99
            tp2_price = entry_price * 0.98

        # Validate position size
        min_margin = 5  # Minimum $5 margin
        max_margin_pct = 50  # Max 50% of balance as margin

        warnings = []
        if position_margin < min_margin:
            warnings.append(f"Position margin (${position_margin:.2f}) is below minimum (${min_margin})")

        if position_margin > balance * (max_margin_pct / 100):
            warnings.append(f"Position margin exceeds {max_margin_pct}% of balance")

        if sl_distance_pct > 0.05:  # More than 5% SL
            warnings.append(f"Stop-loss distance ({sl_distance_pct*100:.1f}%) is very wide")

        if sl_distance_pct < 0.002:  # Less than 0.2% SL
            warnings.append(f"Stop-loss distance ({sl_distance_pct*100:.2f}%) is too tight")

        summary = f"""Position Calculation:
Direction: {direction}
Entry: ${entry_price:,.2f}
Stop-Loss: ${stop_loss:,.2f} ({sl_distance_pct*100:.2f}% away)

Risk: ${risk_amount:.2f} ({risk_percent}% of ${balance:.2f})
Leverage: {leverage}x
Margin Required: ${position_margin:.2f}
Position Size: ${real_position:,.2f}
Quantity: {quantity:.6f}

TP1 (1%): ${tp1_price:,.2f} -> Profit: ${profit_at_1pct:.2f}
TP2 (2%): ${tp2_price:,.2f} -> Profit: ${profit_at_1pct*2:.2f}"""

        if warnings:
            summary += f"\n\nWarnings:\n" + "\n".join(f"- {w}" for w in warnings)

        return {
            "status": "success",
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "sl_distance_pct": sl_distance_pct * 100,
            "risk_amount": risk_amount,
            "risk_percent": risk_percent,
            "leverage": leverage,
            "margin_required": position_margin,
            "position_size": real_position,
            "quantity": quantity,
            "tp1_price": tp1_price,
            "tp2_price": tp2_price,
            "profit_at_1pct": profit_at_1pct,
            "warnings": warnings,
            "content": [{"text": summary}]
        }

    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"Position calculation error: {str(e)}"}]
        }


@tool
def select_leverage(
    sl_distance_pct: float,
    volatility: str = "normal"
) -> Dict[str, Any]:
    """
    Select appropriate leverage based on stop-loss distance and market volatility.

    Args:
        sl_distance_pct: Stop-loss distance as percentage (e.g., 1.0 for 1%)
        volatility: Market volatility level ("low", "normal", "high")

    Returns:
        Dict with recommended leverage

    Logic:
    - Tighter SL = Higher leverage possible
    - Higher volatility = Lower leverage recommended
    - Range: 10x - 30x
    """
    try:
        # Base leverage calculation based on SL distance
        # Smaller SL = can use higher leverage
        if sl_distance_pct <= 0.5:
            base_leverage = 30
        elif sl_distance_pct <= 1.0:
            base_leverage = 25
        elif sl_distance_pct <= 1.5:
            base_leverage = 20
        elif sl_distance_pct <= 2.0:
            base_leverage = 15
        else:
            base_leverage = 10

        # Adjust for volatility
        volatility_multiplier = {
            "low": 1.2,
            "normal": 1.0,
            "high": 0.7
        }.get(volatility.lower(), 1.0)

        recommended_leverage = int(base_leverage * volatility_multiplier)

        # Clamp to range [10, 30]
        recommended_leverage = max(10, min(30, recommended_leverage))

        return {
            "status": "success",
            "sl_distance_pct": sl_distance_pct,
            "volatility": volatility,
            "recommended_leverage": recommended_leverage,
            "content": [{
                "text": f"Recommended Leverage: {recommended_leverage}x\n"
                        f"Based on: SL distance {sl_distance_pct:.2f}%, volatility: {volatility}"
            }]
        }

    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"Leverage selection error: {str(e)}"}]
        }


@tool
def manage_position(
    action: str,
    entry_price: float = None,
    current_price: float = None,
    stop_loss: float = None,
    quantity: float = None,
    direction: str = None
) -> Dict[str, Any]:
    """
    Manage open position - check TP/SL, partial close, move SL.

    Args:
        action: "check_pnl", "check_tp", "partial_close_calc"
        entry_price: Entry price of position
        current_price: Current market price
        stop_loss: Current stop-loss price
        quantity: Position quantity
        direction: "LONG" or "SHORT"

    Returns:
        Dict with position management recommendation
    """
    try:
        if action == "check_pnl":
            if not all([entry_price, current_price, direction]):
                return {
                    "status": "error",
                    "content": [{"text": "Need entry_price, current_price, and direction"}]
                }

            if direction.upper() == "LONG":
                pnl_pct = (current_price - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - current_price) / entry_price * 100

            status = "PROFIT" if pnl_pct > 0 else "LOSS"

            return {
                "status": "success",
                "pnl_pct": pnl_pct,
                "pnl_status": status,
                "content": [{
                    "text": f"Position P&L: {pnl_pct:+.2f}% ({status})\n"
                            f"Entry: ${entry_price:.2f} | Current: ${current_price:.2f}"
                }]
            }

        elif action == "check_tp":
            if not all([entry_price, current_price, direction]):
                return {
                    "status": "error",
                    "content": [{"text": "Need entry_price, current_price, and direction"}]
                }

            if direction.upper() == "LONG":
                pnl_pct = (current_price - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - current_price) / entry_price * 100

            recommendation = None
            new_sl = None

            if pnl_pct >= 1.0:
                # TP1 hit - recommend partial close and move SL to breakeven
                recommendation = "TP1_HIT"
                new_sl = entry_price
                action_text = f"TP1 reached ({pnl_pct:.2f}%)\n" \
                              f"Recommendation: Close 50% of position\n" \
                              f"Move SL to breakeven: ${entry_price:.2f}"
            elif pnl_pct >= 2.0:
                # TP2 zone
                recommendation = "TP2_ZONE"
                action_text = f"TP2 zone ({pnl_pct:.2f}%)\n" \
                              f"Consider closing remaining position or trail SL"
            elif pnl_pct <= -2.0:
                # Near SL
                recommendation = "NEAR_SL"
                action_text = f"Near stop-loss ({pnl_pct:.2f}%)\n" \
                              f"SL should trigger soon if set correctly"
            else:
                recommendation = "HOLD"
                action_text = f"Current P&L: {pnl_pct:.2f}%\n" \
                              f"No action needed - hold position"

            return {
                "status": "success",
                "pnl_pct": pnl_pct,
                "recommendation": recommendation,
                "new_sl": new_sl,
                "content": [{"text": action_text}]
            }

        elif action == "partial_close_calc":
            if not all([quantity, current_price]):
                return {
                    "status": "error",
                    "content": [{"text": "Need quantity and current_price"}]
                }

            close_qty = quantity * 0.5  # 50% of position
            close_value = close_qty * current_price

            return {
                "status": "success",
                "close_quantity": close_qty,
                "close_value": close_value,
                "remaining_quantity": quantity - close_qty,
                "content": [{
                    "text": f"Partial Close (50%):\n"
                            f"Close: {close_qty:.6f} (${close_value:.2f})\n"
                            f"Remaining: {quantity - close_qty:.6f}"
                }]
            }

        else:
            return {
                "status": "error",
                "content": [{"text": f"Unknown action: {action}. Valid: check_pnl, check_tp, partial_close_calc"}]
            }

    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"Position management error: {str(e)}"}]
        }
