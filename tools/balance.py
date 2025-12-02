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


def _get_bybit_balance():
    """Get balance directly from Bybit API to avoid import issues"""
    import time
    import hmac
    import hashlib
    import requests

    api_key = os.getenv("BYBIT_API_KEY", "")
    api_secret = os.getenv("BYBIT_API_SECRET", "")
    testnet = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
    base_url = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"

    if not api_key or not api_secret:
        return None, "API keys not found"

    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"
    params = "accountType=UNIFIED"

    param_str = f"{timestamp}{api_key}{recv_window}{params}"
    signature = hmac.new(
        api_secret.encode('utf-8'),
        param_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "X-BAPI-SIGN": signature
    }

    try:
        resp = requests.get(f"{base_url}/v5/account/wallet-balance?{params}",
                           headers=headers, timeout=10)
        data = resp.json()

        if data.get("retCode") == 0:
            coins = data["result"]["list"][0]["coin"]
            usdt = next((c for c in coins if c["coin"] == "USDT"), None)
            if usdt:
                return float(usdt.get("equity", usdt["walletBalance"])), None
        return None, data.get("retMsg", "Unknown error")
    except Exception as e:
        return None, str(e)


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
            equity, error = _get_bybit_balance()

            if error:
                return {"status": "error", "content": [{"text": error}]}

            if equity is None:
                return {"status": "error", "content": [{"text": "Failed to get balance"}]}

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
