"""
Balance Tool - Persistent balance tracking
Tracks account balance and writes to balance.json
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
    Track and persist account balance.

    Args:
        action: "get" (fetch current), "history" (show all records), "clear" (reset)
        exchange: Exchange name (default: bybit)
        api_key: API key (reads from env if not provided)
        api_secret: API secret (reads from env if not provided)

    Returns:
        Dict with status and balance data
    """
    try:
        # Balance file path
        balance_file = Path(__file__).parent.parent / "data" / "balance.json"
        balance_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing data
        if balance_file.exists():
            with open(balance_file, 'r') as f:
                balance_data = json.load(f)
        else:
            balance_data = {"history": []}

        if action == "get":
            # Get API credentials
            if not api_key:
                api_key = os.getenv("BYBIT_API_KEY")
            if not api_secret:
                api_secret = os.getenv("BYBIT_API_SECRET")

            if not api_key or not api_secret:
                return {
                    "status": "error",
                    "content": [{"text": "API credentials not found. Set BYBIT_API_KEY and BYBIT_API_SECRET"}]
                }

            # Call bybit_v5 to get balance
            result = bybit_v5(action="get_balance")

            if result.get("status") == "error":
                return result

            # Parse balance - bybit_v5 returns structured data
            balance_text = result["content"][0]["text"]

            # Extract equity - try multiple patterns
            equity = 0.0
            usdt_balance = 0.0

            # Pattern 1: "Balance: X USDT ($Y)"
            usdt_match = re.search(r'Balance:\s*([\d,.]+)\s*USDT', balance_text)
            if usdt_match:
                usdt_balance = float(usdt_match.group(1).replace(',', ''))
                equity = usdt_balance

            # Pattern 2: "Toplam Equity: $X" or "Total Equity: $X"
            if equity == 0:
                equity_match = re.search(r'(?:Toplam|Total)\s+(?:Deger|Equity):\s*\$?([\d,.]+)', balance_text, re.IGNORECASE)
                if equity_match:
                    equity = float(equity_match.group(1).replace(',', ''))

            # Pattern 3: "Wallet Balance: $X"
            if equity == 0:
                wallet_match = re.search(r'Wallet\s+Balance:\s*\$?([\d,.]+)', balance_text, re.IGNORECASE)
                if wallet_match:
                    equity = float(wallet_match.group(1).replace(',', ''))

            # Pattern 4: First number with $ sign
            if equity == 0:
                dollar_match = re.search(r'\$([\d,.]+)', balance_text)
                if dollar_match:
                    equity = float(dollar_match.group(1).replace(',', ''))

            # Create balance record
            record = {
                "timestamp": datetime.now().isoformat(),
                "exchange": exchange,
                "equity": equity,
                "usdt_balance": usdt_balance,
                "raw_data": balance_text[:500]
            }

            # Add to history
            balance_data["history"].append(record)
            balance_data["latest"] = record

            # Save to file
            with open(balance_file, 'w') as f:
                json.dump(balance_data, f, indent=2)

            return {
                "status": "success",
                "content": [{
                    "text": f"Balance updated and saved to {balance_file}\n\n"
                            f"Current Equity: ${equity:,.2f} USD\n"
                            f"USDT Balance: {usdt_balance:,.2f} USDT\n"
                            f"Total Records: {len(balance_data['history'])}\n"
                            f"Timestamp: {record['timestamp']}\n\n"
                            f"Raw data preview:\n{balance_text[:200]}..."
                }]
            }

        elif action == "history":
            if not balance_data.get("history"):
                return {
                    "status": "success",
                    "content": [{"text": "No balance history found. Run balance(action='get') first."}]
                }

            # Format history
            text = f"Balance History ({len(balance_data['history'])} records):\n\n"
            for i, record in enumerate(balance_data["history"][-10:], 1):
                text += f"{i}. {record['timestamp']}: ${record['equity']:,.2f}\n"

            return {
                "status": "success",
                "content": [{"text": text}]
            }

        elif action == "clear":
            balance_data = {"history": []}
            with open(balance_file, 'w') as f:
                json.dump(balance_data, f, indent=2)

            return {
                "status": "success",
                "content": [{"text": "Balance history cleared"}]
            }

        else:
            return {
                "status": "error",
                "content": [{"text": f"Unknown action: {action}. Valid: get, history, clear"}]
            }

    except Exception as e:
        import traceback
        return {
            "status": "error",
            "content": [{"text": f"Balance tool error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"}]
        }
