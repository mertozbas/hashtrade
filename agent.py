#!/usr/bin/env python3
"""
🦆 Hashtrade Agent - Aggressive Autonomous Trading
Uses DevDuck with integrated Telegram notifications
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
    """Aggressive autonomous trading agent using DevDuck with Telegram"""
    
    def __init__(self):
        print("🦆 Initializing AGGRESSIVE Hashtrade Agent...")
        
        # Use DevDuck agent directly
        self.agent = devduck.devduck
        
        # Verify Telegram is available
        if 'telegram' not in self.agent.agent.tool_names:
            print("⚠️ Warning: Telegram tool not loaded")
        
        self.trade_count = 0
        self.session_start = datetime.now()
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        print(f"✅ DevDuck agent initialized with model: {self.agent.model}")
        print(f"🔧 Available tools: {len(self.agent.tools)}")
        print(f"⚡ Mode: AGGRESSIVE - High frequency, risk-taking")
        
        # Send startup notification
        self.send_telegram_notification(
            "🚀 *Hashtrade Agent Started*\n\n"
            f"Model: {self.agent.model}\n"
            f"Tools: {len(self.agent.tools)}\n"
            f"Mode: AGGRESSIVE\n"
            f"Started: {self.session_start.strftime('%H:%M:%S')}"
        )
        
    def send_telegram_notification(self, message: str):
        """Send Telegram notification using DevDuck's telegram tool"""
        if not self.telegram_chat_id:
            return
        
        try:
            self.agent.agent.tool.telegram(
                action="send_message",
                chat_id=self.telegram_chat_id,
                text=message,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"⚠️ Telegram notification failed: {e}")
    
    def run_cycle(self):
        """Run one aggressive trading cycle"""
        self.trade_count += 1
        cycle_start = datetime.now()
        
        print(f"\n{'='*60}")
        print(f"⚡ AGGRESSIVE Trading Cycle #{self.trade_count} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        # Send cycle start notification
        self.send_telegram_notification(
            f"⚡ *Cycle #{self.trade_count}*\n"
            f"Time: {cycle_start.strftime('%H:%M:%S')}"
        )
        
        # Aggressive trading workflow
        workflow = """
        Execute AGGRESSIVE autonomous trading workflow:
        
        🎯 OBJECTIVE: Maximize profits through active trading
        
        1. **Balance Check** (use balance tool)
           - Get current USDT balance
           - Calculate available capital for new trades
        
        2. **Open Positions Review** (use order tool with action="list")
           - Check all open positions
           - Evaluate P&L for each
           - Close positions that:
             * Hit +3-5% profit (take profit)
             * Hit -2% loss (stop loss)
             * Been open >30 minutes without movement
        
        3. **Market Signal Generation** (use generate_all_signals)
           - Scan ALL 15 coins simultaneously
           - Look for STRONG breakout signals (>60% confidence)
           - Prioritize volume spikes (>1.5x average)
        
        4. **Signal Scoring & Ranking** (use score_signal and rank_signals)
           - Score each signal 0-100
           - Filter: Only signals >70 score
           - Rank by: confidence × volume × momentum
        
        5. **Order Flow Analysis** (use analyze_order_flow)
           - Check buy/sell pressure
           - Confirm breakout direction
           - Look for institutional activity
        
        6. **AGGRESSIVE Position Opening** (use order tool with action="open")
           - Risk per trade: 3-5% of balance (HIGHER than conservative 2%)
           - Leverage: 10-20x (based on confidence)
             * 80%+ confidence → 20x leverage
             * 70-80% confidence → 15x leverage
             * 60-70% confidence → 10x leverage
           - Max positions: 2-3 simultaneous trades
           - Entry: Market orders for SPEED
           - IMPORTANT: Open AT LEAST 1 position per cycle if signals exist
        
        7. **Telegram Notification** (send trade summary)
           - Report balance changes
           - List new positions opened
           - Show closed positions with P&L
           - Alert if significant profit/loss
        
        ⚡ AGGRESSIVE RULES:
        - Don't wait for "perfect" setups - ACT on good signals
        - Speed > Precision - Market orders preferred
        - High frequency - More trades = More opportunities
        - Risk management - Use stop losses religiously
        - Momentum trading - Ride trends quickly
        
        🎯 SUCCESS METRICS:
        - Open 1-3 trades per cycle
        - Win rate target: >60%
        - Average trade duration: 15-30 minutes
        - Daily compound growth target: 5-10%
        
        Use all available tools effectively. Be decisive and aggressive.
        """
        
        try:
            # Execute workflow with DevDuck
            result = self.agent(workflow)
            
            cycle_end = datetime.now()
            cycle_duration = (cycle_end - cycle_start).total_seconds()
            
            print(f"\n✅ Cycle completed in {cycle_duration:.1f}s")
            
            # Extract key info from result for Telegram
            result_summary = str(result)[:500] if result else "No result"
            
            # Send cycle completion notification
            self.send_telegram_notification(
                f"✅ *Cycle #{self.trade_count} Complete*\n"
                f"Duration: {cycle_duration:.1f}s\n"
                f"Status: Success"
            )
            
        except Exception as e:
            print(f"❌ Cycle error: {e}")
            self.send_telegram_notification(
                f"❌ *Cycle #{self.trade_count} Failed*\n"
                f"Error: {str(e)[:200]}"
            )
    
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
        print(f"⚡ Risk profile: AGGRESSIVE (3-5% per trade, 10-20x leverage)")
        print(f"🎯 Goal: Maximize profits through active trading")
        print(f"📱 Telegram notifications: {'Enabled' if self.telegram_chat_id else 'Disabled'}")
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
            self.send_telegram_notification(
                "🛑 *Agent Stopped*\n\n"
                f"Total cycles: {self.trade_count}\n"
                f"Runtime: {runtime}\n"
                f"Stopped: {datetime.now().strftime('%H:%M:%S')}"
            )
            
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
