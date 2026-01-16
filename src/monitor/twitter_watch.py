"""
Twitter Dev Watch Monitor

Monitors specific Twitter accounts for mentions of target keywords.
Sends Discord alerts when matches are found.
"""

import asyncio
import aiohttp
import re
from datetime import datetime, timedelta
from typing import Optional

from ..config import config


class TwitterWatchMonitor:
    """
    Monitors Twitter accounts for keyword mentions.
    Uses SocialData API for tweet fetching.
    """
    
    # Accounts to watch: (username, display_name, associated_coin)
    WATCH_LIST = [
        ("jamiepine", "Jamie Pine", "Spacedrive2"),
        ("DannyLimanseta", "Danny Limanseta", "Vibeforge"),
    ]
    
    # Keywords to watch for (case insensitive)
    KEYWORDS = ["bagsapp", "bags app", "$bags", "bags token"]
    
    # Discord webhook for alerts
    ALERT_WEBHOOK = config.MEMECOIN_ALERTS_WEBHOOK
    
    def __init__(self):
        self.seen_tweets: set[str] = set()  # Track already-alerted tweets
        self.running = False
        self.last_check: dict[str, datetime] = {}
    
    async def start(self, check_interval: int = 7200):  # Default 2 hours
        """
        Start monitoring Twitter accounts.
        
        Args:
            check_interval: Seconds between checks (default 7200 = 2 hours)
        """
        self.running = True
        
        if not config.RAPIDAPI_KEY:
            print("⚠️ Twitter Watch: No SocialData API key configured. Skipping.")
            return
        
        print(f"👀 Twitter Watch started (checking every {check_interval//60} min)")
        print(f"   Watching: {', '.join([w[0] for w in self.WATCH_LIST])}")
        print(f"   Keywords: {', '.join(self.KEYWORDS)}")
        
        while self.running:
            try:
                await self._check_all_accounts()
            except Exception as e:
                print(f"⚠️ Twitter Watch error: {e}")
            
            await asyncio.sleep(check_interval)
    
    def stop(self):
        """Stop the monitor"""
        self.running = False
        print("🛑 Twitter Watch stopped")
    
    async def _check_all_accounts(self):
        """Check all watched accounts for keyword mentions"""
        
        print(f"🔍 Twitter Watch: Checking {len(self.WATCH_LIST)} accounts...")
        
        for username, display_name, coin in self.WATCH_LIST:
            try:
                await self._check_account(username, display_name, coin)
                await asyncio.sleep(2)  # Small delay between accounts
            except Exception as e:
                print(f"   ⚠️ Error checking @{username}: {e}")
    
    async def _check_account(self, username: str, display_name: str, coin: str):
        """Check a single account's recent tweets"""
        
        tweets = await self._get_recent_tweets(username)
        
        if not tweets:
            print(f"   @{username}: No tweets found or API error")
            return
        
        print(f"   @{username}: Checking {len(tweets)} recent tweets")
        
        for tweet in tweets:
            tweet_id = tweet.get("id_str") or tweet.get("id")
            tweet_text = tweet.get("full_text") or tweet.get("text") or ""
            
            if not tweet_id or tweet_id in self.seen_tweets:
                continue
            
            # Check for keyword matches
            match = self._check_keywords(tweet_text)
            
            if match:
                print(f"   🚨 MATCH FOUND: @{username} mentioned '{match}'")
                await self._send_alert(username, display_name, coin, tweet_text, match, tweet_id)
                self.seen_tweets.add(tweet_id)
    
    def _check_keywords(self, text: str) -> Optional[str]:
        """Check if text contains any watched keywords"""
        
        text_lower = text.lower()
        
        for keyword in self.KEYWORDS:
            if keyword.lower() in text_lower:
                return keyword
        
        return None
    
    async def _get_recent_tweets(self, username: str) -> list:
        """Fetch recent tweets from a user via SocialData API"""
        
        try:
            headers = {
                "Authorization": f"Bearer {config.RAPIDAPI_KEY}",
                "Content-Type": "application/json"
            }
            
            # SocialData API endpoint for user tweets
            api_url = f"https://api.socialdata.tools/twitter/user/{username}/tweets"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api_url,
                    headers=headers,
                    params={"limit": 10},  # Get last 10 tweets
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("tweets", []) if isinstance(data, dict) else data
                    elif response.status == 402:
                        print(f"   ⚠️ SocialData API: Credits depleted")
                        return []
                    else:
                        error_text = await response.text()
                        print(f"   ⚠️ SocialData API error {response.status}: {error_text[:100]}")
                        return []
        
        except Exception as e:
            print(f"   ⚠️ Twitter API exception: {e}")
            return []
    
    async def _send_alert(
        self, 
        username: str, 
        display_name: str, 
        coin: str, 
        tweet_text: str, 
        matched_keyword: str,
        tweet_id: str
    ):
        """Send Discord webhook alert"""
        
        if not self.ALERT_WEBHOOK:
            print("   ⚠️ No Discord webhook configured for alerts")
            return
        
        tweet_url = f"https://x.com/{username}/status/{tweet_id}"
        
        embed = {
            "title": f"🚨 DEV ALERT: {display_name} mentioned '{matched_keyword}'",
            "description": f"**Coin:** {coin}\n**Dev:** @{username}\n\n**Tweet:**\n{tweet_text[:500]}",
            "color": 0xFF6B00,  # Orange
            "fields": [
                {"name": "Keyword Matched", "value": matched_keyword, "inline": True},
                {"name": "Tweet Link", "value": f"[View Tweet]({tweet_url})", "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Twitter Dev Watch"}
        }
        
        payload = {
            "embeds": [embed]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.ALERT_WEBHOOK,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status in [200, 204]:
                        print(f"   ✅ Discord alert sent!")
                    else:
                        print(f"   ⚠️ Discord webhook error: {response.status}")
        
        except Exception as e:
            print(f"   ⚠️ Discord webhook exception: {e}")
    
    async def check_now(self):
        """Manual trigger to check all accounts immediately"""
        print("🔍 Twitter Watch: Manual check triggered")
        await self._check_all_accounts()
    
    def add_watch(self, username: str, display_name: str, coin: str):
        """Add a new account to the watch list"""
        self.WATCH_LIST.append((username, display_name, coin))
        print(f"👀 Added @{username} to Twitter watch list")
    
    def add_keyword(self, keyword: str):
        """Add a new keyword to watch for"""
        self.KEYWORDS.append(keyword)
        print(f"🔑 Added '{keyword}' to keyword watch list")

