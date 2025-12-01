"""
Balance Tool - Persistent balance tracking
"""
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from strands import tool

from .bybit_v5 import bybit_v5


@tool
def balance(
    action: str = "get",
    exchange: str = "bybit",
    api_key: str = None,
    api_secret: str = None,
) -> Dict[str, Any]:
    """
    Track account balance. Actions: get, history, clear
    """
    try:
        balance_file = Path(__file__).parent.parent / "data" / "balance.json"
        balance_file.parent.mkdir(parents=True, exist_ok=True)

        if balance_file.exists():
            with open(balance_file, 'r') as f:
                balance_data = json.load(f)
        else:
            balance_data = {"history": []}

        if action == "get":
            if not api_key:
                api_key = os.getenv("BYBIT_API_KEY")
            if not api_secret:
                api_secret = os.getenv("BYBIT_API_SECRET")

            if not api_key or not api_secret:
                return {
                    "status": "error",
                    "content": [{"text": "API keys not found"}]
                }

            result = bybit_v5(action="get_balance")

            if result.get("status") == "error":
                return result

            # Get equity directly from result if available
            equity = result.get("equity", 0) or result.get("balance_usdt", 0)

            # Fallback to parsing text
            if equity == 0:
                balance_text = result.get("content", [{}])[0].get("text", "")
                match = re.search(r'\$([\d,.]+)', balance_text)
                if match:
                    equity = float(match.group(1).replace(',', ''))

            # Save to history (keep last 50 only)
            record = {
                "timestamp": datetime.now().isoformat(),
                "equity": equity
            }
            balance_data["history"].append(record)
            balance_data["history"] = balance_data["history"][-50:]
            balance_data["latest"] = record

            with open(balance_file, 'w') as f:
                json.dump(balance_data, f)

            return {
                "status": "success",
                "equity": equity,
                "content": [{"text": f"Balance: ${equity:.2f} USDT"}]
            }

        elif action == "history":
            if not balance_data.get("history"):
                return {"status": "success", "content": [{"text": "No history"}]}

            lines = [f"Last {min(5, len(balance_data['history']))} records:"]
            for r in balance_data["history"][-5:]:
                lines.append(f"  ${r['equity']:.2f}")

            return {"status": "success", "content": [{"text": "\n".join(lines)}]}

        elif action == "clear":
            balance_data = {"history": []}
            with open(balance_file, 'w') as f:
                json.dump(balance_data, f)
            return {"status": "success", "content": [{"text": "Cleared"}]}

        else:
            return {"status": "error", "content": [{"text": f"Unknown action: {action}"}]}

    except Exception as e:
        return {"status": "error", "content": [{"text": f"Error: {str(e)}"}]}
