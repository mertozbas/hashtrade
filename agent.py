#!/usr/bin/env python3
"""
Hashtrade Agent - Strategic Autonomous Trading
Uses DevDuck with flexible model provider support
"""
import sys
import time
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add current dir to path
sys.path.insert(0, str(Path(__file__).parent))

import devduck
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class HashtradeAgent:

    def __init__(self):
        print("Initializing Hashtrade Agent...")

        # Show model configuration
        model_provider = os.getenv('MODEL_PROVIDER', 'auto-detect')
        model_id = os.getenv('MODEL_ID', 'default')
        print(f"Model Provider: {model_provider}")
        print(f"Model ID: {model_id}")

        # Use DevDuck agent directly
        self.agent = devduck.devduck

        # Load local tools explicitly
        tools_dir = Path(__file__).parent / "tools"
        if tools_dir.exists():
            print(f"Loading tools from: {tools_dir}")
            try:
                from tools import balance, bybit_v5, ccxt_generic, order

                # Add to agent's tool registry
                self.agent.agent.tool_registry.register_tool(balance)
                self.agent.agent.tool_registry.register_tool(bybit_v5)
                self.agent.agent.tool_registry.register_tool(ccxt_generic)
                self.agent.agent.tool_registry.register_tool(order)

                print(f"Loaded 4 local tools: balance, bybit_v5, ccxt_generic, order")
            except Exception as e:
                print(f"Failed to load local tools: {e}")

        self.trade_count = 0
        self.session_start = datetime.now()

        print(f"DevDuck agent initialized with model: {self.agent.model}")
        print(f"Total tools: {len(self.agent.agent.tool_registry.registry)}")
        print(f"Mode: STRATEGIC - Trade only on high-probability setups")

    def get_last_journal_entry(self):
        """Son journal girişini oku"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            journal_path = Path(__file__).parent / "journal" / f"{today}.md"

            if journal_path.exists():
                with open(journal_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Son 2000 karakteri al (son birkaç cycle)
                    return content[-2000:] if len(content) > 2000 else content
            return "No previous journal entries today."
        except Exception as e:
            return f"Error reading journal: {e}"

    def get_current_context(self):
        """Mevcut balance ve pozisyonları çek"""
        try:
            # Balance bilgisi
            balance_result = self.agent.agent.tool.balance(action='get')
            balance_text = balance_result.get('content', [{}])[0].get('text', 'No balance info')

            # Açık pozisyonlar
            positions_result = self.agent.agent.tool.order(action='list')
            positions_text = positions_result.get('content', [{}])[0].get('text', 'No positions')

            return f"""
CURRENT STATE:
Balance: {balance_text}

Positions: {positions_text}

Last Journal:
{self.get_last_journal_entry()}
"""
        except Exception as e:
            return f"Error getting context: {e}"

    def run_cycle(self):
        """Run one strategic trading cycle"""
        self.trade_count += 1
        cycle_start = datetime.now()

        print(f"\n{'='*60}")
        print(f"Trading Cycle #{self.trade_count} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        # Context injection
        current_context = self.get_current_context()
        print(current_context)

        # Strategic workflow - NOT obligated to trade
        workflow = f"""
{current_context}

You are a strategic trading agent. Execute this cycle:

IMPORTANT RULES:
- You are NOT obligated to open any position
- "No trade" is a valid and often correct decision
- Only trade when there's a clear, high-probability setup
- Quality over quantity - fewer, better trades

CYCLE STEPS:

1. ANALYZE MARKET CONDITIONS
   - Use ccxt_generic to fetch tickers for BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
   - Check price action, 24h change, volume
   - Identify trend direction (up/down/sideways)

2. MANAGE EXISTING POSITIONS (if any)
   - Calculate P&L: (markPrice - avgPrice) / avgPrice * 100 * side
   - Close if take-profit hit: +3% or higher
   - Close if stop-loss hit: -2% or worse
   - Consider closing stale positions (>1 hour, <+1% profit)

3. EVALUATE NEW TRADE OPPORTUNITIES
   Check if ANY of these criteria are met:
   - Clear trend with momentum (not sideways/choppy)
   - Volume above average (confirmation)
   - Risk/reward ratio > 2:1
   - Not already at max positions (3)

   If NO valid setup exists:
   → Log "No setup found" and WAIT for next cycle
   → This is the CORRECT decision when market is unclear

4. EXECUTE TRADE (only if valid setup found)
   - Risk: max 4% of balance per trade
   - Leverage: 10-20x based on confidence
   - Set TP/SL immediately after entry

5. WRITE JOURNAL ENTRY (max 200 chars)
   Format: "Cycle #{self.trade_count}: [ACTION] | [REASON] | Balance: $X | Positions: X/3"

   Examples:
   - "Cycle #5: NO TRADE | BTC sideways, low volume | Balance: $78 | Positions: 1/3"
   - "Cycle #6: OPENED ETH LONG | Breakout + volume confirm | Balance: $78 | Positions: 2/3"
   - "Cycle #7: CLOSED BTC +2.3% | TP hit | Balance: $82 | Positions: 1/3"

Remember: Patience is profitable. Bad trades cost more than missed trades.
"""

        try:
            # Execute workflow with DevDuck
            result = self.agent(workflow)

            cycle_end = datetime.now()
            cycle_duration = (cycle_end - cycle_start).total_seconds()

            print(f"\nCycle completed in {cycle_duration:.1f}s")

            result_summary = str(result) if result else "No result"
            print(result_summary[:500] + "..." if len(result_summary) > 500 else result_summary)

        except Exception as e:
            print(f"Cycle error: {e}")

    def show_stats(self):
        """Display session statistics"""
        runtime = datetime.now() - self.session_start

        print(f"\nSession Stats:")
        print(f"  Runtime: {runtime}")
        print(f"  Cycles: {self.trade_count}")
        print(f"  Avg cycle time: {runtime.total_seconds() / max(1, self.trade_count):.1f}s")

    def start(self, interval_minutes: int = None):
        """Start strategic autonomous trading loop"""
        # Use env variable or default
        if interval_minutes is None:
            interval_minutes = int(os.getenv('CYCLE_INTERVAL', 5))

        print(f"\nStarting strategic autonomous trading agent...")
        print(f"Cycle interval: {interval_minutes} minutes")
        print(f"Strategy: Trade only on high-probability setups")
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

    parser = argparse.ArgumentParser(description="Hashtrade Strategic Trading Agent")
    parser.add_argument("--interval", type=int, default=None, help="Cycle interval in minutes (default: from .env or 5)")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")

    args = parser.parse_args()

    agent = HashtradeAgent()

    if args.once:
        agent.run_cycle()
        agent.show_stats()
    else:
        agent.start(interval_minutes=args.interval)
