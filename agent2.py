#!/usr/bin/env python3
"""
Hashtrade Agent v2 - Smart Money Scalping Strategy
Enhanced version with:
- 10% risk per trade (for larger positions)
- MAX_POSITIONS = 3
- Partial close capability (min qty 0.02 to allow 50% close)
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

# Trading configuration - ENHANCED
TRADING_COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "CRVUSDT"]
RISK_PERCENT = 10.0  # Risk 10% of balance per trade (doubled for larger positions)
LEVERAGE_RANGE = (10, 30)  # Dynamic: select_leverage() calculates based on SL distance
MAX_POSITIONS = 3  # Allow up to 3 concurrent positions

# Minimum quantities for partial close capability
MIN_QTY = {
    "BTCUSDT": 0.002,   # 2x min (0.001) to allow 50% partial close
    "ETHUSDT": 0.02,    # 2x min (0.01) to allow 50% partial close
    "SOLUSDT": 0.2,     # 2x min (0.1) to allow 50% partial close
    "XRPUSDT": 20,      # 2x min (10) to allow 50% partial close
    "CRVUSDT": 20,      # 2x min (10) to allow 50% partial close
}


class HashtradeAgentV2:

    def __init__(self):
        print("Initializing Hashtrade Agent v2 - Enhanced Smart Money Strategy")

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
        print(f"Strategy: Smart Money Scalping v2 (15m timeframe)")
        print(f"Coins: {', '.join(TRADING_COINS)}")
        print(f"Risk: {RISK_PERCENT}% per trade | Leverage: {LEVERAGE_RANGE[0]}-{LEVERAGE_RANGE[1]}x")
        print(f"Max positions: {MAX_POSITIONS}")
        print(f"Partial close: ENABLED (2x min qty)")

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

POSITIONS ({state['position_count']}/{MAX_POSITIONS}):
{state['positions_text']}

RECENT JOURNAL:
{journal}
"""
        print(context)

        # Get symbols not already in positions
        positioned_symbols = [p.get('symbol', '') for p in state['open_positions']]
        available_coins = [c for c in TRADING_COINS if c not in positioned_symbols]
        can_open_new = state['position_count'] < MAX_POSITIONS

        # Strategy workflow - ENHANCED for partial close
        workflow = f"""
{context}

You are an AUTONOMOUS trading bot v2. Execute trades WITHOUT asking for confirmation.
DO NOT ask "shall I proceed?" - just DO IT.

=== CONFIG v2 ===
Coins: {', '.join(TRADING_COINS)} | TF: 15m | Risk: {RISK_PERCENT}%
Leverage: {LEVERAGE_RANGE[0]}-{LEVERAGE_RANGE[1]}x | Max Pos: {MAX_POSITIONS}
Open positions: {state['position_count']}/{MAX_POSITIONS}
Can open new: {can_open_new}
Available coins: {', '.join(available_coins) if available_coins else 'None (all positioned)'}

=== MIN QTY FOR PARTIAL CLOSE ===
BTCUSDT: 0.002 | ETHUSDT: 0.02 | SOLUSDT: 0.2 | XRPUSDT: 20 | CRVUSDT: 20
These are 2x minimum to allow 50% partial close!

=== STEP 1: MANAGE EXISTING POSITIONS ===
{"FOR EACH position:" if state['position_count'] > 0 else "No positions to manage."}
{chr(10).join([f"  → {p.get('symbol')}: size={p.get('size')}, entry={p.get('entry')}, pnl={p.get('pnl')}" for p in state['open_positions']]) if state['open_positions'] else ""}

IF any position has P&L >= +1%:
  → PARTIAL CLOSE: Close exactly 50% of size
    Example: ETHUSDT size=0.02, close 0.01
    bybit_v5(action="place_order", symbol=X, kwargs='{{"side":"Sell","orderType":"Market","qty":"0.01","reduceOnly":true,"positionIdx":0}}')
  → MOVE SL TO BREAKEVEN:
    bybit_v5(action="set_trading_stop", symbol=X, kwargs='{{"stopLoss":"ENTRY_PRICE","positionIdx":0}}')
  → Journal the partial close

=== STEP 2: SCAN FOR NEW ENTRIES ===
{"SKIP - max positions reached" if not can_open_new else f'''
Scan these coins: {', '.join(available_coins)}

For each coin, run: check_entry_signal(symbol=COIN)

IF signal="ENTRY" found (score >= 5):
  → EXECUTE IMMEDIATELY (no confirmation needed):

  a) FIRST: Calculate leverage based on SL distance:
     → select_leverage(sl_distance_pct=SL_DISTANCE_FROM_SIGNAL)
     → This returns recommended_leverage (10-30x based on SL tightness)
     → LEVERAGE TABLE: SL<=0.5%→30x | SL<=1%→25x | SL<=1.5%→20x | SL<=2%→15x | SL>2%→10x

  b) Set the calculated leverage:
     bybit_v5(action="set_leverage", symbol=X, kwargs='{{"buyLeverage":"CALCULATED","sellLeverage":"CALCULATED"}}')

  c) Place order with PARTIAL-CLOSE ENABLED QTY:
     BTCUSDT: qty=0.002 | ETHUSDT: qty=0.02 | SOLUSDT: qty=0.2
     bybit_v5(action="place_order", symbol=X, kwargs='{{"side":"Buy/Sell","orderType":"Market","qty":"SEE_ABOVE","positionIdx":0}}')

  d) Set stop loss:
     bybit_v5(action="set_trading_stop", symbol=X, kwargs='{{"stopLoss":"X","positionIdx":0}}')

  e) Journal entry (include leverage used):
     journal(entry="Cycle #X: ENTRY [LONG/SHORT] | [COIN] @ [PRICE] | SL: [X] | Lev: [X]x | Size: [X]")

IF no signal on any coin: journal "NO TRADE - no valid SMC setup" and finish
'''}

=== POSITION SIZING v2 ===
Use calculate_position() with current balance from state above.
Risk: {RISK_PERCENT}% of balance per trade

DYNAMIC LEVERAGE (use select_leverage() based on SL distance):
- SL ≤0.5% → 30x leverage
- SL ≤1.0% → 25x leverage
- SL ≤1.5% → 20x leverage
- SL ≤2.0% → 15x leverage
- SL >2.0% → 10x leverage

ALWAYS call select_leverage(sl_distance_pct=X) first to get optimal leverage!

=== CRITICAL RULES ===
1. You are AUTONOMOUS - no human confirmation needed
2. Score 5+ = EXECUTE THE TRADE NOW
3. Use 2x minimum qty for ALL trades (enables partial close)
4. At +1% profit: ALWAYS partial close 50%, then SL to breakeven
5. After any action, write to journal and continue
6. Max {MAX_POSITIONS} positions - don't exceed
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

        print(f"\nStarting Smart Money trading agent v2...")
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

    parser = argparse.ArgumentParser(description="Hashtrade Smart Money Trading Agent v2")
    parser.add_argument("--interval", type=int, default=None,
                        help="Cycle interval in minutes (default: from .env or 5)")
    parser.add_argument("--once", action="store_true",
                        help="Run one cycle and exit")

    args = parser.parse_args()

    agent = HashtradeAgentV2()

    if args.once:
        agent.run_cycle()
        agent.show_stats()
    else:
        agent.start(interval_minutes=args.interval)
