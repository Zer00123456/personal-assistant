"""
URL Scraper - Extracts content from URLs

Handles articles, tweets, and general web pages.
Uses trafilatura for clean article extraction.
"""

import re
import aiohttp
from bs4 import BeautifulSoup
import trafilatura
from typing import Optional
from dataclasses import dataclass


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
        
        # Twitter/X and TikTok have aggressive anti-scraping - store URL directly
        if source in ["twitter", "tiktok"]:
            return self._store_social_url(url, source, content_type)
        
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
    
    def _store_social_url(self, url: str, source: str, content_type: str) -> ScrapedContent:
        """
        Store social media URLs without scraping.
        Twitter/X and TikTok block scrapers aggressively.
        """
        # Extract username and post ID from URL
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
    
    def guess_category(self, content: ScrapedContent) -> str:
        """
        Attempt to auto-categorize based on content and source.
        
        Returns one of the standard categories.
        """
        # Source-based categorization
        if content.source in ["twitter", "x"]:
            return "twitter"
        if content.source in ["dribbble", "behance", "figma"]:
            return "design"
        
        # Content-based categorization
        text = (content.title + " " + content.content).lower()
        
        if any(word in text for word in ["font", "typography", "typeface"]):
            return "fonts"
        if any(word in text for word in ["color", "colour", "palette"]):
            return "colors"
        if any(word in text for word in ["landing page", "homepage", "hero section"]):
            return "landing_pages"
        if any(word in text for word in ["logo", "brand", "branding"]):
            return "logos"
        if any(word in text for word in ["thumbnail", "cover image"]):
            return "thumbnails"
        if content.content_type == "design":
            return "design"
        
        # Default to copywriting for text-heavy content
        if len(content.content) > 500:
            return "copywriting"
        
        return "uncategorized"


