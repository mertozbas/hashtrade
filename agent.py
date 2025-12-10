#!/usr/bin/env python3
"""
Hashtrade Agent - Smart Money Scalping Strategy
Uses DevDuck with Smart Money Concepts (AMD, ICT, SMC)
"""
import sys
import time
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import devduck
from dotenv import load_dotenv

load_dotenv()

# Trading configuration
TRADING_COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "CRVUSDT"]
RISK_PERCENT = 5.0  # Risk 5% of balance per trade
LEVERAGE_RANGE = (5, 30)  # Min and max leverage (lower min for small balances)
MAX_POSITIONS = 1  # Only 1 position at a time


class HashtradeAgent:

    def __init__(self):
        print("Initializing Hashtrade Agent - Smart Money Strategy")

        model_provider = os.getenv('MODEL_PROVIDER', 'auto-detect')
        model_id = os.getenv('MODEL_ID', 'default')
        print(f"Model Provider: {model_provider}")
        print(f"Model ID: {model_id}")

        self.agent = devduck.devduck

        # Load tools
        tools_dir = Path(__file__).parent / "tools"
        if tools_dir.exists():
            print(f"Loading tools from: {tools_dir}")
            try:
                from tools import (
                    balance, bybit_v5, ccxt_generic, order,
                    analyze_market, check_entry_signal,
                    calculate_position, select_leverage, manage_position
                )

                # Register all tools
                self.agent.agent.tool_registry.register_tool(balance)
                self.agent.agent.tool_registry.register_tool(bybit_v5)
                self.agent.agent.tool_registry.register_tool(ccxt_generic)
                self.agent.agent.tool_registry.register_tool(order)
                self.agent.agent.tool_registry.register_tool(analyze_market)
                self.agent.agent.tool_registry.register_tool(check_entry_signal)
                self.agent.agent.tool_registry.register_tool(calculate_position)
                self.agent.agent.tool_registry.register_tool(select_leverage)
                self.agent.agent.tool_registry.register_tool(manage_position)

                print(f"Loaded 9 tools successfully")
            except Exception as e:
                print(f"Failed to load tools: {e}")
                import traceback
                traceback.print_exc()

        self.trade_count = 0
        self.session_start = datetime.now()

        print(f"DevDuck agent initialized: {self.agent.model}")
        print(f"Strategy: Smart Money Scalping (15m timeframe)")
        print(f"Coins: {', '.join(TRADING_COINS)}")
        print(f"Risk: {RISK_PERCENT}% per trade | Leverage: {LEVERAGE_RANGE[0]}-{LEVERAGE_RANGE[1]}x")
        print(f"Max positions: {MAX_POSITIONS}")

    def get_last_journal_entry(self):
        """Read last journal entry for context"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            journal_path = Path(__file__).parent / "journal" / f"{today}.md"

            if journal_path.exists():
                with open(journal_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return content[-2000:] if len(content) > 2000 else content
            return "No journal entries today."
        except Exception as e:
            return f"Journal error: {e}"

    def get_current_state(self):
        """Get current balance and positions"""
        try:
            balance_result = self.agent.agent.tool.balance(action='get')
            balance_text = balance_result.get('content', [{}])[0].get('text', 'Balance unavailable')

            positions_result = self.agent.agent.tool.bybit_v5(action='get_positions')
            positions_text = positions_result.get('content', [{}])[0].get('text', 'Positions unavailable')
            open_positions = positions_result.get('positions', [])  # Changed from 'open_positions'

            return {
                "balance_text": balance_text,
                "positions_text": positions_text,
                "open_positions": open_positions,
                "position_count": len(open_positions)
            }
        except Exception as e:
            return {
                "balance_text": f"Error: {e}",
                "positions_text": "Error",
                "open_positions": [],
                "position_count": 0
            }

    def run_cycle(self):
        """Run one trading cycle with Smart Money strategy"""
        self.trade_count += 1
        cycle_start = datetime.now()

        print(f"\n{'='*60}")
        print(f"Cycle #{self.trade_count} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        # Get current state
        state = self.get_current_state()
        journal = self.get_last_journal_entry()

        # Build context
        context = f"""
CURRENT STATE:
{state['balance_text']}

POSITIONS:
{state['positions_text']}

RECENT JOURNAL:
{journal}
"""
        print(context)

        # Strategy workflow
        workflow = f"""
{context}

You are an AUTONOMOUS trading bot. Execute trades WITHOUT asking for confirmation.
DO NOT ask "shall I proceed?" - just DO IT.

=== CONFIG ===
Coins: {', '.join(TRADING_COINS)} | TF: 15m | Risk: {RISK_PERCENT}%
Leverage: {LEVERAGE_RANGE[0]}-{LEVERAGE_RANGE[1]}x | Max Pos: {MAX_POSITIONS}
Open positions: {state['position_count']}

=== AUTONOMOUS EXECUTION ===

IF POSITION OPEN ({state['position_count']}/{MAX_POSITIONS}):
  → manage_position(action="check_tp") to check P&L
  → IF P&L >= +1%: Close 50%, move SL to breakeven
  → STOP - don't scan new entries

IF NO POSITION:
  1. Scan all coins with check_entry_signal(symbol=COIN)
  2. IF signal="ENTRY" found (score >= 5):
     → DO NOT ASK FOR CONFIRMATION
     → EXECUTE IMMEDIATELY:
       a) bybit_v5(action="set_leverage", symbol=X, kwargs='{{"buyLeverage":"10","sellLeverage":"10"}}')
       b) bybit_v5(action="place_order", symbol=X, kwargs='{{"side":"Buy","orderType":"Market","qty":"0.01","positionIdx":0}}')
       c) bybit_v5(action="set_trading_stop", symbol=X, kwargs='{{"stopLoss":"X","positionIdx":0}}')
       d) journal(entry="Cycle #X: ENTRY [LONG/SHORT] | [COIN] | ...")
  3. IF no signal: journal "NO TRADE" and finish

=== POSITION SIZING ===
Use calculate_position() with current balance from state above.
- Risk: {RISK_PERCENT}% of balance
- Use select_leverage() to get optimal leverage based on SL distance
- Margin must be < 30% of balance

=== CRITICAL ===
- You are AUTONOMOUS - no human confirmation needed
- Score 5+ = EXECUTE THE TRADE NOW
- After placing order, write to journal and finish cycle
"""

        try:
            result = self.agent(workflow)

            cycle_end = datetime.now()
            cycle_duration = (cycle_end - cycle_start).total_seconds()

            print(f"\nCycle completed in {cycle_duration:.1f}s")

            if result:
                result_str = str(result)
                print(result_str[:800] + "..." if len(result_str) > 800 else result_str)

        except Exception as e:
            print(f"Cycle error: {e}")
            import traceback
            traceback.print_exc()

    def show_stats(self):
        """Display session statistics"""
        runtime = datetime.now() - self.session_start

        print(f"\nSession Stats:")
        print(f"  Runtime: {runtime}")
        print(f"  Cycles: {self.trade_count}")
        if self.trade_count > 0:
            print(f"  Avg cycle time: {runtime.total_seconds() / self.trade_count:.1f}s")

    def start(self, interval_minutes: int = None):
        """Start autonomous trading loop"""
        if interval_minutes is None:
            interval_minutes = int(os.getenv('CYCLE_INTERVAL', 5))

        print(f"\nStarting Smart Money trading agent...")
        print(f"Cycle interval: {interval_minutes} minutes")
        print(f"Press Ctrl+C to stop\n")

        try:
            while True:
                self.run_cycle()
                self.show_stats()

                print(f"\nWaiting {interval_minutes} minutes until next cycle...")
                time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            print("\n\nStopping agent...")
            self.show_stats()
            print("Agent stopped gracefully")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hashtrade Smart Money Trading Agent")
    parser.add_argument("--interval", type=int, default=None,
                        help="Cycle interval in minutes (default: from .env or 5)")
    parser.add_argument("--once", action="store_true",
                        help="Run one cycle and exit")

    args = parser.parse_args()

    agent = HashtradeAgent()

    if args.once:
        agent.run_cycle()
        agent.show_stats()
    else:
        agent.start(interval_minutes=args.interval)
