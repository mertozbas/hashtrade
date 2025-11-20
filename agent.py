#!/usr/bin/env python3
"""
Hashtrade Autonomous Trading Agent
Uses DevDuck's capabilities with custom trading tools
"""
import devduck
import os
import time
from datetime import datetime
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

class HashtradeAgent:
    """Autonomous trading agent using DevDuck"""
    
    def __init__(self):
        print("🦆 Initializing Hashtrade Agent...")
        self.agent = devduck.devduck
        print(f"✅ Agent initialized with model: {self.agent.model}")
        print(f"🔧 Available tools: {len(self.agent.tools)}")
        
    def run_cycle(self):
        """Run one trading cycle"""
        print(f"\n{'='*60}")
        print(f"🔄 Trading Cycle - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        # Trading workflow
        workflow = """
        Execute the following autonomous trading workflow:
        
        1. Check and update current balance (use balance tool)
        2. Analyze market conditions for BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
           - Fetch recent tickers using ccxt_generic
           - Check 24h price changes and volumes
        3. List current open orders and positions (use order tool)
        4. Make trading decisions based on:
           - Current balance
           - Market trends
           - Risk management (max 2% per trade)
        5. If conditions are favorable, consider opening positions
        6. Log all activities to journal
        
        Be autonomous but cautious. Only trade if you have high confidence.
        """
        
        result = self.agent(workflow)
        print(f"\n📊 Cycle Result:\n{result}")
        
        return result
    
    def start(self, interval_minutes: int = 5):
        """Start autonomous trading loop"""
        print(f"\n🚀 Starting autonomous trading agent...")
        print(f"⏰ Cycle interval: {interval_minutes} minutes")
        print(f"🛑 Press Ctrl+C to stop\n")
        
        try:
            while True:
                self.run_cycle()
                
                # Wait for next cycle
                print(f"\n⏳ Waiting {interval_minutes} minutes until next cycle...")
                time.sleep(interval_minutes * 60)
        
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping agent...")
            print("✅ Agent stopped gracefully")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Hashtrade Autonomous Trading Agent")
    parser.add_argument("--interval", type=int, default=5, help="Cycle interval in minutes (default: 5)")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    
    args = parser.parse_args()
    
    agent = HashtradeAgent()
    
    if args.once:
        agent.run_cycle()
    else:
        agent.start(interval_minutes=args.interval)
