"""
Discord Bot - Watches input channels and processes content

Monitors two separate channels:
1. Trends channel - for memecoin tracking keywords
2. Creative channel - for design/article references
"""

import discord
from discord.ext import commands
import re
import asyncio
from typing import Callable, Awaitable

from ..config import config
from ..database import ReferencesDB, TrendsDB
from ..scraper import URLScraper


class DiscordBot(commands.Bot):
    """
    Discord bot that watches input channels and processes content.
    
    Completely separates:
    - Trends channel → TrendsDB (memecoin tracking)
    - Creative channel → ReferencesDB (design/content references)
    """
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        
        super().__init__(command_prefix="!", intents=intents)
        
        # Initialize databases
        self.references_db = ReferencesDB()
        self.trends_db = TrendsDB()
        self.scraper = URLScraper()
        
        # Callback for when trends are added (for pump.fun monitor)
        self.on_trend_added: Callable[[dict], Awaitable[None]] = None
    
    async def on_ready(self):
        """Called when bot is connected and ready"""
        print(f"✅ Bot connected as {self.user}")
        print(f"   Watching trends channel: {config.TRENDS_INPUT_CHANNEL_ID}")
        print(f"   Watching creative channel: {config.CREATIVE_INPUT_CHANNEL_ID}")
    
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
        - URL (will scrape and auto-categorize)
        - URL with category: "https://... #design"
        - URL with project: "https://... @projectname"
        - Image attachments
        """
        content = message.content.strip()
        
        # Extract hashtag category if present
        category_match = re.search(r'#(\w+)', content)
        category = category_match.group(1).lower() if category_match else None
        
        # Extract project tag if present
        project_match = re.search(r'@(\w+)', content)
        project = project_match.group(1) if project_match else None
        
        # Check for URLs
        url_match = re.search(r'https?://\S+', content)
        
        if url_match:
            url = url_match.group(0)
            await message.add_reaction("⏳")
            
            scraped = await self.scraper.scrape(url)
            
            if scraped.success:
                # Auto-categorize if not specified
                if not category:
                    category = self.scraper.guess_category(scraped)
                
                ref_id = self.references_db.add_reference(
                    content=scraped.content,
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
                response += f"\n> {scraped.title[:80]}..." if scraped.title else ""
                
                await message.reply(response, mention_author=False)
            else:
                await message.remove_reaction("⏳", self.user)
                await message.add_reaction("❌")
                await message.reply(f"Couldn't scrape: {scraped.error}", mention_author=False)
        
        # Handle image attachments
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith("image/"):
                # Store image reference
                ref_id = self.references_db.add_reference(
                    content=f"Image: {attachment.filename}\n{content}",
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
        
        # Sync commands
        await self.tree.sync()


