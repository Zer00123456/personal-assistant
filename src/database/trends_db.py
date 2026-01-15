"""
Trends Database for Memecoin Tracking

Stores trends/keywords to match against graduating pump.fun coins.
Completely separate from the creative references system.
"""

import json
import os
from datetime import datetime
from typing import Optional
from ..config import config


class TrendsDB:
    """
    Simple JSON-based database for tracking trends.
    
    Stores keywords/phrases to match against graduating coins.
    Supports descriptions and metadata for context.
    """
    
    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or config.CHROMA_PERSIST_DIR
        self.db_path = os.path.join(self.persist_dir, "trends.json")
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Create the database file if it doesn't exist"""
        os.makedirs(self.persist_dir, exist_ok=True)
        if not os.path.exists(self.db_path):
            self._save_db({"trends": [], "matched_coins": []})
    
    def _load_db(self) -> dict:
        """Load the database from disk"""
        with open(self.db_path, "r") as f:
            return json.load(f)
    
    def _save_db(self, data: dict):
        """Save the database to disk"""
        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def add_trend(
        self,
        keyword: str,
        description: str = None,
        source: str = None,  # e.g., "twitter", "tiktok", "manual"
        aliases: list[str] = None,  # Alternative spellings/variations
        priority: int = 1  # 1-5, higher = more important
    ) -> dict:
        """
        Add a new trend to track.
        
        Args:
            keyword: Main keyword/phrase to match
            description: Context about this trend
            source: Where you found this trend
            aliases: Alternative ways this might appear
            priority: How important is this trend (1-5)
            
        Returns:
            The created trend object
        """
        db = self._load_db()
        
        # Check for duplicates
        for trend in db["trends"]:
            if trend["keyword"].lower() == keyword.lower():
                return {"error": f"Trend '{keyword}' already exists", "existing": trend}
        
        trend = {
            "id": len(db["trends"]) + 1,
            "keyword": keyword,
            "description": description or "",
            "source": source or "manual",
            "aliases": aliases or [],
            "priority": min(max(priority, 1), 5),
            "created_at": datetime.now().isoformat(),
            "active": True,
            "match_count": 0
        }
        
        db["trends"].append(trend)
        self._save_db(db)
        
        return trend
    
    def get_all_trends(self, active_only: bool = True) -> list[dict]:
        """Get all tracked trends"""
        db = self._load_db()
        trends = db["trends"]
        
        if active_only:
            trends = [t for t in trends if t.get("active", True)]
        
        return sorted(trends, key=lambda x: -x.get("priority", 1))
    
    def get_trend(self, trend_id: int) -> Optional[dict]:
        """Get a specific trend by ID"""
        db = self._load_db()
        for trend in db["trends"]:
            if trend["id"] == trend_id:
                return trend
        return None
    
    def update_trend(self, trend_id: int, **kwargs) -> Optional[dict]:
        """Update a trend"""
        db = self._load_db()
        for i, trend in enumerate(db["trends"]):
            if trend["id"] == trend_id:
                for key, value in kwargs.items():
                    if key in trend:
                        trend[key] = value
                trend["updated_at"] = datetime.now().isoformat()
                db["trends"][i] = trend
                self._save_db(db)
                return trend
        return None
    
    def deactivate_trend(self, trend_id: int) -> bool:
        """Deactivate a trend (soft delete)"""
        result = self.update_trend(trend_id, active=False)
        return result is not None
    
    def delete_trend(self, trend_id: int) -> bool:
        """Permanently delete a trend"""
        db = self._load_db()
        original_len = len(db["trends"])
        db["trends"] = [t for t in db["trends"] if t["id"] != trend_id]
        if len(db["trends"]) < original_len:
            self._save_db(db)
            return True
        return False
    
    def get_all_keywords(self) -> list[str]:
        """
        Get all keywords and aliases as a flat list.
        Used for matching against coin names.
        """
        keywords = []
        for trend in self.get_all_trends(active_only=True):
            keywords.append(trend["keyword"])
            keywords.extend(trend.get("aliases", []))
        return keywords
    
    def get_keyword_to_trend_map(self) -> dict[str, dict]:
        """
        Get a mapping of keywords/aliases to their parent trend.
        Used for identifying which trend matched.
        """
        mapping = {}
        for trend in self.get_all_trends(active_only=True):
            mapping[trend["keyword"].lower()] = trend
            for alias in trend.get("aliases", []):
                mapping[alias.lower()] = trend
        return mapping
    
    def record_match(
        self,
        trend_id: int,
        coin_name: str,
        coin_address: str = None,
        matched_keyword: str = None
    ) -> dict:
        """
        Record when a coin matches a trend.
        
        Returns the match record.
        """
        db = self._load_db()
        
        # Update match count on trend
        for trend in db["trends"]:
            if trend["id"] == trend_id:
                trend["match_count"] = trend.get("match_count", 0) + 1
                break
        
        # Record the match
        match_record = {
            "trend_id": trend_id,
            "coin_name": coin_name,
            "coin_address": coin_address or "",
            "matched_keyword": matched_keyword or "",
            "matched_at": datetime.now().isoformat()
        }
        
        db["matched_coins"].append(match_record)
        self._save_db(db)
        
        return match_record
    
    def get_recent_matches(self, limit: int = 20) -> list[dict]:
        """Get recent coin matches"""
        db = self._load_db()
        matches = db.get("matched_coins", [])
        return sorted(matches, key=lambda x: x["matched_at"], reverse=True)[:limit]
    
    def search_trends(self, query: str) -> list[dict]:
        """Search trends by keyword or description"""
        query_lower = query.lower()
        results = []
        
        for trend in self.get_all_trends(active_only=False):
            if (query_lower in trend["keyword"].lower() or
                query_lower in trend.get("description", "").lower() or
                any(query_lower in alias.lower() for alias in trend.get("aliases", []))):
                results.append(trend)
        
        return results


