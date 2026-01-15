"""
Discord Webhook Alerts

Sends alerts to Discord when coins match tracked trends.
"""

import aiohttp
from datetime import datetime
from ..config import config


class DiscordAlerts:
    """Sends alerts via Discord webhook"""
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or config.COIN_ALERTS_WEBHOOK
    
    async def send_match_alert(
        self,
        coin: dict,
        trend: dict,
        matched_keyword: str,
        match_score: int
    ):
        """
        Send an alert when a graduated coin matches a trend.
        
        Args:
            coin: Coin data from pump.fun
            trend: The matched trend
            matched_keyword: Which keyword triggered the match
            match_score: Fuzzy match score (0-100)
        """
        coin_name = coin.get("name", "Unknown")
        coin_symbol = coin.get("symbol", "???")
        coin_address = coin.get("mint", coin.get("address", ""))
        coin_image = coin.get("image_uri", coin.get("image", ""))
        
        # Build embed
        embed = {
            "title": f"🚨 COIN MATCH: {coin_name} (${coin_symbol})",
            "color": self._get_color_for_score(match_score),
            "fields": [
                {
                    "name": "🎯 Matched Trend",
                    "value": f"**{trend['keyword']}**",
                    "inline": True
                },
                {
                    "name": "📊 Match Score",
                    "value": f"{match_score}%",
                    "inline": True
                },
                {
                    "name": "🔥 Trend Priority",
                    "value": "⭐" * trend.get("priority", 1),
                    "inline": True
                },
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Add trend description if available
        if trend.get("description"):
            embed["fields"].append({
                "name": "📝 Trend Context",
                "value": trend["description"][:200],
                "inline": False
            })
        
        # Add coin links
        links = []
        if coin_address:
            links.append(f"[Pump.fun](https://pump.fun/{coin_address})")
            links.append(f"[DexScreener](https://dexscreener.com/solana/{coin_address})")
            links.append(f"[Birdeye](https://birdeye.so/token/{coin_address})")
        
        if links:
            embed["fields"].append({
                "name": "🔗 Quick Links",
                "value": " | ".join(links),
                "inline": False
            })
        
        # Add coin image as thumbnail if available
        if coin_image:
            embed["thumbnail"] = {"url": coin_image}
        
        # Add footer
        embed["footer"] = {
            "text": f"Matched via: {matched_keyword}"
        }
        
        # Send webhook
        payload = {
            "embeds": [embed]
        }
        
        await self._send_webhook(payload)
    
    async def send_simple_alert(self, message: str, title: str = None):
        """Send a simple text alert"""
        payload = {
            "content": f"**{title}**\n{message}" if title else message
        }
        await self._send_webhook(payload)
    
    async def send_trend_added(self, trend: dict):
        """Notify when a new trend is added"""
        embed = {
            "title": "📈 New Trend Added",
            "color": 0x00ff00,
            "fields": [
                {
                    "name": "Keyword",
                    "value": trend["keyword"],
                    "inline": True
                },
                {
                    "name": "Source",
                    "value": trend.get("source", "manual"),
                    "inline": True
                }
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if trend.get("description"):
            embed["fields"].append({
                "name": "Description",
                "value": trend["description"][:200],
                "inline": False
            })
        
        await self._send_webhook({"embeds": [embed]})
    
    async def send_status_update(self, trends_count: int, matches_today: int = 0):
        """Send a status update"""
        embed = {
            "title": "📊 System Status",
            "color": 0x0099ff,
            "fields": [
                {
                    "name": "Active Trends",
                    "value": str(trends_count),
                    "inline": True
                },
                {
                    "name": "Matches Today",
                    "value": str(matches_today),
                    "inline": True
                }
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        await self._send_webhook({"embeds": [embed]})
    
    def _get_color_for_score(self, score: int) -> int:
        """Get embed color based on match score"""
        if score >= 90:
            return 0xff0000  # Red - very strong match
        elif score >= 80:
            return 0xff6600  # Orange - strong match
        elif score >= 70:
            return 0xffcc00  # Yellow - good match
        else:
            return 0x00ccff  # Blue - moderate match
    
    async def _send_webhook(self, payload: dict):
        """Send payload to Discord webhook"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status not in [200, 204]:
                        print(f"⚠️ Webhook error: {response.status}")
                        text = await response.text()
                        print(f"   Response: {text[:200]}")
            except Exception as e:
                print(f"⚠️ Failed to send webhook: {e}")


