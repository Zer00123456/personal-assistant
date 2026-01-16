"""
MCP Server for Claude/Cursor Integration

Exposes the reference database and trends tracking to AI assistants.
Allows Claude to read, write, search, and organize content.
"""

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import json

from ..database import ReferencesDB, TrendsDB, CoinPerformanceDB


def create_mcp_server() -> Server:
    """Create and configure the MCP server"""
    
    server = Server("personal-assistant")
    refs_db = ReferencesDB()
    trends_db = TrendsDB()
    coin_db = CoinPerformanceDB()
    
    # ==================== TOOLS ====================
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            # Creative References Tools
            Tool(
                name="search_references",
                description="Search creative references (articles, designs, fonts, etc.) using semantic search",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What to search for (e.g., 'brutalist landing pages', 'persuasive headlines')"
                        },
                        "category": {
                            "type": "string",
                            "description": "Filter by category: copywriting, design, fonts, colors, styles, landing_pages, thumbnails, logos, twitter",
                            "enum": ["copywriting", "design", "fonts", "colors", "styles", "landing_pages", "thumbnails", "logos", "twitter", None]
                        },
                        "project": {
                            "type": "string",
                            "description": "Filter by project name (leave empty for general references)"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 10)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="add_reference",
                description="Add a new creative reference to the database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The content to store (article text, design description, etc.)"
                        },
                        "title": {
                            "type": "string",
                            "description": "Title of the reference"
                        },
                        "category": {
                            "type": "string",
                            "description": "Category for organization"
                        },
                        "source_url": {
                            "type": "string",
                            "description": "Source URL if applicable"
                        },
                        "project": {
                            "type": "string",
                            "description": "Project name if project-specific (leave empty for general)"
                        },
                        "content_type": {
                            "type": "string",
                            "description": "Type: article, tweet, design, image",
                            "enum": ["article", "tweet", "design", "image"]
                        }
                    },
                    "required": ["content", "category"]
                }
            ),
            Tool(
                name="list_references",
                description="List all references, optionally filtered by category or project",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Filter by category"
                        },
                        "project": {
                            "type": "string",
                            "description": "Filter by project"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 50
                        }
                    }
                }
            ),
            Tool(
                name="update_reference",
                description="Update a reference's category, project, or content",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ref_id": {
                            "type": "string",
                            "description": "The reference ID to update"
                        },
                        "category": {"type": "string"},
                        "project": {"type": "string"},
                        "content": {"type": "string"},
                        "title": {"type": "string"}
                    },
                    "required": ["ref_id"]
                }
            ),
            Tool(
                name="delete_reference",
                description="Delete a reference by ID",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ref_id": {
                            "type": "string",
                            "description": "The reference ID to delete"
                        }
                    },
                    "required": ["ref_id"]
                }
            ),
            Tool(
                name="get_categories",
                description="List all categories currently in use",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="get_projects",
                description="List all projects that have references",
                inputSchema={"type": "object", "properties": {}}
            ),
            
            # Trends Tools (Memecoin Tracking)
            Tool(
                name="add_trend",
                description="Add a new trend/keyword to track for memecoin matching",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "The trend keyword to track (e.g., 'vibe coding', 'AI agents')"
                        },
                        "description": {
                            "type": "string",
                            "description": "Context about this trend"
                        },
                        "aliases": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Alternative spellings/variations"
                        },
                        "priority": {
                            "type": "integer",
                            "description": "Priority 1-5 (higher = more important)",
                            "minimum": 1,
                            "maximum": 5
                        }
                    },
                    "required": ["keyword"]
                }
            ),
            Tool(
                name="list_trends",
                description="List all tracked trends",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "active_only": {
                            "type": "boolean",
                            "default": True
                        }
                    }
                }
            ),
            Tool(
                name="remove_trend",
                description="Remove a trend from tracking",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trend_id": {
                            "type": "integer",
                            "description": "The trend ID to remove"
                        }
                    },
                    "required": ["trend_id"]
                }
            ),
            Tool(
                name="update_trend",
                description="Update a trend's details",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trend_id": {"type": "integer"},
                        "keyword": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {"type": "integer"},
                        "aliases": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["trend_id"]
                }
            ),
            Tool(
                name="get_recent_matches",
                description="Get recent coin matches",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "default": 20
                        }
                    }
                }
            ),
            Tool(
                name="search_trends",
                description="Search trends by keyword",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            ),
            
            # Coin Performance Tools (Meta Analysis)
            Tool(
                name="add_coin_data",
                description="Record a coin's performance for meta analysis",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Coin name/ticker"
                        },
                        "narrative": {
                            "type": "string",
                            "description": "Meta category: ai_agents, animal, celebrity, political, gaming, defi, meme_culture, tech, viral_moment, influencer, other"
                        },
                        "peak_mcap": {
                            "type": "string",
                            "description": "Peak market cap (e.g., '500M', '1.2B', '50K')"
                        },
                        "time_to_peak": {
                            "type": "string",
                            "description": "Time to reach peak (e.g., '3 days', '12 hours')"
                        },
                        "notes": {
                            "type": "string",
                            "description": "Additional context"
                        }
                    },
                    "required": ["name", "narrative", "peak_mcap", "time_to_peak"]
                }
            ),
            Tool(
                name="get_meta_analysis",
                description="Get meta analysis showing typical ceilings and hold times for narratives",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "narrative": {
                            "type": "string",
                            "description": "Specific narrative to analyze (optional, omit for all)"
                        }
                    }
                }
            ),
            Tool(
                name="list_coin_data",
                description="List all recorded coin performance data",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "narrative": {
                            "type": "string",
                            "description": "Filter by narrative (optional)"
                        }
                    }
                }
            ),
            Tool(
                name="get_narrative_summary",
                description="Get a readable summary of a narrative's performance patterns",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "narrative": {
                            "type": "string",
                            "description": "The narrative to summarize"
                        }
                    },
                    "required": ["narrative"]
                }
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls"""
        
        result = None
        
        # Creative References
        if name == "search_references":
            results = refs_db.search(
                query=arguments["query"],
                category=arguments.get("category"),
                project=arguments.get("project"),
                limit=arguments.get("limit", 10)
            )
            result = {"count": len(results), "references": results}
        
        elif name == "add_reference":
            ref_id = refs_db.add_reference(
                content=arguments["content"],
                title=arguments.get("title"),
                category=arguments["category"],
                source_url=arguments.get("source_url"),
                project=arguments.get("project"),
                content_type=arguments.get("content_type", "article")
            )
            result = {"success": True, "id": ref_id}
        
        elif name == "list_references":
            refs = refs_db.list_all(
                category=arguments.get("category"),
                project=arguments.get("project"),
                limit=arguments.get("limit", 50)
            )
            result = {"count": len(refs), "references": refs}
        
        elif name == "update_reference":
            ref_id = arguments.pop("ref_id")
            success = refs_db.update(ref_id, **arguments)
            result = {"success": success}
        
        elif name == "delete_reference":
            success = refs_db.delete(arguments["ref_id"])
            result = {"success": success}
        
        elif name == "get_categories":
            result = {"categories": refs_db.get_categories()}
        
        elif name == "get_projects":
            result = {"projects": refs_db.get_projects()}
        
        # Trends
        elif name == "add_trend":
            trend = trends_db.add_trend(
                keyword=arguments["keyword"],
                description=arguments.get("description"),
                aliases=arguments.get("aliases"),
                priority=arguments.get("priority", 1)
            )
            result = trend
        
        elif name == "list_trends":
            trends = trends_db.get_all_trends(
                active_only=arguments.get("active_only", True)
            )
            result = {"count": len(trends), "trends": trends}
        
        elif name == "remove_trend":
            success = trends_db.delete_trend(arguments["trend_id"])
            result = {"success": success}
        
        elif name == "update_trend":
            trend_id = arguments.pop("trend_id")
            trend = trends_db.update_trend(trend_id, **arguments)
            result = {"success": trend is not None, "trend": trend}
        
        elif name == "get_recent_matches":
            matches = trends_db.get_recent_matches(arguments.get("limit", 20))
            result = {"count": len(matches), "matches": matches}
        
        elif name == "search_trends":
            trends = trends_db.search_trends(arguments["query"])
            result = {"count": len(trends), "trends": trends}
        
        # Coin Performance
        elif name == "add_coin_data":
            coin = coin_db.add_coin(
                name=arguments["name"],
                narrative=arguments["narrative"],
                peak_mcap=arguments["peak_mcap"],
                time_to_peak=arguments["time_to_peak"],
                notes=arguments.get("notes")
            )
            result = {"success": True, "coin": coin}
        
        elif name == "get_meta_analysis":
            if arguments.get("narrative"):
                analysis = coin_db.get_meta_analysis(arguments["narrative"])
            else:
                analysis = coin_db.get_meta_analysis()
            result = {"analysis": analysis}
        
        elif name == "list_coin_data":
            coins = coin_db.get_all_coins(narrative=arguments.get("narrative"))
            result = {"count": len(coins), "coins": coins}
        
        elif name == "get_narrative_summary":
            summary = coin_db.get_narrative_summary(arguments["narrative"])
            result = {"summary": summary}
        
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    return server


async def run_mcp_server():
    """Run the MCP server"""
    server = create_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


