#!/usr/bin/env python3
"""
Quick trend management script
Run: python3 manage_trends.py
"""

import json
import os

TRENDS_FILE = "data/trends.json"

def load_trends():
    if os.path.exists(TRENDS_FILE):
        with open(TRENDS_FILE, 'r') as f:
            return json.load(f)
    return {"trends": [], "total_matches": 0}

def save_trends(data):
    os.makedirs("data", exist_ok=True)
    with open(TRENDS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def list_trends():
    data = load_trends()
    print("\n📊 Current tracked trends:")
    print("-" * 40)
    if not data.get("trends"):
        print("  (none)")
    else:
        for t in data["trends"]:
            status = "✅" if t.get("active", True) else "❌"
            print(f"  {status} {t['keyword']} (id: {t['id']})")
    print()

def remove_trend(keyword):
    data = load_trends()
    keyword_lower = keyword.lower()
    
    original_count = len(data.get("trends", []))
    data["trends"] = [t for t in data.get("trends", []) 
                      if t.get("keyword", "").lower() != keyword_lower 
                      and t.get("id", "").lower() != keyword_lower]
    
    if len(data["trends"]) < original_count:
        save_trends(data)
        print(f"✅ Removed '{keyword}' from tracked trends")
    else:
        print(f"⚠️ '{keyword}' not found in trends")

def add_trend(keyword, description=""):
    data = load_trends()
    
    # Check if already exists
    for t in data.get("trends", []):
        if t.get("keyword", "").lower() == keyword.lower():
            print(f"⚠️ '{keyword}' already being tracked")
            return
    
    trend_id = keyword.lower().replace(" ", "-")
    new_trend = {
        "id": trend_id,
        "keyword": keyword,
        "description": description,
        "added_at": "2025-01-16",
        "active": True,
        "aliases": [keyword.lower(), keyword.lower().replace(" ", "")],
        "matches": []
    }
    
    data["trends"].append(new_trend)
    save_trends(data)
    print(f"✅ Added '{keyword}' to tracked trends")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        list_trends()
        print("Usage:")
        print("  python3 manage_trends.py list")
        print("  python3 manage_trends.py remove <keyword>")
        print("  python3 manage_trends.py add <keyword>")
        sys.exit(0)
    
    cmd = sys.argv[1].lower()
    
    if cmd == "list":
        list_trends()
    elif cmd == "remove" and len(sys.argv) >= 3:
        remove_trend(" ".join(sys.argv[2:]))
        list_trends()
    elif cmd == "add" and len(sys.argv) >= 3:
        add_trend(" ".join(sys.argv[2:]))
        list_trends()
    else:
        print("Unknown command. Use: list, remove <keyword>, add <keyword>")

