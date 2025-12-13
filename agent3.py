#!/usr/bin/env python3
"""
Hashtrade Agent v3 - Liquidity Sweep Strategy
Multi-Timeframe analysis with dynamic SL/TP based on liquidity levels

Strategy:
1. 1H: Identify market bias + major liquidity pools
2. 15m: Detect liquidity sweep + confirmation
3. 5m: Refine entry timing
4. SL: Beyond sweep wick
5. TP: Opposing liquidity pool
6. Position management: 50% partial at 1:1 R:R, trail rest to TP
"""
import sys
import time
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent))

import devduck
from dotenv import load_dotenv

load_dotenv()

# Trading configuration - Liquidity Sweep Strategy
TRADING_COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "CRVUSDT"]
RISK_PERCENT = 10.0  # Risk 10% of balance per trade
MAX_POSITIONS = 3  # Allow up to 3 concurrent positions
MIN_RR_RATIO = 1.5  # Minimum R:R ratio to take a trade

# Note: Position sizing is calculated by calculate_position_dynamic()
# which already handles minimum quantities for partial close capability


class LiquiditySweepAgent:

    def __init__(self):
        print("=" * 60)
        print("Initializing Hashtrade Agent v3 - Liquidity Sweep Strategy")
        print("=" * 60)

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
                    # Liquidity tools
                    find_liquidity_pools, detect_liquidity_sweep,
                    get_opposing_liquidity, mtf_liquidity_scan,
                    # Position tools
                    calculate_position_dynamic, manage_position_v2, select_leverage
                )

                # Register all tools
                self.agent.agent.tool_registry.register_tool(balance)
                self.agent.agent.tool_registry.register_tool(bybit_v5)
                self.agent.agent.tool_registry.register_tool(order)
                self.agent.agent.tool_registry.register_tool(find_liquidity_pools)
                self.agent.agent.tool_registry.register_tool(detect_liquidity_sweep)
                self.agent.agent.tool_registry.register_tool(get_opposing_liquidity)
                self.agent.agent.tool_registry.register_tool(mtf_liquidity_scan)
                self.agent.agent.tool_registry.register_tool(calculate_position_dynamic)
                self.agent.agent.tool_registry.register_tool(manage_position_v2)
                self.agent.agent.tool_registry.register_tool(select_leverage)

                print(f"Loaded 10 tools successfully")
            except Exception as e:
                print(f"Failed to load tools: {e}")
                import traceback
                traceback.print_exc()

        self.trade_count = 0
        self.session_start = datetime.now()

        # Track partial closes with file persistence
        self.partial_closed_file = Path(__file__).parent / "data" / "partial_closed.json"
        self.partial_closed = self._load_partial_closed()

        # Track position sizes for reliable partial close detection
        self.position_sizes_file = Path(__file__).parent / "data" / "position_sizes.json"
        self.last_position_sizes = self._load_position_sizes()

        print(f"\nDevDuck agent initialized: {self.agent.model}")
        print(f"Strategy: Liquidity Sweep (MTF: 1H/15m/5m)")
        print(f"Coins: {', '.join(TRADING_COINS)}")
        print(f"Risk: {RISK_PERCENT}% per trade | Min R:R: {MIN_RR_RATIO}")
        print(f"Max positions: {MAX_POSITIONS}")
        print("=" * 60)

    def _load_partial_closed(self) -> Dict[str, bool]:
        """Load partial close tracking from file"""
        try:
            if self.partial_closed_file.exists():
                with open(self.partial_closed_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load partial_closed: {e}")
        return {}

    def _save_partial_closed(self):
        """Save partial close tracking to file"""
        try:
            self.partial_closed_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.partial_closed_file, 'w') as f:
                json.dump(self.partial_closed, f)
        except Exception as e:
            print(f"Warning: Could not save partial_closed: {e}")

    def _load_position_sizes(self) -> Dict[str, float]:
        """Load last known position sizes from file"""
        try:
            if self.position_sizes_file.exists():
                with open(self.position_sizes_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load position_sizes: {e}")
        return {}

    def _save_position_sizes(self, sizes: Dict[str, float]):
        """Save current position sizes to file"""
        try:
            self.position_sizes_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.position_sizes_file, 'w') as f:
                json.dump(sizes, f)
            self.last_position_sizes = sizes
        except Exception as e:
            print(f"Warning: Could not save position_sizes: {e}")

    def detect_partial_close_from_size(self, open_positions: list):
        """
        Detect partial closes by comparing current position sizes with last known sizes.
        If size decreased by 40-60%, it's a partial close.
        """
        current_sizes = {p.get('symbol', ''): float(p.get('size', 0)) for p in open_positions}

        for symbol, current_size in current_sizes.items():
            if symbol in self.last_position_sizes and symbol not in self.partial_closed:
                last_size = self.last_position_sizes[symbol]
                if last_size > 0 and current_size > 0:
                    # Calculate size reduction ratio
                    reduction_ratio = current_size / last_size
                    # If size reduced to 40-60% of original, it's a partial close
                    if 0.4 <= reduction_ratio <= 0.6:
                        self.mark_partial_closed(symbol)
                        print(f"Detected partial close for {symbol}: {last_size} -> {current_size} ({reduction_ratio:.1%})")

        # Save current sizes for next comparison
        self._save_position_sizes(current_sizes)

    def mark_partial_closed(self, symbol: str):
        """Mark a symbol as having been partially closed"""
        self.partial_closed[symbol] = True
        self._save_partial_closed()
        print(f"Marked {symbol} as partially closed")

    def clear_partial_closed(self, symbol: str):
        """Clear partial close status for a symbol (when position is fully closed)"""
        if symbol in self.partial_closed:
            del self.partial_closed[symbol]
            self._save_partial_closed()
            print(f"Cleared partial close status for {symbol}")

    def sync_partial_closed_with_positions(self, open_positions: list):
        """Remove partial_closed entries for symbols no longer in positions"""
        positioned_symbols = {p.get('symbol', '') for p in open_positions}
        closed_symbols = [s for s in self.partial_closed if s not in positioned_symbols]
        for symbol in closed_symbols:
            self.clear_partial_closed(symbol)

    def get_last_journal_entry(self):
        """Read last journal entry for context"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            journal_path = Path(__file__).parent / "journal" / f"{today}.md"

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
        """Run one trading cycle with Liquidity Sweep strategy"""
        self.trade_count += 1
        cycle_start = datetime.now()

        print(f"\n{'='*60}")
        print(f"CYCLE #{self.trade_count} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        # Get current state
        state = self.get_current_state()
        journal = self.get_last_journal_entry()

        # Sync partial_closed with actual positions (clean up closed positions)
        self.sync_partial_closed_with_positions(state['open_positions'])

        # Detect partial closes by comparing position sizes (reliable method)
        self.detect_partial_close_from_size(state['open_positions'])

        # Build context
        context = f"""
CURRENT STATE:
{state['balance_text']}

OPEN POSITIONS ({state['position_count']}/{MAX_POSITIONS}):
{state['positions_text']}

RECENT JOURNAL:
{journal[-800:]}
"""
        print(context)

        # Get symbols with positions
        positioned_symbols = [p.get('symbol', '') for p in state['open_positions']]
        available_coins = [c for c in TRADING_COINS if c not in positioned_symbols]
        can_open_new = state['position_count'] < MAX_POSITIONS

        # Build position info for management with accurate partial_closed tracking
        position_info = ""
        partial_closed_symbols = []
        for p in state['open_positions']:
            sym = p.get('symbol', '')
            is_partial = self.partial_closed.get(sym, False)
            partial_status = "PARTIAL_CLOSED" if is_partial else "FULL"
            if is_partial:
                partial_closed_symbols.append(sym)
            position_info += f"  {sym}: size={p.get('size')}, entry={p.get('entry')}, pnl={p.get('pnl')}, status={partial_status}\n"

        # Create partial_closed info for workflow
        partial_closed_json = json.dumps(self.partial_closed)

        # Strategy workflow
        workflow = f"""
{context}

You are an AUTONOMOUS Liquidity Sweep trading bot. Execute trades WITHOUT asking for confirmation.

=== CONFIG ===
Coins: {', '.join(TRADING_COINS)}
Risk: {RISK_PERCENT}% | Min R:R: {MIN_RR_RATIO}
Open: {state['position_count']}/{MAX_POSITIONS} | Can open new: {can_open_new}

=== PARTIAL CLOSE TRACKING ===
Already partial closed: {partial_closed_json}
DO NOT partial close these symbols again!

=== STEP 1: MANAGE EXISTING POSITIONS ===
{position_info if position_info else "No positions to manage."}

FOR EACH open position:
1. Get current price from bybit_v5(action="get_ticker", symbol=X)
2. Check R:R with manage_position_v2(action="check_rr", entry_price=X, current_price=X, stop_loss=X, direction=X, partial_closed=X)
3. IF action="PARTIAL_CLOSE" and NOT already partial closed:
   → Close 50%: bybit_v5(action="place_order", symbol=X, kwargs='{{"side":"Sell/Buy","orderType":"Market","qty":"HALF","reduceOnly":true,"positionIdx":0}}')
   → Move SL to entry: bybit_v5(action="set_trading_stop", symbol=X, kwargs='{{"stopLoss":"ENTRY","positionIdx":0}}')
   → Journal: "PARTIAL CLOSE | [symbol] @ [price] | SL moved to BE"
4. Check TP with manage_position_v2(action="check_tp", ...)
5. IF action="CLOSE_ALL":
   → Close remaining: bybit_v5(action="place_order", ..., reduceOnly=true)
   → Journal: "TP HIT | [symbol] | Full close"

=== STEP 2: SCAN FOR NEW ENTRIES (if can_open_new) ===
{"SKIP - max positions reached or all coins positioned" if not can_open_new or not available_coins else f'''
Scan these coins: {', '.join(available_coins)}

FOR EACH coin, run: mtf_liquidity_scan(symbol=COIN)

This returns:
- htf.bias: 1H trend (bullish/bearish/neutral)
- mtf.sweep_detected: bool
- mtf.sweep_type: bullish/bearish
- mtf.confirmation: bool
- setup: entry, sl, tp, rr_ratio (if valid)

IF signal="ENTRY" AND setup.rr_ratio >= {MIN_RR_RATIO}:

  1. FIRST get balance: balance(action="get") → extract equity number

  2. Calculate position size (CRITICAL - use the returned values!):
     result = calculate_position_dynamic(
       balance=EQUITY_FROM_STEP_1,
       entry_price=setup.entry,
       stop_loss=setup.sl,
       take_profit=setup.tp,
       risk_percent={RISK_PERCENT},
       symbol=COIN
     )
     → USE result.quantity for order qty!
     → USE result.leverage for leverage setting!

  3. Set leverage from calculate_position_dynamic result:
     bybit_v5(action="set_leverage", symbol=X, kwargs='{{"buyLeverage":"RESULT_LEVERAGE","sellLeverage":"RESULT_LEVERAGE"}}')

  4. Place order with CALCULATED QTY (not min qty!):
     bybit_v5(action="place_order", symbol=X, kwargs='{{"side":"Buy/Sell","orderType":"Market","qty":"RESULT_QUANTITY","positionIdx":0}}')

     IMPORTANT: qty must be result.quantity from step 2, NOT a fixed minimum!
     Example: If result.quantity = 6000 for CRV, use qty="6000"

  5. Set stop loss:
     bybit_v5(action="set_trading_stop", symbol=X, kwargs='{{"stopLoss":"SL","positionIdx":0}}')

  6. Journal entry:
     "ENTRY | [direction] [symbol] @ [price] | SL: [sl] | TP: [tp] | R:R 1:[rr] | Qty: [qty] | Lev: [lev]x"

IF no valid setup on any coin:
  → Journal: "NO TRADE | Reason: [no sweep / no confirmation / R:R too low]"
'''}

=== LIQUIDITY SWEEP STRATEGY RULES ===

ENTRY CONDITIONS (ALL must be true):
1. 1H bias aligns with sweep direction (or neutral)
2. 15m liquidity sweep detected (wick beyond swing point, close inside)
3. Confirmation candle (reversal candle after sweep)
4. R:R >= {MIN_RR_RATIO}

STOP LOSS:
- Place beyond the sweep wick (with 0.2% buffer)
- NO fixed % limit - strategy determines SL

TAKE PROFIT:
- Target: Opposing liquidity pool from 1H
- Dynamic target based on market structure

POSITION MANAGEMENT:
1. At 1:1 R:R: Close 50%, move SL to breakeven
2. Trail remaining 50% toward TP
3. Exit at TP or structure break

=== CRITICAL ===
1. AUTONOMOUS - no confirmation needed
2. R:R {MIN_RR_RATIO}+ = EXECUTE
3. Always check balance FIRST before sizing
4. USE CALCULATED QTY from calculate_position_dynamic (NOT fixed min qty!)
5. Risk {RISK_PERCENT}% of balance = proper position size
6. Journal ALL actions
"""

        try:
            result = self.agent(workflow)

            cycle_end = datetime.now()
            cycle_duration = (cycle_end - cycle_start).total_seconds()

            print(f"\nCycle completed in {cycle_duration:.1f}s")

            if result:
                result_str = str(result)
                print(result_str[:1000] + "..." if len(result_str) > 1000 else result_str)

            # Note: Partial close detection is now done via position size comparison
            # at the start of each cycle (detect_partial_close_from_size method)
            # This is more reliable than string parsing agent output

        except Exception as e:
            print(f"Cycle error: {e}")
            import traceback
            traceback.print_exc()

    def show_stats(self):
        """Display session statistics"""
        runtime = datetime.now() - self.session_start

        print(f"\n--- Session Stats ---")
        print(f"Runtime: {runtime}")
        print(f"Cycles: {self.trade_count}")
        if self.trade_count > 0:
            print(f"Avg cycle time: {runtime.total_seconds() / self.trade_count:.1f}s")
        print(f"Partial closes tracked: {sum(self.partial_closed.values())}")

    def start(self, interval_minutes: int = None):
        """Start autonomous trading loop"""
        if interval_minutes is None:
            interval_minutes = int(os.getenv('CYCLE_INTERVAL', 5))

        print(f"\nStarting Liquidity Sweep trading agent...")
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

    parser = argparse.ArgumentParser(description="Hashtrade Liquidity Sweep Agent v3")
    parser.add_argument("--interval", type=int, default=None,
                        help="Cycle interval in minutes (default: from .env or 5)")
    parser.add_argument("--once", action="store_true",
                        help="Run one cycle and exit")

    args = parser.parse_args()

    agent = LiquiditySweepAgent()

    if args.once:
        agent.run_cycle()
        agent.show_stats()
    else:
        agent.start(interval_minutes=args.interval)
