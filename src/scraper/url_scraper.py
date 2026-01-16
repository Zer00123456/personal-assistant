"""
URL Scraper - Extracts content from URLs

Handles articles, tweets, and general web pages.
Uses trafilatura for clean article extraction.
Uses Twitter API v2 for tweet scraping.
"""

import re
import aiohttp
from bs4 import BeautifulSoup
import trafilatura
from typing import Optional
from dataclasses import dataclass

from ..config import config

# Twitter API v2 endpoint
TWITTER_API_URL = "https://api.twitter.com/2/tweets"


@dataclass
class ScrapedContent:
    """Result of scraping a URL"""
    url: str
    title: str
    content: str
    content_type: str  # article, tweet, image, design, unknown
    source: str  # twitter, medium, substack, etc.
    images: list[str]
    success: bool
    error: str = None


class URLScraper:
    """Scrapes content from URLs for storage in the reference database"""
    
    # Common sources and their types
    SOURCE_PATTERNS = {
        r"twitter\.com|x\.com": ("twitter", "tweet"),
        r"medium\.com": ("medium", "article"),
        r"substack\.com": ("substack", "article"),
        r"dribbble\.com": ("dribbble", "design"),
        r"behance\.net": ("behance", "design"),
        r"figma\.com": ("figma", "design"),
        r"pinterest\.com": ("pinterest", "image"),
        r"tiktok\.com": ("tiktok", "video"),
    }
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
    
    async def scrape(self, url: str) -> ScrapedContent:
        """
        Scrape content from a URL.
        
        Automatically detects the type of content and extracts appropriately.
        """
        source, content_type = self._detect_source(url)
        
        # Twitter/X - try RapidAPI first, then official API, then Nitter
        if source == "twitter":
            if config.RAPIDAPI_KEY:
                return await self._scrape_twitter_via_rapidapi(url)
            elif config.TWITTER_BEARER_TOKEN:
                return await self._scrape_twitter_via_api(url)
            else:
                return await self._scrape_twitter_via_nitter(url)
        
        # TikTok - just store URL (no good scraping option)
        if source == "tiktok":
            return self._store_social_url_fallback(url, source, content_type)
        
        try:
            # Create connector with larger header limits for problematic sites
            connector = aiohttp.TCPConnector(force_close=True)
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(
                headers=self.headers,
                connector=connector,
                timeout=timeout
            ) as session:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status != 200:
                        return ScrapedContent(
                            url=url,
                            title="",
                            content="",
                            content_type="unknown",
                            source=source,
                            images=[],
                            success=False,
                            error=f"HTTP {response.status}"
                        )
                    
                    html = await response.text()
        except Exception as e:
            # If scraping fails, still store the URL as a reference
            return ScrapedContent(
                url=url,
                title=f"Reference from {source}",
                content=f"URL saved: {url}",
                content_type=content_type,
                source=source,
                images=[],
                success=True,  # Still mark as success - we saved the URL
                error=None
            )
        
        # Route to appropriate extractor
        if content_type == "design":
            return await self._extract_design(url, html, source)
        else:
            return await self._extract_article(url, html, source)
    
    async def _scrape_twitter_via_rapidapi(self, url: str) -> ScrapedContent:
        """
        Scrape Twitter/X content via Twttr API on RapidAPI.
        Much cheaper than official Twitter API.
        """
        # Extract tweet ID from URL
        twitter_match = re.search(r'(?:twitter|x)\.com/(\w+)/status/(\d+)', url)
        if not twitter_match:
            return self._store_social_url_fallback(url, "twitter", "tweet")
        
        username = twitter_match.group(1)
        tweet_id = twitter_match.group(2)
        
        try:
            headers = {
                "X-RapidAPI-Key": config.RAPIDAPI_KEY,
                "X-RapidAPI-Host": "twttr.p.rapidapi.com"
            }
            
            # Twttr API endpoint for getting tweet details
            api_url = f"https://twttr.p.rapidapi.com/get-tweet?id={tweet_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract tweet data from response
                        # Twttr API structure varies, handle common formats
                        tweet_text = ""
                        author_name = username
                        
                        if "data" in data:
                            tweet_data = data["data"]
                            tweet_text = tweet_data.get("text", "")
                            
                            # Get author info if available
                            if "user" in tweet_data:
                                user = tweet_data["user"]
                                author_name = f"{user.get('name', username)} (@{user.get('screen_name', username)})"
                            elif "author" in tweet_data:
                                author = tweet_data["author"]
                                author_name = f"{author.get('name', username)} (@{author.get('username', username)})"
                        
                        elif "tweet" in data:
                            tweet_data = data["tweet"]
                            tweet_text = tweet_data.get("full_text", tweet_data.get("text", ""))
                            if "user" in tweet_data:
                                user = tweet_data["user"]
                                author_name = f"{user.get('name', username)} (@{user.get('screen_name', username)})"
                        
                        elif "full_text" in data:
                            tweet_text = data["full_text"]
                        
                        elif "text" in data:
                            tweet_text = data["text"]
                        
                        if tweet_text:
                            return ScrapedContent(
                                url=url,
                                title=f"Tweet by {author_name}",
                                content=tweet_text,
                                content_type="tweet",
                                source="twitter",
                                images=[],
                                success=True
                            )
                    
                    elif response.status == 429:
                        print("RapidAPI rate limited")
                    else:
                        error_text = await response.text()
                        print(f"RapidAPI error {response.status}: {error_text[:200]}")
        
        except Exception as e:
            print(f"RapidAPI exception: {e}")
        
        # Fallback to official API or Nitter
        if config.TWITTER_BEARER_TOKEN:
            return await self._scrape_twitter_via_api(url)
        return await self._scrape_twitter_via_nitter(url)
    
    async def _scrape_twitter_via_api(self, url: str) -> ScrapedContent:
        """
        Scrape Twitter/X content via official Twitter API v2.
        Requires TWITTER_BEARER_TOKEN in config.
        """
        # Extract tweet ID from URL
        twitter_match = re.search(r'(?:twitter|x)\.com/(\w+)/status/(\d+)', url)
        if not twitter_match:
            return self._store_social_url_fallback(url, "twitter", "tweet")
        
        username = twitter_match.group(1)
        tweet_id = twitter_match.group(2)
        
        try:
            headers = {
                "Authorization": f"Bearer {config.TWITTER_BEARER_TOKEN}",
                "User-Agent": "v2TweetLookupPython"
            }
            
            # Request tweet with expanded author info
            params = {
                "ids": tweet_id,
                "tweet.fields": "text,author_id,created_at,public_metrics",
                "expansions": "author_id",
                "user.fields": "name,username"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    TWITTER_API_URL,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if "data" in data and len(data["data"]) > 0:
                            tweet = data["data"][0]
                            tweet_text = tweet.get("text", "")
                            
                            # Get author info
                            author_name = username
                            if "includes" in data and "users" in data["includes"]:
                                user = data["includes"]["users"][0]
                                author_name = f"{user.get('name', username)} (@{user.get('username', username)})"
                            
                            # Get metrics if available
                            metrics = tweet.get("public_metrics", {})
                            metrics_str = ""
                            if metrics:
                                metrics_str = f"\n\nEngagement: {metrics.get('like_count', 0)} likes, {metrics.get('retweet_count', 0)} RTs, {metrics.get('reply_count', 0)} replies"
                            
                            return ScrapedContent(
                                url=url,
                                title=f"Tweet by {author_name}",
                                content=f"{tweet_text}{metrics_str}",
                                content_type="tweet",
                                source="twitter",
                                images=[],
                                success=True
                            )
                    
                    elif response.status == 429:
                        # Rate limited - fallback to URL only
                        return ScrapedContent(
                            url=url,
                            title=f"Tweet by @{username}",
                            content=f"Twitter API rate limited. URL: {url}",
                            content_type="tweet",
                            source="twitter",
                            images=[],
                            success=True,
                            error="Rate limited"
                        )
                    else:
                        error_text = await response.text()
                        print(f"Twitter API error {response.status}: {error_text[:200]}")
        
        except Exception as e:
            print(f"Twitter API exception: {e}")
        
        # Fallback to Nitter if API fails
        return await self._scrape_twitter_via_nitter(url)
    
    async def _scrape_twitter_via_nitter(self, url: str) -> ScrapedContent:
        """
        Scrape Twitter/X content via Nitter instances.
        Nitter is an open-source Twitter frontend that's easier to scrape.
        """
        # Extract tweet ID and username
        twitter_match = re.search(r'(?:twitter|x)\.com/(\w+)/status/(\d+)', url)
        if not twitter_match:
            return self._store_social_url_fallback(url, "twitter", "tweet")
        
        username = twitter_match.group(1)
        tweet_id = twitter_match.group(2)
        
        # List of Nitter instances to try
        nitter_instances = [
            "nitter.privacydev.net",
            "nitter.poast.org", 
            "nitter.woodland.cafe",
            "nitter.1d4.us",
        ]
        
        for instance in nitter_instances:
            nitter_url = f"https://{instance}/{username}/status/{tweet_id}"
            
            try:
                connector = aiohttp.TCPConnector(force_close=True)
                timeout = aiohttp.ClientTimeout(total=15)
                
                async with aiohttp.ClientSession(
                    headers=self.headers,
                    connector=connector,
                    timeout=timeout
                ) as session:
                    async with session.get(nitter_url, allow_redirects=True) as response:
                        if response.status != 200:
                            continue
                        
                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")
                        
                        # Extract tweet content
                        tweet_content = ""
                        content_div = soup.find("div", class_="tweet-content")
                        if content_div:
                            tweet_content = content_div.get_text(strip=True)
                        
                        # Extract username/display name
                        fullname = soup.find("a", class_="fullname")
                        display_name = fullname.get_text(strip=True) if fullname else username
                        
                        # Extract images if any
                        images = []
                        for img in soup.find_all("img", class_="still-image"):
                            src = img.get("src", "")
                            if src:
                                images.append(f"https://{instance}{src}" if src.startswith("/") else src)
                        
                        if tweet_content:
                            return ScrapedContent(
                                url=url,
                                title=f"Tweet by @{username} ({display_name})",
                                content=tweet_content,
                                content_type="tweet",
                                source="twitter",
                                images=images,
                                success=True
                            )
            except Exception:
                continue
        
        # Fallback if all Nitter instances fail
        return self._store_social_url_fallback(url, "twitter", "tweet")
    
    def _store_social_url_fallback(self, url: str, source: str, content_type: str) -> ScrapedContent:
        """
        Fallback: Store social media URLs without full scraping.
        Used when Nitter scraping fails.
        """
        title = f"Post from {source.capitalize()}"
        content = f"Saved reference: {url}"
        
        # Try to extract username from Twitter/X URL
        twitter_match = re.search(r'(?:twitter|x)\.com/(\w+)/status/(\d+)', url)
        if twitter_match:
            username = twitter_match.group(1)
            title = f"Tweet by @{username}"
            content = f"Twitter/X post by @{username}\nURL: {url}"
        
        # Try to extract from TikTok URL
        tiktok_match = re.search(r'tiktok\.com/@(\w+)', url)
        if tiktok_match:
            username = tiktok_match.group(1)
            title = f"TikTok by @{username}"
            content = f"TikTok post by @{username}\nURL: {url}"
        
        return ScrapedContent(
            url=url,
            title=title,
            content=content,
            content_type=content_type,
            source=source,
            images=[],
            success=True
        )
    
    def _detect_source(self, url: str) -> tuple[str, str]:
        """Detect the source platform and expected content type"""
        for pattern, (source, content_type) in self.SOURCE_PATTERNS.items():
            if re.search(pattern, url, re.IGNORECASE):
                return source, content_type
        return "web", "article"
    
    async def _extract_article(self, url: str, html: str, source: str) -> ScrapedContent:
        """Extract article content using trafilatura"""
        # Try trafilatura first (best for articles)
        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            no_fallback=False
        )
        
        # Fallback to BeautifulSoup if trafilatura fails
        soup = BeautifulSoup(html, "html.parser")
        
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text().strip()
        
        # Also try og:title
        og_title = soup.find("meta", property="og:title")
        if og_title:
            title = og_title.get("content", title)
        
        # Extract images
        images = []
        for img in soup.find_all("img", src=True)[:10]:  # Limit to 10 images
            src = img["src"]
            if src.startswith("http"):
                images.append(src)
        
        if not content:
            # Fallback: get all paragraph text
            paragraphs = soup.find_all("p")
            content = "\n\n".join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
        
        return ScrapedContent(
            url=url,
            title=title,
            content=content or "",
            content_type="article",
            source=source,
            images=images,
            success=bool(content)
        )
    
    async def _extract_tweet(self, url: str, html: str, source: str) -> ScrapedContent:
        """
        Extract tweet content.
        
        Note: Twitter/X requires authentication for full access.
        This extracts what's available from the public page.
        """
        soup = BeautifulSoup(html, "html.parser")
        
        title = ""
        content = ""
        
        # Try meta tags (usually contain tweet text)
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            content = og_desc.get("content", "")
        
        og_title = soup.find("meta", property="og:title")
        if og_title:
            title = og_title.get("content", "")
        
        # Extract images
        images = []
        og_image = soup.find("meta", property="og:image")
        if og_image:
            images.append(og_image.get("content", ""))
        
        return ScrapedContent(
            url=url,
            title=title,
            content=content,
            content_type="tweet",
            source=source,
            images=images,
            success=bool(content)
        )
    
    async def _extract_design(self, url: str, html: str, source: str) -> ScrapedContent:
        """Extract design content (images + descriptions)"""
        soup = BeautifulSoup(html, "html.parser")
        
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text().strip()
        
        # Get description
        description = ""
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            description = og_desc.get("content", "")
        
        # Extract images
        images = []
        
        # Try og:image first
        og_image = soup.find("meta", property="og:image")
        if og_image:
            images.append(og_image.get("content", ""))
        
        # Then regular images
        for img in soup.find_all("img", src=True)[:10]:
            src = img["src"]
            if src.startswith("http") and src not in images:
                images.append(src)
        
        return ScrapedContent(
            url=url,
            title=title,
            content=description,
            content_type="design",
            source=source,
            images=images,
            success=bool(images)
        )
    
    def guess_category(self, content: ScrapedContent, user_message: str = "") -> str:
        """
        Attempt to auto-categorize based on content and source.
        Uses keyword detection to identify topic areas.
        
        Returns one of the standard categories.
        """
        # Combine all text for analysis
        text = (content.title + " " + content.content + " " + user_message).lower()
        
        # Category keywords - ordered by priority (first match wins)
        # More specific categories first, then broader ones
        CATEGORY_KEYWORDS = {
            # Topic-based categories (content focus)
            "crypto": [
                "crypto", "bitcoin", "ethereum", "solana", "trading", "defi", 
                "blockchain", "web3", "token", "coin", "memecoin", "degen",
                "onchain", "on-chain", "wallet", "swap", "liquidity", "market cap",
                "bull", "bear", "pump", "dump", "airdrop", "yield"
            ],
            "marketing": [
                "marketing", "growth", "acquisition", "conversion", "funnel",
                "campaign", "audience", "viral", "engagement", "retention",
                "ctr", "roi", "ads", "advertising", "promotion"
            ],
            "content_systems": [
                "content system", "content strategy", "content creation", "workflow",
                "repurpose", "distribution", "content machine", "content engine",
                "editorial", "publishing", "content calendar"
            ],
            "copywriting": [
                "copywriting", "copy", "headline", "hook", "persuasion", "cta",
                "call to action", "sales page", "landing page copy", "email copy",
                "storytelling", "narrative", "writing"
            ],
            "twitter": [
                "twitter", "tweet", "thread", "x.com", "followers", "viral tweet"
            ],
            
            # Design-focused categories
            "landing_pages": [
                "landing page", "homepage", "hero section", "above the fold",
                "conversion page", "squeeze page", "sales page design"
            ],
            "design": [
                "design", "ui", "ux", "interface", "layout", "visual", 
                "aesthetic", "mockup", "wireframe", "figma", "sketch"
            ],
            "fonts": [
                "font", "typography", "typeface", "lettering", "sans-serif",
                "serif", "display font", "font pairing"
            ],
            "colors": [
                "color", "colour", "palette", "gradient", "scheme", "hex",
                "rgb", "hue", "saturation"
            ],
            "logos": [
                "logo", "brand identity", "brandmark", "wordmark", "icon design"
            ],
            "thumbnails": [
                "thumbnail", "cover image", "featured image", "youtube thumbnail"
            ],
            
            # Broader categories
            "ai": [
                "ai", "artificial intelligence", "machine learning", "gpt", 
                "claude", "llm", "prompt", "automation", "chatbot"
            ],
            "productivity": [
                "productivity", "efficiency", "workflow", "system", "process",
                "automation", "template", "framework"
            ],
            "business": [
                "business", "startup", "entrepreneur", "founder", "revenue",
                "profit", "scale", "growth"
            ],
        }
        
        # Check each category's keywords
        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return category
        
        # Source-based fallback
        if content.source in ["dribbble", "behance", "figma"]:
            return "design"
        
        # Content type fallback
        if content.content_type == "design":
            return "design"
        
        # Default to copywriting for text-heavy content
        if len(content.content) > 500:
            return "copywriting"
        
        return "uncategorized"


