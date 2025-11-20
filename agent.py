#!/usr/bin/env python3
"""
🦆 Hashtrade Agent - Aggressive Autonomous Trading
Uses DevDuck
"""
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add devduck to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import devduck
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

class HashtradeAgent:
    
    def __init__(self):
        print("🦆 Initializing AGGRESSIVE Hashtrade Agent...")
        
        # Use DevDuck agent directly
        self.agent = devduck.devduck
        
      
        self.trade_count = 0
        self.session_start = datetime.now()
        
        print(f"✅ DevDuck agent initialized with model: {self.agent.model}")
        print(f"🔧 Available tools: {len(self.agent.tools)}")
        print(f"⚡ Mode: AGGRESSIVE - High frequency, risk-taking")
        
        
  
    def run_cycle(self):
        """Run one aggressive trading cycle"""
        self.trade_count += 1
        cycle_start = datetime.now()
        
        print(f"\n{'='*60}")
        print(f"⚡ Trading Cycle #{self.trade_count} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
       
        
        # Aggressive trading workflow
        workflow = """
        Execute the following autonomous trading workflow:
        AGGRESSIVE 
        1. Check and update current balance (use balance tool)
        2. Analyze market conditions for BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT, and others.
           - Fetch recent tickers using ccxt_generic
           - Check price changes and volumes
        3. List current open orders and positions (use order tool)
        4. Make trading decisions based on:
           - Current balance
           - Market trends
           - Risk management (3-5% per trade, 10-20x leverage)
        5. If conditions are favorable, consider opening positions
        6. Log all activities to journal
        
        Be autonomous. Start trading.
        """
        
        try:
            # Execute workflow with DevDuck
            result = self.agent(workflow)
            
            cycle_end = datetime.now()
            cycle_duration = (cycle_end - cycle_start).total_seconds()
            
            print(f"\n✅ Cycle completed in {cycle_duration:.1f}s")
            
            result_summary = str(result) if result else "No result"
            
            print(result_summary)
            
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
                
                # Shorter wait time for high-frequency trading
                print(f"\n⏳ Waiting {interval_minutes} minutes until next cycle...")
                time.sleep(interval_minutes * 60)
        
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping agent...")
            self.show_stats()
            
            # Send shutdown notification
            runtime = datetime.now() - self.session_start
            
            
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
