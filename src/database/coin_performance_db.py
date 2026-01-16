"""
Coin Performance Database - Track historical coin performance for meta analysis

Stores data about coins to establish:
- Market cap ceilings for different narratives
- Time to peak patterns
- What performs well in current meta
"""

import json
import os
from datetime import datetime
from typing import Optional
from ..config import config


class CoinPerformanceDB:
    """
    Database for tracking coin performance data.
    
    Helps establish patterns like:
    - "AI agent coins typically ceiling at $200-800M"
    - "Animal coins peak within 48 hours"
    - "Hold time for narrative X should be ~3 days"
    """
    
    # Common narrative/meta categories
    NARRATIVES = [
        "ai_agents",
        "animal",
        "celebrity",
        "political",
        "gaming",
        "defi",
        "meme_culture",
        "tech",
        "viral_moment",
        "influencer",
        "other"
    ]
    
    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or config.CHROMA_PERSIST_DIR
        self.db_path = os.path.join(self.persist_dir, "coin_performance.json")
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Create the database file if it doesn't exist"""
        os.makedirs(self.persist_dir, exist_ok=True)
        if not os.path.exists(self.db_path):
            self._save_db({"coins": [], "meta_analysis": {}})
    
    def _load_db(self) -> dict:
        """Load the database from disk"""
        with open(self.db_path, "r") as f:
            return json.load(f)
    
    def _save_db(self, data: dict):
        """Save the database to disk"""
        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def add_coin(
        self,
        name: str,
        narrative: str,
        peak_mcap: str,  # e.g., "500M", "1.2B", "50K"
        time_to_peak: str,  # e.g., "3 days", "12 hours", "1 week"
        notes: str = None,
        coin_address: str = None,
        entry_mcap: str = None,
        exit_mcap: str = None
    ) -> dict:
        """
        Add a coin performance record.
        
        Args:
            name: Coin name/ticker
            narrative: Meta category (ai_agents, animal, celebrity, etc.)
            peak_mcap: Peak market cap reached
            time_to_peak: How long to reach peak
            notes: Additional context/observations
            coin_address: Solana address if known
            entry_mcap: Your entry market cap (optional)
            exit_mcap: Your exit market cap (optional)
            
        Returns:
            The created coin record
        """
        db = self._load_db()
        
        # Parse market cap to numeric for analysis
        peak_mcap_numeric = self._parse_mcap(peak_mcap)
        time_to_peak_hours = self._parse_time_to_hours(time_to_peak)
        
        coin = {
            "id": len(db["coins"]) + 1,
            "name": name.upper(),
            "narrative": narrative.lower().replace(" ", "_"),
            "peak_mcap": peak_mcap,
            "peak_mcap_numeric": peak_mcap_numeric,
            "time_to_peak": time_to_peak,
            "time_to_peak_hours": time_to_peak_hours,
            "notes": notes or "",
            "coin_address": coin_address or "",
            "entry_mcap": entry_mcap or "",
            "exit_mcap": exit_mcap or "",
            "recorded_at": datetime.now().isoformat(),
        }
        
        db["coins"].append(coin)
        self._save_db(db)
        
        # Update meta analysis
        self._update_meta_analysis()
        
        return coin
    
    def _parse_mcap(self, mcap_str: str) -> float:
        """Parse market cap string to numeric value in USD"""
        mcap_str = mcap_str.upper().replace("$", "").replace(",", "").strip()
        
        multipliers = {
            "K": 1_000,
            "M": 1_000_000,
            "B": 1_000_000_000,
        }
        
        for suffix, mult in multipliers.items():
            if suffix in mcap_str:
                try:
                    return float(mcap_str.replace(suffix, "")) * mult
                except ValueError:
                    return 0
        
        try:
            return float(mcap_str)
        except ValueError:
            return 0
    
    def _parse_time_to_hours(self, time_str: str) -> float:
        """Parse time string to hours"""
        time_str = time_str.lower().strip()
        
        # Try to extract number and unit
        import re
        match = re.search(r'(\d+\.?\d*)\s*(hour|hr|h|day|d|week|w|min|m)', time_str)
        
        if not match:
            return 0
        
        value = float(match.group(1))
        unit = match.group(2)
        
        if unit in ["hour", "hr", "h"]:
            return value
        elif unit in ["day", "d"]:
            return value * 24
        elif unit in ["week", "w"]:
            return value * 24 * 7
        elif unit in ["min", "m"]:
            return value / 60
        
        return value
    
    def _update_meta_analysis(self):
        """Update aggregate analysis for each narrative"""
        db = self._load_db()
        coins = db["coins"]
        
        # Group by narrative
        by_narrative = {}
        for coin in coins:
            narrative = coin["narrative"]
            if narrative not in by_narrative:
                by_narrative[narrative] = []
            by_narrative[narrative].append(coin)
        
        # Calculate stats for each narrative
        analysis = {}
        for narrative, narrative_coins in by_narrative.items():
            mcaps = [c["peak_mcap_numeric"] for c in narrative_coins if c["peak_mcap_numeric"] > 0]
            times = [c["time_to_peak_hours"] for c in narrative_coins if c["time_to_peak_hours"] > 0]
            
            if mcaps:
                analysis[narrative] = {
                    "count": len(narrative_coins),
                    "avg_peak_mcap": sum(mcaps) / len(mcaps),
                    "min_peak_mcap": min(mcaps),
                    "max_peak_mcap": max(mcaps),
                    "median_peak_mcap": sorted(mcaps)[len(mcaps) // 2],
                    "avg_time_to_peak_hours": sum(times) / len(times) if times else 0,
                    "suggested_ceiling": self._format_mcap(sorted(mcaps)[len(mcaps) // 2]),
                    "suggested_hold_time": self._format_hours(sum(times) / len(times)) if times else "unknown",
                }
        
        db["meta_analysis"] = analysis
        self._save_db(db)
    
    def _format_mcap(self, value: float) -> str:
        """Format numeric mcap to readable string"""
        if value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.1f}B"
        elif value >= 1_000_000:
            return f"${value / 1_000_000:.0f}M"
        elif value >= 1_000:
            return f"${value / 1_000:.0f}K"
        return f"${value:.0f}"
    
    def _format_hours(self, hours: float) -> str:
        """Format hours to readable time string"""
        if hours >= 168:  # 1 week
            return f"{hours / 168:.1f} weeks"
        elif hours >= 24:
            return f"{hours / 24:.1f} days"
        else:
            return f"{hours:.0f} hours"
    
    def get_all_coins(self, narrative: str = None) -> list[dict]:
        """Get all coin records, optionally filtered by narrative"""
        db = self._load_db()
        coins = db["coins"]
        
        if narrative:
            coins = [c for c in coins if c["narrative"] == narrative.lower().replace(" ", "_")]
        
        return sorted(coins, key=lambda x: x["recorded_at"], reverse=True)
    
    def get_meta_analysis(self, narrative: str = None) -> dict:
        """Get meta analysis for one or all narratives"""
        db = self._load_db()
        analysis = db.get("meta_analysis", {})
        
        if narrative:
            narrative_key = narrative.lower().replace(" ", "_")
            return analysis.get(narrative_key, {})
        
        return analysis
    
    def get_narrative_summary(self, narrative: str) -> str:
        """Get a human-readable summary for a narrative"""
        analysis = self.get_meta_analysis(narrative)
        
        if not analysis:
            return f"No data yet for '{narrative}' narrative."
        
        return (
            f"**{narrative.replace('_', ' ').title()} Analysis** ({analysis['count']} coins)\n"
            f"• Suggested ceiling: {analysis['suggested_ceiling']}\n"
            f"• Range: {self._format_mcap(analysis['min_peak_mcap'])} - {self._format_mcap(analysis['max_peak_mcap'])}\n"
            f"• Suggested hold time: {analysis['suggested_hold_time']}"
        )
    
    def get_overall_summary(self) -> str:
        """Get summary across all narratives"""
        analysis = self.get_meta_analysis()
        
        if not analysis:
            return "No coin performance data recorded yet."
        
        lines = ["**📊 Meta Analysis Summary**\n"]
        
        for narrative, data in sorted(analysis.items(), key=lambda x: -x[1]["count"]):
            lines.append(
                f"**{narrative.replace('_', ' ').title()}** ({data['count']} coins): "
                f"Ceiling ~{data['suggested_ceiling']}, Hold ~{data['suggested_hold_time']}"
            )
        
        return "\n".join(lines)
    
    def delete_coin(self, coin_id: int) -> bool:
        """Delete a coin record"""
        db = self._load_db()
        original_len = len(db["coins"])
        db["coins"] = [c for c in db["coins"] if c["id"] != coin_id]
        
        if len(db["coins"]) < original_len:
            self._save_db(db)
            self._update_meta_analysis()
            return True
        return False
    
    def search_coins(self, query: str) -> list[dict]:
        """Search coins by name or notes"""
        db = self._load_db()
        query_lower = query.lower()
        
        return [
            c for c in db["coins"]
            if query_lower in c["name"].lower() or query_lower in c.get("notes", "").lower()
        ]

