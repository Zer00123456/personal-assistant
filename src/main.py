"""
Personal Assistant - Main Entry Point

Runs all services:
- Discord Bot (watches input channels)
- Pump.fun Monitor (watches for graduating coins)
- Alerts (sends Discord notifications)
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.bot import DiscordBot
from src.monitor import PumpFunMonitor, TwitterWatchMonitor
from src.alerts import DiscordAlerts
from src.database import TrendsDB


async def main():
    """Run all services concurrently"""
    
    print("=" * 50)
    print("🤖 Personal Assistant System Starting...")
    print("=" * 50)
    
    # Validate config
    try:
        config.validate()
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("   Make sure you've created a .env file from env.template")
        return
    
    # Initialize components
    bot = DiscordBot()
    monitor = PumpFunMonitor()
    twitter_watch = TwitterWatchMonitor()
    alerts = DiscordAlerts()
    
    # Wire up callbacks
    async def on_coin_match(coin, trend, matched_keyword, score):
        """Called when pump.fun monitor finds a match"""
        await alerts.send_match_alert(coin, trend, matched_keyword, score)
    
    async def on_trend_added(trend):
        """Called when a new trend is added via Discord"""
        # Optionally notify about new trends
        # await alerts.send_trend_added(trend)
        pass
    
    monitor.on_match = on_coin_match
    bot.on_trend_added = on_trend_added
    
    # Start all services
    print("\n📡 Starting services...")
    print(f"   • Discord Bot")
    print(f"   • Pump.fun Monitor (60s interval)")
    print(f"   • Twitter Dev Watch (2hr interval)")
    print(f"   • Alert System")
    print("\n")
    
    try:
        await asyncio.gather(
            bot.start(config.DISCORD_BOT_TOKEN),
            monitor.start(check_interval=60),
            twitter_watch.start(check_interval=7200),  # Check every 2 hours
        )
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        monitor.stop()
        twitter_watch.stop()
        await bot.close()


def run_bot_only():
    """Run just the Discord bot (for testing)"""
    config.validate()
    bot = DiscordBot()
    bot.run(config.DISCORD_BOT_TOKEN)


def run_monitor_only():
    """Run just the pump.fun monitor (for testing)"""
    monitor = PumpFunMonitor()
    alerts = DiscordAlerts()
    
    async def on_match(coin, trend, matched_keyword, score):
        await alerts.send_match_alert(coin, trend, matched_keyword, score)
    
    monitor.on_match = on_match
    asyncio.run(monitor.start(check_interval=60))


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Personal Assistant System")
    parser.add_argument("--bot-only", action="store_true", help="Run only Discord bot")
    parser.add_argument("--monitor-only", action="store_true", help="Run only pump.fun monitor")
    args = parser.parse_args()
    
    if args.bot_only:
        run_bot_only()
    elif args.monitor_only:
        run_monitor_only()
    else:
        asyncio.run(main())


