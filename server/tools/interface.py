#!/usr/bin/env python3
"""
Dynamic UI Interface Tool for HashTrade Dashboard

Enables the agent to:
1. Render dynamic UI components (HTML/React-style injection)
2. Update theme/template variables (colors, styles)
3. Create interactive widgets, cards, charts

The tool broadcasts messages via WebSocket to the frontend
AND adds entries to history so they appear in the History of Actions panel.
"""

import json
import time
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from strands import tool

# Import history for adding to timeline - handle both direct and package imports
try:
    from .history import HISTORY_FILE, _ensure
except ImportError:
    from server.tools.history import HISTORY_FILE, _ensure

# Default theme (neon green)
DEFAULT_THEME = {
    "neon": "#00ff88",
    "neon_dim": "#00ff8880",
    "neon_glow": "rgba(0, 255, 136, 0.5)",
    "neon_subtle": "rgba(0, 255, 136, 0.1)",
    "neon_border": "rgba(0, 255, 136, 0.2)",
    "bg": "#000000",
    "panel": "#000000",
    "panel_glass": "rgba(0, 0, 0, 0.8)",
    "text": "#00ff88",
    "text_dim": "#00ff8899",
    "muted": "rgba(0, 255, 136, 0.5)",
    "line": "rgba(0, 255, 136, 0.15)",
    "good": "#00ff88",
    "bad": "#ff3366",
    "warn": "#ffcc00",
}

# Preset themes
PRESET_THEMES = {
    "neon_green": DEFAULT_THEME,
    "cyberpunk": {
        "neon": "#ff00ff",
        "neon_dim": "#ff00ff80",
        "neon_glow": "rgba(255, 0, 255, 0.5)",
        "neon_subtle": "rgba(255, 0, 255, 0.1)",
        "neon_border": "rgba(255, 0, 255, 0.2)",
        "bg": "#0a0014",
        "panel": "#0a0014",
        "panel_glass": "rgba(10, 0, 20, 0.8)",
        "text": "#ff00ff",
        "text_dim": "#ff00ff99",
        "muted": "rgba(255, 0, 255, 0.5)",
        "line": "rgba(255, 0, 255, 0.15)",
        "good": "#00ffff",
        "bad": "#ff0066",
        "warn": "#ffcc00",
    },
    "ocean_blue": {
        "neon": "#00d4ff",
        "neon_dim": "#00d4ff80",
        "neon_glow": "rgba(0, 212, 255, 0.5)",
        "neon_subtle": "rgba(0, 212, 255, 0.1)",
        "neon_border": "rgba(0, 212, 255, 0.2)",
        "bg": "#000a14",
        "panel": "#000a14",
        "panel_glass": "rgba(0, 10, 20, 0.8)",
        "text": "#00d4ff",
        "text_dim": "#00d4ff99",
        "muted": "rgba(0, 212, 255, 0.5)",
        "line": "rgba(0, 212, 255, 0.15)",
        "good": "#00ff88",
        "bad": "#ff3366",
        "warn": "#ffa500",
    },
    "sunset_orange": {
        "neon": "#ff6b35",
        "neon_dim": "#ff6b3580",
        "neon_glow": "rgba(255, 107, 53, 0.5)",
        "neon_subtle": "rgba(255, 107, 53, 0.1)",
        "neon_border": "rgba(255, 107, 53, 0.2)",
        "bg": "#140800",
        "panel": "#140800",
        "panel_glass": "rgba(20, 8, 0, 0.8)",
        "text": "#ff6b35",
        "text_dim": "#ff6b3599",
        "muted": "rgba(255, 107, 53, 0.5)",
        "line": "rgba(255, 107, 53, 0.15)",
        "good": "#00ff88",
        "bad": "#ff3366",
        "warn": "#ffcc00",
    },
    "gold_luxury": {
        "neon": "#ffd700",
        "neon_dim": "#ffd70080",
        "neon_glow": "rgba(255, 215, 0, 0.5)",
        "neon_subtle": "rgba(255, 215, 0, 0.1)",
        "neon_border": "rgba(255, 215, 0, 0.2)",
        "bg": "#0a0a00",
        "panel": "#0a0a00",
        "panel_glass": "rgba(10, 10, 0, 0.8)",
        "text": "#ffd700",
        "text_dim": "#ffd70099",
        "muted": "rgba(255, 215, 0, 0.5)",
        "line": "rgba(255, 215, 0, 0.15)",
        "good": "#00ff88",
        "bad": "#ff3366",
        "warn": "#ffa500",
    },
    "matrix_green": {
        "neon": "#00ff00",
        "neon_dim": "#00ff0080",
        "neon_glow": "rgba(0, 255, 0, 0.5)",
        "neon_subtle": "rgba(0, 255, 0, 0.1)",
        "neon_border": "rgba(0, 255, 0, 0.2)",
        "bg": "#000500",
        "panel": "#000500",
        "panel_glass": "rgba(0, 5, 0, 0.8)",
        "text": "#00ff00",
        "text_dim": "#00ff0099",
        "muted": "rgba(0, 255, 0, 0.5)",
        "line": "rgba(0, 255, 0, 0.15)",
        "good": "#00ff00",
        "bad": "#ff0000",
        "warn": "#ffff00",
    },
    "dark_minimal": {
        "neon": "#ffffff",
        "neon_dim": "#ffffff80",
        "neon_glow": "rgba(255, 255, 255, 0.3)",
        "neon_subtle": "rgba(255, 255, 255, 0.05)",
        "neon_border": "rgba(255, 255, 255, 0.1)",
        "bg": "#0a0a0a",
        "panel": "#0a0a0a",
        "panel_glass": "rgba(10, 10, 10, 0.9)",
        "text": "#ffffff",
        "text_dim": "#ffffff99",
        "muted": "rgba(255, 255, 255, 0.4)",
        "line": "rgba(255, 255, 255, 0.1)",
        "good": "#00ff88",
        "bad": "#ff3366",
        "warn": "#ffcc00",
    },
}

# Store current theme in memory (shared across calls)
_current_theme = DEFAULT_THEME.copy()


def _add_to_history(
    event_type: str, data: Dict[str, Any], widget_id: str = ""
) -> Dict[str, Any]:
    """Add an entry to history so it appears in the History of Actions panel."""
    _ensure()
    rec = {
        "ts": time.time(),
        "type": event_type,
        "turn_id": widget_id,
        "data": data,
    }
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


@tool
def interface(
    action: str,
    # Theme parameters
    preset: Optional[str] = None,
    theme: Optional[Dict[str, str]] = None,
    color_name: Optional[str] = None,
    color_value: Optional[str] = None,
    # UI render parameters
    html: Optional[str] = None,
    component_type: Optional[str] = None,
    title: Optional[str] = None,
    content: Optional[str] = None,
    data: Optional[Union[Dict, List]] = None,
    style: Optional[Dict[str, str]] = None,
    target: Optional[
        str
    ] = None,  # Where to render: "timeline", "chat", "modal", "toast"
    # Widget parameters
    widget_id: Optional[str] = None,
    interactive: bool = True,
) -> Dict[str, Any]:
    """
    Dynamic UI interface for rendering components and customizing themes.

    Args:
        action: Operation to perform:
            Theme Actions:
            - "get_theme" - Get current theme variables
            - "set_theme" - Set entire theme from preset or custom dict
            - "update_color" - Update a single color variable
            - "list_presets" - List available theme presets
            - "reset_theme" - Reset to default neon green theme

            UI Render Actions:
            - "render_html" - Inject raw HTML into dashboard
            - "render_card" - Render a styled card component
            - "render_table" - Render a data table
            - "render_chart" - Render a simple chart widget
            - "render_alert" - Show an alert/notification
            - "render_progress" - Show a progress indicator
            - "render_widget" - Render a custom widget
            - "clear_ui" - Clear dynamic UI from target area

        preset: Theme preset name (for set_theme):
            - "neon_green" (default)
            - "cyberpunk" (magenta/cyan)
            - "ocean_blue" (blue/teal)
            - "sunset_orange" (orange/amber)
            - "gold_luxury" (gold/black)
            - "matrix_green" (pure green)
            - "dark_minimal" (white/gray)

        theme: Custom theme dict (overrides preset)
        color_name: Variable name for update_color (e.g., "neon", "bg", "good")
        color_value: Color value for update_color (e.g., "#ff00ff", "rgba(255,0,0,0.5)")

        html: Raw HTML string for render_html
        component_type: Type hint for component rendering
        title: Title for cards/widgets
        content: Text content for components
        data: Data object/array for tables/charts
        style: Additional inline styles as dict
        target: Where to render ("timeline", "chat", "modal", "toast")
        widget_id: Unique ID for the widget (auto-generated if not provided)
        interactive: Whether widget is interactive (default: True)

    Returns:
        Dict with status and the message payload to broadcast via WebSocket

    Examples:
        # Change to cyberpunk theme
        interface(action="set_theme", preset="cyberpunk")

        # Custom single color
        interface(action="update_color", color_name="neon", color_value="#ff00ff")

        # Render a card in timeline
        interface(
            action="render_card",
            title="Trade Alert",
            content="BTC breakout detected!",
            target="timeline"
        )

        # Render custom HTML
        interface(
            action="render_html",
            html='<div class="custom-widget">Hello World</div>',
            target="timeline"
        )

        # Render a data table
        interface(
            action="render_table",
            title="Top Movers",
            data=[
                {"symbol": "BTC", "change": "+5.2%"},
                {"symbol": "ETH", "change": "+3.1%"}
            ]
        )

        # Show alert toast
        interface(
            action="render_alert",
            content="Order filled!",
            style={"type": "success"}
        )
    """
    global _current_theme
    ts = time.time()
    widget_id = widget_id or f"ui-{int(ts * 1000)}"

    # ========== THEME ACTIONS ==========

    if action == "get_theme":
        return {
            "status": "success",
            "content": [{"text": json.dumps(_current_theme, indent=2)}],
            "theme": _current_theme,
            "ws_message": {
                "type": "theme_current",
                "data": _current_theme,
                "timestamp": ts,
            },
        }

    if action == "list_presets":
        preset_info = {
            name: {"neon": t["neon"], "bg": t["bg"]}
            for name, t in PRESET_THEMES.items()
        }
        return {
            "status": "success",
            "content": [{"text": json.dumps(preset_info, indent=2)}],
            "presets": list(PRESET_THEMES.keys()),
            "preset_preview": preset_info,
        }

    if action == "set_theme":
        if preset and preset in PRESET_THEMES:
            _current_theme = PRESET_THEMES[preset].copy()
        if theme and isinstance(theme, dict):
            _current_theme.update(theme)

        # Add to history for timeline display
        history_data = {
            "title": f"Theme: {preset or 'Custom'}",
            "message": f"Changed theme to {preset or 'custom theme'}",
            "preset": preset,
            "neon": _current_theme.get("neon"),
        }
        _add_to_history("theme", history_data, widget_id)

        ws_msg = {
            "type": "theme_update",
            "data": _current_theme,
            "preset": preset,
            "timestamp": ts,
        }
        return {
            "status": "success",
            "content": [
                {"text": f"Theme updated to: {preset or 'custom'}"},
                {"text": f"__WS__:{json.dumps(ws_msg)}"},
            ],
            "theme": _current_theme,
            "ws_message": ws_msg,
        }

    if action == "update_color":
        if not color_name or not color_value:
            return {
                "status": "error",
                "content": [{"text": "color_name and color_value required"}],
            }

        # Map common names to CSS var names
        var_map = {
            "neon": "neon",
            "primary": "neon",
            "accent": "neon",
            "background": "bg",
            "bg": "bg",
            "text": "text",
            "good": "good",
            "success": "good",
            "bad": "bad",
            "error": "bad",
            "danger": "bad",
            "warn": "warn",
            "warning": "warn",
        }
        actual_name = var_map.get(color_name.lower(), color_name)
        _current_theme[actual_name] = color_value

        # Also update derived colors if changing neon
        if actual_name == "neon":
            # Parse color to create variants
            _current_theme["neon_dim"] = color_value + "80"
            _current_theme["text"] = color_value
            _current_theme["text_dim"] = color_value + "99"

        # Add to history for timeline display
        history_data = {
            "title": f"Color: {actual_name}",
            "message": f"Changed {actual_name} to {color_value}",
            "color_name": actual_name,
            "color_value": color_value,
        }
        _add_to_history("theme", history_data, widget_id)

        ws_msg = {
            "type": "theme_update",
            "data": _current_theme,
            "changed": {actual_name: color_value},
            "timestamp": ts,
        }
        return {
            "status": "success",
            "content": [
                {"text": f"Updated {actual_name} to {color_value}"},
                {"text": f"__WS__:{json.dumps(ws_msg)}"},
            ],
            "theme": _current_theme,
            "ws_message": ws_msg,
        }

    if action == "reset_theme":
        _current_theme = DEFAULT_THEME.copy()
        ws_msg = {
            "type": "theme_update",
            "data": _current_theme,
            "preset": "neon_green",
            "timestamp": ts,
        }
        return {
            "status": "success",
            "content": [
                {"text": "Theme reset to default neon green"},
                {"text": f"__WS__:{json.dumps(ws_msg)}"},
            ],
            "theme": _current_theme,
            "ws_message": ws_msg,
        }

    # ========== UI RENDER ACTIONS ==========

    target = target or "timeline"

    if action == "render_html":
        if not html:
            return {"status": "error", "content": [{"text": "html parameter required"}]}

        # Add to history for timeline display
        history_data = {
            "render_type": "html",
            "html": html,
            "widget_id": widget_id,
            "title": title or "Custom HTML",
        }
        _add_to_history("ui_html", history_data, widget_id)

        ws_msg = {
            "type": "ui_render",
            "render_type": "html",
            "target": target,
            "widget_id": widget_id,
            "html": html,
            "style": style or {},
            "interactive": interactive,
            "timestamp": ts,
        }
        return {
            "status": "success",
            "content": [
                {"text": f"Rendered HTML to {target}"},
                {"text": f"__WS__:{json.dumps(ws_msg)}"},
            ],
            "ws_message": ws_msg,
        }

    if action == "render_card":
        card_html = f"""
        <div class="dynamic-card" id="{widget_id}" style="
            padding: 16px;
            border-radius: 12px;
            border: 1px solid var(--neon-border);
            background: var(--neon-subtle);
            backdrop-filter: blur(10px);
        ">
            {f'<div style="font-weight: 600; margin-bottom: 8px; color: var(--neon);">{title}</div>' if title else ''}
            <div style="color: var(--text); line-height: 1.5;">{content or ''}</div>
            {f'<div style="margin-top: 12px; font-size: 11px; color: var(--muted);">{json.dumps(data)}</div>' if data else ''}
        </div>
        """

        # Add to history for timeline display
        history_data = {
            "render_type": "card",
            "html": card_html,
            "widget_id": widget_id,
            "title": title or "Card",
            "message": content or "",
        }
        _add_to_history("ui_card", history_data, widget_id)

        ws_msg = {
            "type": "ui_render",
            "render_type": "card",
            "target": target,
            "widget_id": widget_id,
            "html": card_html,
            "title": title,
            "content": content,
            "data": data,
            "style": style or {},
            "timestamp": ts,
        }
        return {
            "status": "success",
            "content": [
                {"text": f"Rendered card: {title or widget_id}"},
                {"text": f"__WS__:{json.dumps(ws_msg)}"},
            ],
            "ws_message": ws_msg,
        }

    if action == "render_table":
        if not data or not isinstance(data, list):
            return {
                "status": "error",
                "content": [{"text": "data (list of dicts) required for table"}],
            }

        # Build table HTML
        headers = list(data[0].keys()) if data else []
        header_row = "".join(
            f'<th style="padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--line); color: var(--neon);">{h}</th>'
            for h in headers
        )
        body_rows = ""
        for row in data:
            cells = "".join(
                f'<td style="padding: 8px 12px; border-bottom: 1px solid var(--line);">{row.get(h, "")}</td>'
                for h in headers
            )
            body_rows += f"<tr>{cells}</tr>"

        table_html = f"""
        <div class="dynamic-table" id="{widget_id}" style="overflow: auto;">
            {f'<div style="font-weight: 600; margin-bottom: 12px; color: var(--neon);">{title}</div>' if title else ''}
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead><tr>{header_row}</tr></thead>
                <tbody>{body_rows}</tbody>
            </table>
        </div>
        """

        # Add to history for timeline display
        history_data = {
            "render_type": "table",
            "html": table_html,
            "widget_id": widget_id,
            "title": title or "Table",
            "message": f"Table with {len(data)} rows",
            "rows": len(data),
        }
        _add_to_history("ui_table", history_data, widget_id)

        ws_msg = {
            "type": "ui_render",
            "render_type": "table",
            "target": target,
            "widget_id": widget_id,
            "html": table_html,
            "title": title,
            "data": data,
            "timestamp": ts,
        }
        return {
            "status": "success",
            "content": [
                {"text": f"Rendered table with {len(data)} rows"},
                {"text": f"__WS__:{json.dumps(ws_msg)}"},
            ],
            "ws_message": ws_msg,
        }

    if action == "render_chart":
        # Simple bar/sparkline chart via CSS
        if not data:
            return {"status": "error", "content": [{"text": "data required for chart"}]}

        # Normalize data to list of values
        values = []
        labels = []
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                for d in data:
                    labels.append(str(d.get("label", d.get("name", ""))))
                    values.append(float(d.get("value", d.get("v", 0))))
            else:
                values = [float(v) for v in data]
                labels = [str(i) for i in range(len(values))]
        elif isinstance(data, dict):
            labels = list(data.keys())
            values = [float(v) for v in data.values()]

        max_val = max(values) if values else 1
        bars = ""
        for i, (label, val) in enumerate(zip(labels, values)):
            pct = (val / max_val) * 100 if max_val else 0
            bars += f"""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                <div style="width: 60px; font-size: 11px; color: var(--muted); text-overflow: ellipsis; overflow: hidden;">{label}</div>
                <div style="flex: 1; height: 20px; background: var(--neon-subtle); border-radius: 4px; overflow: hidden;">
                    <div style="width: {pct}%; height: 100%; background: linear-gradient(90deg, var(--neon), var(--neon-dim)); transition: width 0.3s;"></div>
                </div>
                <div style="width: 50px; font-size: 11px; text-align: right; color: var(--text);">{val}</div>
            </div>
            """

        chart_html = f"""
        <div class="dynamic-chart" id="{widget_id}">
            {f'<div style="font-weight: 600; margin-bottom: 12px; color: var(--neon);">{title}</div>' if title else ''}
            {bars}
        </div>
        """

        # Add to history for timeline display
        history_data = {
            "render_type": "chart",
            "html": chart_html,
            "widget_id": widget_id,
            "title": title or "Chart",
            "message": f"Chart with {len(values)} data points",
        }
        _add_to_history("ui_chart", history_data, widget_id)

        ws_msg = {
            "type": "ui_render",
            "render_type": "chart",
            "target": target,
            "widget_id": widget_id,
            "html": chart_html,
            "title": title,
            "data": data,
            "timestamp": ts,
        }
        return {
            "status": "success",
            "content": [
                {"text": f"Rendered chart: {title or widget_id}"},
                {"text": f"__WS__:{json.dumps(ws_msg)}"},
            ],
            "ws_message": ws_msg,
        }

    if action == "render_alert":
        alert_type = (style or {}).get("type", "info")
        color_map = {
            "success": "var(--good)",
            "error": "var(--bad)",
            "warning": "var(--warn)",
            "info": "var(--neon)",
        }
        border_color = color_map.get(alert_type, "var(--neon)")
        icon_map = {
            "success": "✓",
            "error": "✗",
            "warning": "⚠",
            "info": "ℹ",
        }
        icon = icon_map.get(alert_type, "•")

        # Add to history for timeline display
        history_data = {
            "render_type": "alert",
            "alert_type": alert_type,
            "widget_id": widget_id,
            "title": title or f"Alert ({alert_type})",
            "message": content or "",
            "icon": icon,
        }
        _add_to_history("ui_alert", history_data, widget_id)

        ws_msg = {
            "type": "ui_alert",
            "alert_type": alert_type,
            "widget_id": widget_id,
            "title": title,
            "content": content,
            "icon": icon,
            "border_color": border_color,
            "target": "toast",  # Alerts always go to toast
            "timestamp": ts,
        }
        return {
            "status": "success",
            "content": [
                {"text": f"Alert: {content}"},
                {"text": f"__WS__:{json.dumps(ws_msg)}"},
            ],
            "ws_message": ws_msg,
        }

    if action == "render_progress":
        value = (data or {}).get("value", 0) if isinstance(data, dict) else 50
        max_value = (data or {}).get("max", 100) if isinstance(data, dict) else 100
        pct = (value / max_value) * 100 if max_value else 0

        progress_html = f"""
        <div class="dynamic-progress" id="{widget_id}">
            {f'<div style="font-weight: 500; margin-bottom: 8px; color: var(--neon);">{title}</div>' if title else ''}
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="flex: 1; height: 8px; background: var(--neon-subtle); border-radius: 4px; overflow: hidden;">
                    <div style="width: {pct}%; height: 100%; background: var(--neon); border-radius: 4px; transition: width 0.3s;"></div>
                </div>
                <div style="font-size: 12px; color: var(--text);">{value}/{max_value}</div>
            </div>
            {f'<div style="margin-top: 6px; font-size: 11px; color: var(--muted);">{content}</div>' if content else ''}
        </div>
        """

        # Add to history for timeline display
        history_data = {
            "render_type": "progress",
            "html": progress_html,
            "widget_id": widget_id,
            "title": title or "Progress",
            "message": f"{value}/{max_value} ({pct:.0f}%)",
            "value": value,
            "max_value": max_value,
        }
        _add_to_history("ui_progress", history_data, widget_id)

        ws_msg = {
            "type": "ui_render",
            "render_type": "progress",
            "target": target,
            "widget_id": widget_id,
            "html": progress_html,
            "value": value,
            "max_value": max_value,
            "timestamp": ts,
        }
        return {
            "status": "success",
            "content": [
                {"text": f"Progress: {value}/{max_value}"},
                {"text": f"__WS__:{json.dumps(ws_msg)}"},
            ],
            "ws_message": ws_msg,
        }

    if action == "render_widget":
        # Generic widget - combines multiple elements
        widget_html = f"""
        <div class="dynamic-widget" id="{widget_id}" style="
            padding: 16px;
            border-radius: 12px;
            border: 1px solid var(--neon-border);
            background: var(--panel-glass);
            backdrop-filter: blur(10px);
        ">
            {f'<div style="font-weight: 600; margin-bottom: 12px; color: var(--neon); display: flex; align-items: center; gap: 8px;"><span style="font-size: 18px;">{(style or {}).get("icon", "◆")}</span>{title}</div>' if title else ''}
            {f'<div style="color: var(--text); margin-bottom: 12px; line-height: 1.5;">{content}</div>' if content else ''}
            {html or ''}
            {f'<pre style="margin-top: 12px; padding: 10px; background: rgba(0,0,0,0.3); border-radius: 8px; font-size: 11px; overflow: auto;">{json.dumps(data, indent=2)}</pre>' if data else ''}
        </div>
        """

        # Add to history for timeline display
        history_data = {
            "render_type": "widget",
            "html": widget_html,
            "widget_id": widget_id,
            "title": title or "Widget",
            "message": content or "",
            "icon": (style or {}).get("icon", "◆"),
        }
        _add_to_history("ui_widget", history_data, widget_id)

        ws_msg = {
            "type": "ui_render",
            "render_type": "widget",
            "target": target,
            "widget_id": widget_id,
            "html": widget_html,
            "title": title,
            "content": content,
            "data": data,
            "style": style or {},
            "interactive": interactive,
            "timestamp": ts,
        }
        return {
            "status": "success",
            "content": [
                {"text": f"Rendered widget: {title or widget_id}"},
                {"text": f"__WS__:{json.dumps(ws_msg)}"},
            ],
            "ws_message": ws_msg,
        }

    if action == "clear_ui":
        ws_msg = {
            "type": "ui_clear",
            "target": target,
            "widget_id": (
                widget_id if widget_id != f"ui-{int(ts * 1000)}" else None
            ),  # Only clear specific if provided
            "timestamp": ts,
        }
        return {
            "status": "success",
            "content": [
                {"text": f"Cleared dynamic UI from {target}"},
                {"text": f"__WS__:{json.dumps(ws_msg)}"},
            ],
            "ws_message": ws_msg,
        }

    return {
        "status": "error",
        "content": [
            {
                "text": f"Unknown action: {action}. Valid: get_theme, set_theme, update_color, "
                "list_presets, reset_theme, render_html, render_card, render_table, "
                "render_chart, render_alert, render_progress, render_widget, clear_ui"
            }
        ],
    }


if __name__ == "__main__":
    # Test
    print("Testing interface tool...")

    # List presets
    result = interface(action="list_presets")
    print(f"Presets: {result['presets']}")

    # Set theme
    result = interface(action="set_theme", preset="cyberpunk")
    print(f"Theme set: {result['ws_message']['preset']}")

    # Render card
    result = interface(
        action="render_card",
        title="Test Alert",
        content="This is a test card!",
        target="timeline",
    )
    print(f"Card rendered: {result['ws_message']['widget_id']}")

    # Render table
    result = interface(
        action="render_table",
        title="Top Coins",
        data=[
            {"symbol": "BTC", "price": "67000", "change": "+2.5%"},
            {"symbol": "ETH", "price": "3500", "change": "+1.2%"},
        ],
    )
    print(f"Table rendered: {result['ws_message']['widget_id']}")
