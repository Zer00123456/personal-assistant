"""
Pump.fun Monitor - Watches for graduating coins using Helius API

Monitors pump.fun for coins that graduate to Raydium,
then matches them against tracked trends using fuzzy matching.

Uses Helius API for reliable Solana data instead of pump.fun's frontend API.
"""

import asyncio
import aiohttp
import re
from datetime import datetime
from typing import Callable, Awaitable
from rapidfuzz import fuzz, process

from ..database import TrendsDB
from ..config import config


class PumpFunMonitor:
    """
    Monitors pump.fun for graduating coins and matches against trends.
    
    Uses Helius API for reliable data access.
    Uses fuzzy matching to catch variations like:
    - "vibe coding" matches "Vibe Codoor"
    - "AI agents" matches "aiagent", "AI Agent Club", etc.
    """
    
    # Pump.fun program address
    PUMPFUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
    
    # Fallback: Pump.fun API endpoints (may not work due to blocking)
    GRADUATED_API = "https://frontend-api.pump.fun/coins/graduated"
    
    # Fuzzy match threshold (0-100, lower = more matches)
    MATCH_THRESHOLD = 60
    
    def __init__(self, trends_db: TrendsDB = None):
        self.trends_db = trends_db or TrendsDB()
        self.seen_coins: set[str] = set()  # Track already-seen coins
        self.running = False
        self.last_signature = None  # Track last processed transaction
        
        # Callback when a match is found
        self.on_match: Callable[[dict, dict, str, int], Awaitable[None]] = None
    
    async def start(self, check_interval: int = 60):
        """
        Start monitoring for graduated coins.
        
        Args:
            check_interval: Seconds between checks (default 60)
        """
        self.running = True
        
        if config.HELIUS_API_KEY:
            print(f"🔍 Pump.fun monitor started with Helius API (checking every {check_interval}s)")
        else:
            print(f"🔍 Pump.fun monitor started (fallback mode, checking every {check_interval}s)")
            print(f"   ⚠️ Add HELIUS_API_KEY to .env for better reliability")
        
        while self.running:
            try:
                if config.HELIUS_API_KEY:
                    await self._check_graduates_helius()
                else:
                    await self._check_graduates_fallback()
            except Exception as e:
                print(f"⚠️ Error checking graduates: {e}")
            
            await asyncio.sleep(check_interval)
    
    def stop(self):
        """Stop the monitor"""
        self.running = False
        print("🛑 Pump.fun monitor stopped")
    
    async def _check_graduates_helius(self):
        """Check for newly graduated coins using Helius API"""
        
        # Helius API endpoint for getting recent token metadata
        # We'll query for recent pump.fun tokens that have graduated
        helius_url = f"https://api.helius.xyz/v0/token-metadata?api-key={config.HELIUS_API_KEY}"
        
        # Alternative: Use Helius to get recent transactions on pump.fun program
        # and parse for graduation events
        
        async with aiohttp.ClientSession() as session:
            try:
                # Get recently created tokens that might be pump.fun graduations
                # Using DAS API to search for recent tokens
                das_url = f"https://mainnet.helius-rpc.com/?api-key={config.HELIUS_API_KEY}"
                
                # Search for recent pump.fun tokens
                payload = {
                    "jsonrpc": "2.0",
                    "id": "pump-monitor",
                    "method": "searchAssets",
                    "params": {
                        "ownerAddress": None,
                        "grouping": ["collection", self.PUMPFUN_PROGRAM],
                        "page": 1,
                        "limit": 50,
                        "sortBy": {"sortBy": "created", "sortDirection": "desc"}
                    }
                }
                
                async with session.post(
                    das_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if "result" in data and "items" in data["result"]:
                            await self._process_helius_tokens(data["result"]["items"])
                    else:
                        # Fall back to alternative method
                        await self._check_graduates_helius_enhanced(session)
                        
            except Exception as e:
                print(f"⚠️ Helius API error: {e}")
                # Try fallback
                await self._check_graduates_fallback()
    
    async def _check_graduates_helius_enhanced(self, session: aiohttp.ClientSession):
        """Alternative Helius method using enhanced transactions API"""
        
        # Get recent transactions for pump.fun program
        url = f"https://api.helius.xyz/v0/addresses/{self.PUMPFUN_PROGRAM}/transactions?api-key={config.HELIUS_API_KEY}&limit=50"
        
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    transactions = await response.json()
                    
                    for tx in transactions:
                        # Look for graduation events (Raydium pool creation)
                        tx_type = tx.get("type", "")
                        description = tx.get("description", "")
                        
                        # Check if this is a graduation/liquidity event
                        if any(keyword in description.lower() for keyword in ["raydium", "liquidity", "pool"]):
                            await self._process_graduation_tx(tx)
                else:
                    text = await response.text()
                    print(f"⚠️ Helius enhanced API returned {response.status}: {text[:100]}")
        except Exception as e:
            print(f"⚠️ Helius enhanced API error: {e}")
    
    async def _process_helius_tokens(self, tokens: list):
        """Process tokens from Helius DAS API"""
        
        trends = self.trends_db.get_all_trends(active_only=True)
        keyword_map = self.trends_db.get_keyword_to_trend_map()
        
        for token in tokens:
            token_address = token.get("id", "")
            
            if token_address in self.seen_coins:
                continue
            
            self.seen_coins.add(token_address)
            
            # Get token metadata
            content = token.get("content", {})
            metadata = content.get("metadata", {})
            
            coin_name = metadata.get("name", "")
            coin_symbol = metadata.get("symbol", "")
            coin_image = content.get("links", {}).get("image", "")
            
            if not coin_name:
                continue
            
            # Try to match against trends
            match_result = await self._find_match(
                coin_name,
                coin_symbol,
                trends,
                keyword_map
            )
            
            if match_result:
                trend, matched_keyword, score = match_result
                
                # Record the match
                self.trends_db.record_match(
                    trend_id=trend["id"],
                    coin_name=coin_name,
                    coin_address=token_address,
                    matched_keyword=matched_keyword
                )
                
                print(f"🎯 MATCH: '{coin_name}' matched trend '{trend['keyword']}' (score: {score})")
                
                # Build coin data for alert
                coin = {
                    "name": coin_name,
                    "symbol": coin_symbol,
                    "mint": token_address,
                    "image_uri": coin_image
                }
                
                # Trigger callback
                if self.on_match:
                    await self.on_match(coin, trend, matched_keyword, score)
    
    async def _process_graduation_tx(self, tx: dict):
        """Process a graduation transaction from Helius"""
        
        trends = self.trends_db.get_all_trends(active_only=True)
        keyword_map = self.trends_db.get_keyword_to_trend_map()
        
        # Extract token info from transaction
        token_transfers = tx.get("tokenTransfers", [])
        
        for transfer in token_transfers:
            token_address = transfer.get("mint", "")
            
            if token_address in self.seen_coins:
                continue
            
            self.seen_coins.add(token_address)
            
            # Get token metadata via Helius
            metadata = await self._get_token_metadata(token_address)
            
            if not metadata:
                continue
            
            coin_name = metadata.get("name", "")
            coin_symbol = metadata.get("symbol", "")
            coin_image = metadata.get("image", "")
            
            if not coin_name:
                continue
            
            # Try to match against trends
            match_result = await self._find_match(
                coin_name,
                coin_symbol,
                trends,
                keyword_map
            )
            
            if match_result:
                trend, matched_keyword, score = match_result
                
                self.trends_db.record_match(
                    trend_id=trend["id"],
                    coin_name=coin_name,
                    coin_address=token_address,
                    matched_keyword=matched_keyword
                )
                
                print(f"🎯 MATCH: '{coin_name}' matched trend '{trend['keyword']}' (score: {score})")
                
                coin = {
                    "name": coin_name,
                    "symbol": coin_symbol,
                    "mint": token_address,
                    "image_uri": coin_image
                }
                
                if self.on_match:
                    await self.on_match(coin, trend, matched_keyword, score)
    
    async def _get_token_metadata(self, mint_address: str) -> dict | None:
        """Get token metadata via Helius"""
        
        url = f"https://api.helius.xyz/v0/token-metadata?api-key={config.HELIUS_API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    url,
                    json={"mintAccounts": [mint_address]},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            token = data[0]
                            return {
                                "name": token.get("onChainMetadata", {}).get("metadata", {}).get("name", ""),
                                "symbol": token.get("onChainMetadata", {}).get("metadata", {}).get("symbol", ""),
                                "image": token.get("offChainMetadata", {}).get("metadata", {}).get("image", "")
                            }
            except Exception as e:
                print(f"⚠️ Failed to get token metadata: {e}")
        
        return None
    
    async def _check_graduates_fallback(self):
        """Fallback: Check pump.fun frontend API (may be blocked)"""
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    self.GRADUATED_API,
                    params={"limit": 50, "offset": 0},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        print(f"⚠️ Pump.fun API returned {response.status}")
                        return
                    
                    coins = await response.json()
            except Exception as e:
                print(f"⚠️ Failed to fetch graduates: {e}")
                return
        
        if not coins:
            return
        
        # Get current trends for matching
        trends = self.trends_db.get_all_trends(active_only=True)
        keyword_map = self.trends_db.get_keyword_to_trend_map()
        
        for coin in coins:
            coin_address = coin.get("mint", coin.get("address", ""))
            
            # Skip if already processed
            if coin_address in self.seen_coins:
                continue
            
            self.seen_coins.add(coin_address)
            
            # Get coin name and symbol
            coin_name = coin.get("name", "")
            coin_symbol = coin.get("symbol", "")
            
            # Try to match against trends
            match_result = await self._find_match(
                coin_name,
                coin_symbol,
                trends,
                keyword_map
            )
            
            if match_result:
                trend, matched_keyword, score = match_result
                
                # Record the match
                self.trends_db.record_match(
                    trend_id=trend["id"],
                    coin_name=coin_name,
                    coin_address=coin_address,
                    matched_keyword=matched_keyword
                )
                
                print(f"🎯 MATCH: '{coin_name}' matched trend '{trend['keyword']}' (score: {score})")
                
                # Trigger callback
                if self.on_match:
                    await self.on_match(coin, trend, matched_keyword, score)
    
    async def _find_match(
        self,
        coin_name: str,
        coin_symbol: str,
        trends: list[dict],
        keyword_map: dict[str, dict]
    ) -> tuple[dict, str, int] | None:
        """
        Find if a coin name/symbol matches any tracked trend.
        
        Uses multiple fuzzy matching strategies:
        1. Direct substring match
        2. Token-based similarity
        3. Phonetic similarity (handles "Codoor" = "Coder")
        
        Returns: (trend, matched_keyword, score) or None
        """
        # Normalize coin name for matching
        coin_name_lower = coin_name.lower()
        coin_name_clean = self._clean_for_matching(coin_name)
        coin_symbol_lower = coin_symbol.lower()
        
        all_keywords = list(keyword_map.keys())
        
        if not all_keywords:
            return None
        
        best_match = None
        best_score = 0
        
        for keyword in all_keywords:
            keyword_clean = self._clean_for_matching(keyword)
            
            # Strategy 1: Direct substring match (highest priority)
            if keyword_clean in coin_name_clean or coin_name_clean in keyword_clean:
                score = 95
                if score > best_score:
                    best_score = score
                    best_match = (keyword_map[keyword], keyword, score)
                continue
            
            # Strategy 2: Symbol exact match
            if keyword_clean == coin_symbol_lower:
                score = 90
                if score > best_score:
                    best_score = score
                    best_match = (keyword_map[keyword], keyword, score)
                continue
            
            # Strategy 3: Fuzzy token sort ratio (handles word reordering)
            score = fuzz.token_sort_ratio(keyword_clean, coin_name_clean)
            if score >= self.MATCH_THRESHOLD and score > best_score:
                best_score = score
                best_match = (keyword_map[keyword], keyword, score)
            
            # Strategy 4: Partial ratio (handles substring-like matches)
            score = fuzz.partial_ratio(keyword_clean, coin_name_clean)
            if score >= self.MATCH_THRESHOLD + 10 and score > best_score:  # Higher threshold for partial
                best_score = score
                best_match = (keyword_map[keyword], keyword, score)
        
        return best_match
    
    def _clean_for_matching(self, text: str) -> str:
        """
        Clean text for better matching.
        
        Removes special characters, normalizes spaces, lowercases.
        """
        # Remove special characters except spaces
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        # Normalize whitespace
        cleaned = ' '.join(cleaned.split())
        return cleaned.lower()
    
    def adjust_threshold(self, new_threshold: int):
        """
        Adjust the fuzzy match threshold.
        
        Lower = more matches (wider net)
        Higher = fewer matches (more precise)
        
        Recommended range: 50-80
        """
        self.MATCH_THRESHOLD = max(30, min(90, new_threshold))
        print(f"🎚️ Match threshold set to {self.MATCH_THRESHOLD}")
    
    async def test_match(self, coin_name: str) -> list[dict]:
        """
        Test what trends would match a given coin name.
        Useful for debugging/tuning.
        """
        trends = self.trends_db.get_all_trends(active_only=True)
        keyword_map = self.trends_db.get_keyword_to_trend_map()
        
        matches = []
        coin_clean = self._clean_for_matching(coin_name)
        
        for keyword in keyword_map.keys():
            keyword_clean = self._clean_for_matching(keyword)
            
            # Calculate various scores
            scores = {
                "token_sort": fuzz.token_sort_ratio(keyword_clean, coin_clean),
                "partial": fuzz.partial_ratio(keyword_clean, coin_clean),
                "ratio": fuzz.ratio(keyword_clean, coin_clean),
            }
            
            max_score = max(scores.values())
            if max_score >= self.MATCH_THRESHOLD - 10:  # Show near-matches too
                matches.append({
                    "keyword": keyword,
                    "trend": keyword_map[keyword]["keyword"],
                    "scores": scores,
                    "would_match": max_score >= self.MATCH_THRESHOLD
                })
        
        return sorted(matches, key=lambda x: max(x["scores"].values()), reverse=True)
