#!/usr/bin/env python3
"""Minimal history store for dashboard.

- Writes JSONL to ./data/history.jsonl
- Use as a tool so the agent/server can persist actions.

Actions:
  - add: append an event
  - tail: read last N
  - clear: truncate file

Event schema (suggested):
  {"ts": 173..., "type": "tool_start|tool_end|balance|order|ui|note|error", "turn_id":"...", "data": {...}}
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from strands import tool

DATA_DIR = Path(os.getenv("DASH_DATA_DIR", "./data")).resolve()
HISTORY_FILE = DATA_DIR / "history.jsonl"


def _ensure():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.exists():
        HISTORY_FILE.touch()


def _read_last_lines(path: Path, n: int) -> list[str]:
    # Small/fast: read whole file if small, else tail by blocks
    try:
        size = path.stat().st_size
        if size <= 1024 * 1024:  # 1MB
            return path.read_text(encoding="utf-8", errors="ignore").splitlines()[-n:]
    except Exception:
        pass

    # Tail by reading blocks from end
    lines: list[str] = []
    block = 8192
    with path.open("rb") as f:
        f.seek(0, 2)
        end = f.tell()
        pos = end
        buf = b""
        while pos > 0 and len(lines) <= n:
            read_size = block if pos >= block else pos
            pos -= read_size
            f.seek(pos)
            buf = f.read(read_size) + buf
            lines = buf.splitlines()
        # decode last n lines
        out = [ln.decode("utf-8", errors="ignore") for ln in lines[-n:]]
        return out


@tool
def history(
    action: str = "add",
    event_type: str = "note",
    data: Optional[Dict[str, Any]] = None,
    turn_id: str = "",
    limit: int = 200,
) -> Dict[str, Any]:
    """Persist and fetch dashboard history.

    action:
      - add: append one JSON line
      - tail: return last `limit` entries
      - clear: truncate
    """
    _ensure()

    if action == "add":
        rec = {
            "ts": time.time(),
            "type": event_type,
            "turn_id": turn_id,
            "data": data or {},
        }
        with HISTORY_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return {
            "status": "success",
            "content": [{"text": json.dumps(rec, ensure_ascii=False)}],
            "record": rec,
        }

    if action == "tail":
        limit = int(limit or 200)
        raw_lines = _read_last_lines(
            HISTORY_FILE, max(1, limit * 2)
        )  # Read extra to account for filtering
        items = []

        # ONLY show explicit history entries (note, trade, signal, etc.)
        # SKIP all automatic events (tool_start, tool_end, ui, balance, raw)
        SKIP_TYPES = {"tool_start", "tool_end", "ui", "balance", "raw"}

        for ln in raw_lines:
            ln = (ln or "").strip()
            if not ln:
                continue
            try:
                rec = json.loads(ln)
                rec_type = rec.get("type", "")

                # Skip automatic/meta events - only show explicit history entries
                if rec_type in SKIP_TYPES:
                    continue

                items.append(rec)
            except Exception:
                # skip invalid entries
                continue

        # Return only the requested limit after filtering
        items = items[-limit:] if len(items) > limit else items
        return {
            "status": "success",
            "content": [{"text": json.dumps(items, ensure_ascii=False)}],
            "items": items,
        }

    if action == "clear":
        HISTORY_FILE.write_text("", encoding="utf-8")
        return {"status": "success", "content": [{"text": "cleared"}]}

    return {"status": "error", "content": [{"text": f"Unknown action: {action}"}]}
