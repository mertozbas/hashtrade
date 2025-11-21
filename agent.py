#!/usr/bin/env python3
"""
🦆 Hashtrade Agent - Aggressive Autonomous Trading
Uses DevDuck
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
        print("🦆 Initializing AGGRESSIVE Hashtrade Agent...")
        
        # Use DevDuck agent directly
        self.agent = devduck.devduck
        
        # Load local tools explicitly
        tools_dir = Path(__file__).parent / "tools"
        if tools_dir.exists():
            print(f"📂 Loading tools from: {tools_dir}")
            try:
                from tools import balance, bybit_v5, ccxt_generic, order
                
                # Add to agent's tool registry
                self.agent.agent.tool_registry.register_tool(balance)
                self.agent.agent.tool_registry.register_tool(bybit_v5)
                self.agent.agent.tool_registry.register_tool(ccxt_generic)
                self.agent.agent.tool_registry.register_tool(order)
                
                print(f"✅ Loaded 4 local tools: balance, bybit_v5, ccxt_generic, order")
            except Exception as e:
                print(f"⚠️ Failed to load local tools: {e}")
        
        self.trade_count = 0
        self.session_start = datetime.now()
        
        print(f"✅ DevDuck agent initialized with model: {self.agent.model}")
        print(f"🔧 Total tools: {len(self.agent.agent.tool_registry.registry)}")
        print(f"⚡ Mode: AGGRESSIVE - High frequency, risk-taking")
    
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
📊 CURRENT STATE:
Balance: {balance_text}

Positions: {positions_text}

Last Journal:
{self.get_last_journal_entry()}
"""
        except Exception as e:
            return f"Error getting context: {e}"
        
    def run_cycle(self):
        """Run one aggressive trading cycle"""
        self.trade_count += 1
        cycle_start = datetime.now()
        
        print(f"\n{'='*60}")
        print(f"⚡ Trading Cycle #{self.trade_count} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        # Context injection
        current_context = self.get_current_context()
        print(current_context)
        # Simple but aggressive workflow
        workflow = f"""
{current_context}

Execute aggressive autonomous trading cycle:

1. Analyze current state above

2. Review ALL open positions:
   - Close if TP (+3-4%) or SL (-2%) hit
   - Close stale (>30min, <+1% profit)
   - Calculate P&L: (markPrice - avgPrice) / avgPrice * 100 * side

3. IF capacity < 3 positions:
   - Scan BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
   - Use ccxt_generic ONE ticker at a time (rate limit)
   - Look for breakout/momentum

4. Open new position if signal:
   - Risk: 4% balance
   - Leverage: 10-30x (based on confidence)
   - Set TP/SL immediately

5. Write SHORT journal entry (max 200 chars):
   Format: "Cycle #{self.trade_count}: [action] [symbol] [reason] | Balance: $X | Positions: X/3"
   Example: "Cycle #5: OPENED BTC LONG breakout +2.3% | Balance: $78 | Positions: 2/3"

GOAL: Grow to $1000. Cut losses fast, ride winners.
"""
        
        try:
            # Execute workflow with DevDuck
            result = self.agent(workflow)
            
            cycle_end = datetime.now()
            cycle_duration = (cycle_end - cycle_start).total_seconds()
            
            print(f"\n✅ Cycle completed in {cycle_duration:.1f}s")
            
            result_summary = str(result) if result else "No result"
            print(result_summary[:500] + "..." if len(result_summary) > 500 else result_summary)
            
        except Exception as e:
            print(f"❌ Cycle error: {e}")
    
    def show_stats(self):
        """Display session statistics"""
        runtime = datetime.now() - self.session_start
        
        print(f"\n📈 Session Stats:")
        print(f"  Runtime: {runtime}")
        print(f"  Cycles: {self.trade_count}")
        print(f"  Avg cycle time: {runtime.total_seconds() / max(1, self.trade_count):.1f}s")
    
    def start(self, interval_minutes: int = 3):
        """Start aggressive autonomous trading loop"""
        print(f"\n🚀 Starting AGGRESSIVE autonomous trading agent...")
        print(f"⏰ Cycle interval: {interval_minutes} minutes (HIGH FREQUENCY)")
        print(f"🎯 Goal: Maximize profits through active trading")
        print(f"🛑 Press Ctrl+C to stop\n")
        
        try:
            while True:
                self.run_cycle()
                self.show_stats()
                
                print(f"\n⏳ Waiting {interval_minutes} minutes until next cycle...")
                time.sleep(interval_minutes * 60)
        
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping agent...")
            self.show_stats()
            print("✅ Agent stopped gracefully")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Hashtrade AGGRESSIVE Autonomous Trading Agent")
    parser.add_argument("--interval", type=int, default=3, help="Cycle interval in minutes (default: 3)")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    
    args = parser.parse_args()
    
    agent = HashtradeAgent()
    
    if args.once:
        agent.run_cycle()
        agent.show_stats()
    else:
        agent.start(interval_minutes=args.interval)
