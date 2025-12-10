#!/usr/bin/env python3
"""
Hashtrade Agent - 4H Range Breakout Strategy
Simple rule-based scalping using first 4-hour candle of the day
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
RISK_PERCENT = 5.0
MAX_POSITIONS = 1
RR_RATIO = 2.0  # Fixed 2:1 risk-reward


class RangeAgent:

    def __init__(self):
        print("Initializing Hashtrade Agent - 4H Range Strategy")

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
                    balance, bybit_v5, order,
                    calculate_position, select_leverage
                )
                from tools.range_4h import get_4h_range, check_range_breakout, scan_4h_range_setups

                # Register tools
                self.agent.agent.tool_registry.register_tool(balance)
                self.agent.agent.tool_registry.register_tool(bybit_v5)
                self.agent.agent.tool_registry.register_tool(order)
                self.agent.agent.tool_registry.register_tool(calculate_position)
                self.agent.agent.tool_registry.register_tool(select_leverage)
                self.agent.agent.tool_registry.register_tool(get_4h_range)
                self.agent.agent.tool_registry.register_tool(check_range_breakout)
                self.agent.agent.tool_registry.register_tool(scan_4h_range_setups)

                print("Loaded 8 tools successfully")
            except Exception as e:
                print(f"Failed to load tools: {e}")
                import traceback
                traceback.print_exc()

        self.trade_count = 0
        self.session_start = datetime.now()

        print(f"Strategy: 4H Range Breakout (5m scalping)")
        print(f"Coins: {', '.join(TRADING_COINS)}")
        print(f"Risk: {RISK_PERCENT}% | R:R: {RR_RATIO}:1")

    def get_journal_path(self):
        """Get journal file path for today"""
        today = datetime.now().strftime("%Y-%m-%d")
        return Path(__file__).parent / "journal" / f"4h_range_{today}.md"

    def get_last_journal_entry(self):
        """Read last journal entry"""
        try:
            journal_path = self.get_journal_path()
            if journal_path.exists():
                with open(journal_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return content[-1500:] if len(content) > 1500 else content
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
            open_positions = positions_result.get('positions', [])

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
        """Run one trading cycle"""
        self.trade_count += 1
        cycle_start = datetime.now()

        print(f"\n{'='*60}")
        print(f"4H Range Cycle #{self.trade_count} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        state = self.get_current_state()
        journal = self.get_last_journal_entry()

        context = f"""
CURRENT STATE:
{state['balance_text']}

POSITIONS:
{state['positions_text']}

RECENT JOURNAL:
{journal}
"""
        print(context)

        workflow = f"""
{context}

You are a 4H Range Breakout trading agent.
Execute this cycle following the rules EXACTLY.

=== CONFIGURATION ===
- Coins: {', '.join(TRADING_COINS)}
- Timeframe: 5m (entries) with 4H range
- Risk: {RISK_PERCENT}% per trade
- Take Profit: 2:1 R:R (fixed)
- Max positions: {MAX_POSITIONS}
- Current positions: {state['position_count']}

=== 4H RANGE STRATEGY RULES ===

STEP 1: CHECK POSITION
If position is open ({state['position_count']}/{MAX_POSITIONS}):
- Check P&L using bybit_v5(action="get_positions")
- If TP hit (2:1 R:R): Position should auto-close
- If SL hit: Position should auto-close
- Log status and STOP - no new scans

STEP 2: SCAN FOR SETUPS (if no position)
Use scan_4h_range_setups() to scan all coins at once.
This will:
- Get 4H range (first 4H candle of the day, NY time)
- Check for breakout + retest on 5m
- Return valid setups if found

STEP 3: ENTRY CRITERIA
Valid setup requires:
1. First 4H candle of the day is CLOSED
2. 5m candle CLOSED outside range (breakout)
3. 5m candle CLOSED back inside range (retest)
4. NOT just wicks - must be candle CLOSES

LONG Setup: Price broke BELOW range low, then closed back INSIDE
SHORT Setup: Price broke ABOVE range high, then closed back INSIDE

STEP 4: EXECUTE TRADE (if setup found)
- Use calculate_position() for sizing:
  * balance from current state
  * entry_price from setup
  * stop_loss from setup (breakout extreme)
  * risk_percent = {RISK_PERCENT}
- Place order with bybit_v5(action="place_order")
- Set SL/TP with bybit_v5(action="set_trading_stop")
  * SL = breakout extreme
  * TP = 2x SL distance (2:1 R:R)

STEP 5: NO SETUP
If no valid setup found:
- Log "NO SETUP - waiting"
- This is CORRECT when conditions aren't met

=== IMPORTANT RULES ===
- Only CLOSED candles count (no wicks)
- One trade per setup
- Multiple setups can occur same day if valid
- Same day = same 4H range period
- Fixed 2:1 R:R for all trades

=== JOURNAL FORMAT ===
Write entry (save to journal/4h_range_YYYY-MM-DD.md):
"## HH:MM:SS
Cycle #{self.trade_count}: [ACTION] | [COIN] | [DETAILS] | Balance: $X | Pos: X/1"

Examples:
- "Cycle #3: NO SETUP | All coins inside range | Balance: $23 | Pos: 0/1"
- "Cycle #4: LONG BTCUSDT | Range retest @ $95000 | SL: $94500 | TP: $96000 | Pos: 1/1"
- "Cycle #5: TP HIT | BTCUSDT +2R | Balance: $28 | Pos: 0/1"
"""

        try:
            result = self.agent(workflow)

            cycle_end = datetime.now()
            duration = (cycle_end - cycle_start).total_seconds()

            print(f"\nCycle completed in {duration:.1f}s")

            if result:
                result_str = str(result)
                print(result_str[:800] + "..." if len(result_str) > 800 else result_str)

        except Exception as e:
            print(f"Cycle error: {e}")
            import traceback
            traceback.print_exc()

    def show_stats(self):
        """Display session stats"""
        runtime = datetime.now() - self.session_start
        print(f"\nSession Stats:")
        print(f"  Runtime: {runtime}")
        print(f"  Cycles: {self.trade_count}")
        if self.trade_count > 0:
            print(f"  Avg cycle: {runtime.total_seconds() / self.trade_count:.1f}s")

    def start(self, interval_minutes: int = None):
        """Start trading loop"""
        if interval_minutes is None:
            interval_minutes = int(os.getenv('CYCLE_INTERVAL', 5))

        print(f"\nStarting 4H Range agent...")
        print(f"Interval: {interval_minutes} min")
        print(f"Press Ctrl+C to stop\n")

        try:
            while True:
                self.run_cycle()
                self.show_stats()
                print(f"\nWaiting {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            print("\n\nStopping...")
            self.show_stats()
            print("Agent stopped.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="4H Range Breakout Agent")
    parser.add_argument("--interval", type=int, default=None)
    parser.add_argument("--once", action="store_true")

    args = parser.parse_args()

    agent = RangeAgent()

    if args.once:
        agent.run_cycle()
        agent.show_stats()
    else:
        agent.start(interval_minutes=args.interval)
