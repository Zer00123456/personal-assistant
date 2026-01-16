"""
Discord Bot - Watches input channels and processes content

Monitors three channels:
1. Trends channel - for memecoin tracking keywords
2. Creative channel - for design/article references
3. Coin data channel - for tracking coin performance/meta analysis
"""

import discord
from discord.ext import commands
import re
import asyncio
from typing import Callable, Awaitable

from ..config import config
from ..database import ReferencesDB, TrendsDB, CoinPerformanceDB
from ..scraper import URLScraper


class DiscordBot(commands.Bot):
    """
    Discord bot that watches input channels and processes content.
    
    Completely separates:
    - Trends channel → TrendsDB (memecoin tracking)
    - Creative channel → ReferencesDB (design/content references)
    - Coin data channel → CoinPerformanceDB (meta analysis)
    """
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        
        super().__init__(command_prefix="!", intents=intents)
        
        # Initialize databases
        self.references_db = ReferencesDB()
        self.trends_db = TrendsDB()
        self.coin_db = CoinPerformanceDB()
        self.scraper = URLScraper()
        
        # Callback for when trends are added (for pump.fun monitor)
        self.on_trend_added: Callable[[dict], Awaitable[None]] = None
    
    async def on_ready(self):
        """Called when bot is connected and ready"""
        print(f"✅ Bot connected as {self.user}")
        print(f"   Watching trends channel: {config.TRENDS_INPUT_CHANNEL_ID}")
        print(f"   Watching creative channel: {config.CREATIVE_INPUT_CHANNEL_ID}")
        if config.COIN_DATA_CHANNEL_ID:
            print(f"   Watching coin data channel: {config.COIN_DATA_CHANNEL_ID}")
    
    async def on_message(self, message: discord.Message):
        """Process incoming messages"""
        # Ignore bot's own messages
        if message.author == self.user:
            return
        
        # Route to appropriate handler based on channel
        if message.channel.id == config.TRENDS_INPUT_CHANNEL_ID:
            await self._handle_trend_input(message)
        elif message.channel.id == config.CREATIVE_INPUT_CHANNEL_ID:
            await self._handle_creative_input(message)
        elif config.COIN_DATA_CHANNEL_ID and message.channel.id == config.COIN_DATA_CHANNEL_ID:
            await self._handle_coin_data_input(message)
        
        # Process commands too
        await self.process_commands(message)
    
    async def _handle_trend_input(self, message: discord.Message):
        """
        Handle messages in the trends channel.
        
        Expected formats:
        - Just a keyword: "vibe coding"
        - Keyword with description: "vibe coding — AI assisted development"
        - TikTok/Twitter link (will extract trend from it)
        """
        content = message.content.strip()
        
        if not content:
            return
        
        # Check if it's a URL
        url_match = re.search(r'https?://\S+', content)
        
        if url_match:
            # It's a link - scrape and extract trend info
            url = url_match.group(0)
            await message.add_reaction("⏳")
            
            scraped = await self.scraper.scrape(url)
            
            if scraped.success:
                # Use title as keyword, content as description
                keyword = scraped.title[:50] if scraped.title else url
                description = scraped.content[:200] if scraped.content else ""
                
                trend = self.trends_db.add_trend(
                    keyword=keyword,
                    description=description,
                    source=scraped.source
                )
                
                if "error" in trend:
                    await message.add_reaction("⚠️")
                    await message.reply(f"Already tracking: **{trend['existing']['keyword']}**", mention_author=False)
                else:
                    await message.remove_reaction("⏳", self.user)
                    await message.add_reaction("✅")
                    await message.reply(
                        f"📈 Now tracking: **{keyword}**\n> {description[:100]}..." if description else f"📈 Now tracking: **{keyword}**",
                        mention_author=False
                    )
                    
                    if self.on_trend_added:
                        await self.on_trend_added(trend)
            else:
                await message.remove_reaction("⏳", self.user)
                await message.add_reaction("❌")
                await message.reply(f"Couldn't scrape that link: {scraped.error}", mention_author=False)
        
        else:
            # Plain text - parse as keyword [— description]
            parts = re.split(r'\s*[—-]\s*', content, maxsplit=1)
            keyword = parts[0].strip()
            description = parts[1].strip() if len(parts) > 1 else ""
            
            if keyword:
                trend = self.trends_db.add_trend(
                    keyword=keyword,
                    description=description,
                    source="manual"
                )
                
                if "error" in trend:
                    await message.add_reaction("⚠️")
                    await message.reply(f"Already tracking: **{trend['existing']['keyword']}**", mention_author=False)
                else:
                    await message.add_reaction("✅")
                    response = f"📈 Now tracking: **{keyword}**"
                    if description:
                        response += f"\n> {description}"
                    await message.reply(response, mention_author=False)
                    
                    if self.on_trend_added:
                        await self.on_trend_added(trend)
    
    async def _handle_creative_input(self, message: discord.Message):
        """
        Handle messages in the creative references channel.
        
        Expected formats:
        - URL (will scrape and auto-categorize based on content)
        - URL with category: "https://... #crypto" (manual override)
        - URL with project: "https://... @projectname"
        - Image attachments
        - Context text helps with auto-categorization
        """
        content = message.content.strip()
        
        # Extract hashtag category if present (manual override)
        category_match = re.search(r'#(\w+)', content)
        category = category_match.group(1).lower() if category_match else None
        
        # Extract project tag if present
        project_match = re.search(r'@(\w+)', content)
        project = project_match.group(1) if project_match else None
        
        # Get the user's context (everything that's not a URL or tag)
        user_context = re.sub(r'https?://\S+', '', content)  # Remove URLs
        user_context = re.sub(r'[#@]\w+', '', user_context).strip()  # Remove tags
        
        # Check for URLs
        url_match = re.search(r'https?://\S+', content)
        
        if url_match:
            url = url_match.group(0)
            await message.add_reaction("⏳")
            
            scraped = await self.scraper.scrape(url)
            
            if scraped.success:
                # Auto-categorize if not specified, using user context for better detection
                if not category:
                    category = self.scraper.guess_category(scraped, user_context)
                
                # Combine scraped content with user context
                full_content = scraped.content
                if user_context:
                    full_content = f"User notes: {user_context}\n\n{scraped.content}"
                
                ref_id = self.references_db.add_reference(
                    content=full_content,
                    source_url=url,
                    category=category,
                    project=project,
                    title=scraped.title,
                    content_type=scraped.content_type
                )
                
                await message.remove_reaction("⏳", self.user)
                await message.add_reaction("✅")
                
                response = f"💾 Saved to **{category}**"
                if project:
                    response += f" (project: {project})"
                if scraped.title:
                    response += f"\n> {scraped.title[:80]}..."
                
                await message.reply(response, mention_author=False)
            else:
                await message.remove_reaction("⏳", self.user)
                await message.add_reaction("❌")
                await message.reply(f"Couldn't scrape: {scraped.error}", mention_author=False)
        
        # Handle image attachments
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("image/"):
                # Use user context to help categorize images too
                if not category and user_context:
                    # Simple keyword check for images
                    ctx_lower = user_context.lower()
                    if any(w in ctx_lower for w in ["crypto", "trading", "coin"]):
                        category = "crypto"
                    elif any(w in ctx_lower for w in ["design", "ui", "ux"]):
                        category = "design"
                    elif any(w in ctx_lower for w in ["font", "typography"]):
                        category = "fonts"
                
                # Store image reference
                ref_id = self.references_db.add_reference(
                    content=f"Image: {attachment.filename}\n{user_context or content}",
                    source_url=attachment.url,
                    category=category or "design",
                    project=project,
                    title=attachment.filename,
                    content_type="image"
                )
                
                await message.add_reaction("🖼️")
                await message.reply(
                    f"🖼️ Image saved to **{category or 'design'}**" + (f" (project: {project})" if project else ""),
                    mention_author=False
                )
    
    async def _handle_coin_data_input(self, message: discord.Message):
        """
        Handle messages in the coin data channel for meta analysis.
        
        Expected formats:
        - Simple: COINNAME | narrative | peak | time | notes/URL
        - Detailed:
            $COINNAME
            meta: ai_agents
            peak: 500M
            time: 3 days
            notes: context here OR https://x.com/...
        
        If a URL is included, it will be scraped for context.
        """
        content = message.content.strip()
        
        if not content:
            return
        
        # Try to parse the input
        coin_data = self._parse_coin_data(content)
        
        if not coin_data:
            await message.add_reaction("❓")
            await message.reply(
                "**Format help:**\n"
                "`COINNAME | narrative | peak_mcap | time_to_peak | notes/URL`\n"
                "Example: `FARTCOIN | ai_agents | 500M | 3 days | https://x.com/...`\n\n"
                "Or detailed format:\n"
                "```\n$COINNAME\nmeta: ai_agents\npeak: 500M\ntime: 3 days\nnotes: https://x.com/...```\n\n"
                "**Twitter links will be scraped for full context!**",
                mention_author=False
            )
            return
        
        # Check if notes contains a URL - if so, scrape it
        notes = coin_data.get("notes", "")
        url_match = re.search(r'https?://\S+', notes)
        
        if url_match:
            url = url_match.group(0)
            await message.add_reaction("⏳")
            
            # Scrape the URL for context
            scraped = await self.scraper.scrape(url)
            
            if scraped.success and scraped.content:
                # Combine URL with scraped content
                coin_data["notes"] = f"Source: {url}\n\n{scraped.content}"
                await message.remove_reaction("⏳", self.user)
            else:
                await message.remove_reaction("⏳", self.user)
                # Keep original notes if scraping failed
        
        # Add to database
        try:
            coin = self.coin_db.add_coin(**coin_data)
            
            await message.add_reaction("📊")
            
            # Get updated analysis for this narrative
            analysis = self.coin_db.get_narrative_summary(coin_data["narrative"])
            
            # Show preview of scraped content if we got it
            notes_preview = ""
            if coin_data.get("notes") and len(coin_data["notes"]) > 50:
                notes_preview = f"\n📝 Context: {coin_data['notes'][:150]}..."
            
            response = (
                f"📊 Recorded: **{coin['name']}**\n"
                f"• Narrative: {coin['narrative'].replace('_', ' ').title()}\n"
                f"• Peak: {coin['peak_mcap']}\n"
                f"• Time to peak: {coin['time_to_peak']}"
                f"{notes_preview}\n\n"
                f"{analysis}"
            )
            
            await message.reply(response, mention_author=False)
            
        except Exception as e:
            await message.add_reaction("❌")
            await message.reply(f"Error recording coin: {str(e)}", mention_author=False)
    
    def _parse_coin_data(self, content: str) -> dict | None:
        """Parse coin data from user input"""
        
        # Try pipe-separated format: NAME | narrative | peak | time | notes
        if "|" in content:
            parts = [p.strip() for p in content.split("|")]
            if len(parts) >= 4:
                return {
                    "name": parts[0].replace("$", ""),
                    "narrative": parts[1],
                    "peak_mcap": parts[2],
                    "time_to_peak": parts[3],
                    "notes": parts[4] if len(parts) > 4 else ""
                }
        
        # Try detailed format with labels
        lines = content.strip().split("\n")
        data = {}
        
        for line in lines:
            line = line.strip()
            
            # First line might be coin name
            if line.startswith("$") or (not ":" in line and not data.get("name")):
                data["name"] = line.replace("$", "").strip()
                continue
            
            # Parse key: value pairs
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key in ["meta", "narrative", "category"]:
                    data["narrative"] = value
                elif key in ["peak", "peak_mcap", "mcap", "market cap"]:
                    data["peak_mcap"] = value
                elif key in ["time", "time_to_peak", "duration"]:
                    data["time_to_peak"] = value
                elif key in ["notes", "note", "context"]:
                    data["notes"] = value
                elif key in ["entry", "entry_mcap"]:
                    data["entry_mcap"] = value
                elif key in ["exit", "exit_mcap"]:
                    data["exit_mcap"] = value
        
        # Validate required fields
        if data.get("name") and data.get("narrative") and data.get("peak_mcap") and data.get("time_to_peak"):
            return data
        
        return None
    
    async def setup_hook(self):
        """Add slash commands"""
        
        @self.tree.command(name="trends", description="List all tracked trends")
        async def list_trends(interaction: discord.Interaction):
            trends = self.trends_db.get_all_trends()
            
            if not trends:
                await interaction.response.send_message("No trends being tracked yet!")
                return
            
            response = "**📈 Tracked Trends:**\n"
            for t in trends[:20]:  # Limit to 20
                status = "🔥" if t["priority"] >= 4 else "📊" if t["priority"] >= 2 else "📌"
                response += f"{status} **{t['keyword']}**"
                if t.get("description"):
                    response += f" — {t['description'][:50]}..."
                response += f" (matches: {t.get('match_count', 0)})\n"
            
            await interaction.response.send_message(response)
        
        @self.tree.command(name="refs", description="Search creative references")
        async def search_refs(interaction: discord.Interaction, query: str, category: str = None):
            results = self.references_db.search(query, category=category, limit=5)
            
            if not results:
                await interaction.response.send_message(f"No references found for '{query}'")
                return
            
            response = f"**🔍 References for '{query}':**\n\n"
            for ref in results:
                meta = ref["metadata"]
                response += f"**{meta.get('title', 'Untitled')[:50]}**\n"
                response += f"Category: {meta.get('category')} | Type: {meta.get('content_type')}\n"
                if meta.get("source_url"):
                    response += f"Source: {meta['source_url'][:50]}...\n"
                response += f"> {ref['content'][:100]}...\n\n"
            
            await interaction.response.send_message(response)
        
        @self.tree.command(name="remove_trend", description="Remove a trend from tracking")
        async def remove_trend(interaction: discord.Interaction, keyword: str):
            trends = self.trends_db.search_trends(keyword)
            
            if not trends:
                await interaction.response.send_message(f"No trend found matching '{keyword}'")
                return
            
            trend = trends[0]
            self.trends_db.delete_trend(trend["id"])
            await interaction.response.send_message(f"🗑️ Removed trend: **{trend['keyword']}**")
        
        @self.tree.command(name="meta", description="View meta analysis for coin narratives")
        async def meta_analysis(interaction: discord.Interaction, narrative: str = None):
            if narrative:
                summary = self.coin_db.get_narrative_summary(narrative)
                await interaction.response.send_message(summary)
            else:
                summary = self.coin_db.get_overall_summary()
                await interaction.response.send_message(summary)
        
        @self.tree.command(name="coins", description="List recorded coins")
        async def list_coins(interaction: discord.Interaction, narrative: str = None):
            coins = self.coin_db.get_all_coins(narrative=narrative)
            
            if not coins:
                await interaction.response.send_message(
                    f"No coins recorded" + (f" for '{narrative}'" if narrative else "") + " yet!"
                )
                return
            
            response = f"**📊 Recorded Coins" + (f" ({narrative})" if narrative else "") + ":**\n\n"
            for c in coins[:15]:  # Limit to 15
                response += (
                    f"**{c['name']}** ({c['narrative'].replace('_', ' ')})\n"
                    f"Peak: {c['peak_mcap']} in {c['time_to_peak']}\n"
                )
                if c.get('notes'):
                    response += f"> {c['notes'][:50]}...\n"
                response += "\n"
            
            await interaction.response.send_message(response)
        
        @self.tree.command(name="categories", description="List all reference categories in use")
        async def list_categories(interaction: discord.Interaction):
            categories = self.references_db.get_categories()
            
            if not categories:
                await interaction.response.send_message("No categories in use yet!")
                return
            
            response = "**📁 Categories in use:**\n" + "\n".join(f"• {cat}" for cat in categories)
            await interaction.response.send_message(response)
        
        # Sync commands
        await self.tree.sync()


