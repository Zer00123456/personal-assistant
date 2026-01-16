"""
Local MCP Server - Connects to VPS API through SSH tunnel

Run the SSH tunnel first:
    ssh -L 8000:localhost:8000 -N root@72.61.147.47

Then run this MCP server:
    python local_mcp.py
"""

import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# API base URL (through Cloudflare tunnel)
# Update this URL if the tunnel restarts
API_BASE = "https://clean-experienced-john-visible.trycloudflare.com"

def create_local_mcp() -> Server:
    """Create MCP server that proxies to VPS API"""
    
    server = Server("personal-assistant-local")
    client = httpx.Client(timeout=30.0)
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            # References
            Tool(
                name="search_references",
                description="Search creative references by semantic meaning",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "What to search for"},
                        "category": {"type": "string", "description": "Filter by category (optional)"},
                        "limit": {"type": "integer", "default": 10}
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="list_references",
                description="List all references, optionally by category",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "limit": {"type": "integer", "default": 50}
                    }
                }
            ),
            Tool(
                name="get_categories",
                description="List all categories in use",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="add_reference",
                description="Add a new reference to the database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "The content to store"},
                        "category": {"type": "string", "description": "Category (crypto, marketing, design, etc.)"},
                        "title": {"type": "string"},
                        "source_url": {"type": "string"}
                    },
                    "required": ["content", "category"]
                }
            ),
            Tool(
                name="update_reference",
                description="Update a reference's category or content",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ref_id": {"type": "string"},
                        "category": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["ref_id"]
                }
            ),
            Tool(
                name="delete_reference",
                description="Delete a reference",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ref_id": {"type": "string"}
                    },
                    "required": ["ref_id"]
                }
            ),
            
            # Trends
            Tool(
                name="list_trends",
                description="List all tracked trends for memecoin matching",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "active_only": {"type": "boolean", "default": True}
                    }
                }
            ),
            Tool(
                name="add_trend",
                description="Add a new trend to track",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {"type": "integer", "minimum": 1, "maximum": 5}
                    },
                    "required": ["keyword"]
                }
            ),
            Tool(
                name="delete_trend",
                description="Remove a trend",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trend_id": {"type": "integer"}
                    },
                    "required": ["trend_id"]
                }
            ),
            Tool(
                name="get_trend_matches",
                description="Get recent coins that matched trends",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20}
                    }
                }
            ),
            
            # Coin Performance
            Tool(
                name="list_coins",
                description="List recorded coin performance data",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "narrative": {"type": "string", "description": "Filter by narrative (optional)"}
                    }
                }
            ),
            Tool(
                name="get_meta_analysis",
                description="Get meta analysis showing ceilings and hold times by narrative",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "narrative": {"type": "string", "description": "Specific narrative (optional)"}
                    }
                }
            ),
            Tool(
                name="get_overall_summary",
                description="Get overall summary of all narratives",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="add_coin_data",
                description="Record a coin's performance",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "narrative": {"type": "string"},
                        "peak_mcap": {"type": "string", "description": "e.g., '500M', '1.2B'"},
                        "time_to_peak": {"type": "string", "description": "e.g., '3 days', '12 hours'"},
                        "notes": {"type": "string"}
                    },
                    "required": ["name", "narrative", "peak_mcap", "time_to_peak"]
                }
            ),
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Route tool calls to VPS API"""
        
        try:
            result = None
            
            # References
            if name == "search_references":
                resp = client.get(f"{API_BASE}/refs/search", params=arguments)
                result = resp.json()
            
            elif name == "list_references":
                resp = client.get(f"{API_BASE}/refs/list", params=arguments)
                result = resp.json()
            
            elif name == "get_categories":
                resp = client.get(f"{API_BASE}/refs/categories")
                result = resp.json()
            
            elif name == "add_reference":
                resp = client.post(f"{API_BASE}/refs/add", params=arguments)
                result = resp.json()
            
            elif name == "update_reference":
                ref_id = arguments.pop("ref_id")
                resp = client.put(f"{API_BASE}/refs/{ref_id}", params=arguments)
                result = resp.json()
            
            elif name == "delete_reference":
                resp = client.delete(f"{API_BASE}/refs/{arguments['ref_id']}")
                result = resp.json()
            
            # Trends
            elif name == "list_trends":
                resp = client.get(f"{API_BASE}/trends/list", params=arguments)
                result = resp.json()
            
            elif name == "add_trend":
                resp = client.post(f"{API_BASE}/trends/add", params=arguments)
                result = resp.json()
            
            elif name == "delete_trend":
                resp = client.delete(f"{API_BASE}/trends/{arguments['trend_id']}")
                result = resp.json()
            
            elif name == "get_trend_matches":
                resp = client.get(f"{API_BASE}/trends/matches", params=arguments)
                result = resp.json()
            
            # Coins
            elif name == "list_coins":
                resp = client.get(f"{API_BASE}/coins/list", params=arguments)
                result = resp.json()
            
            elif name == "get_meta_analysis":
                resp = client.get(f"{API_BASE}/coins/meta", params=arguments)
                result = resp.json()
            
            elif name == "get_overall_summary":
                resp = client.get(f"{API_BASE}/coins/summary")
                result = resp.json()
            
            elif name == "add_coin_data":
                resp = client.post(f"{API_BASE}/coins/add", params=arguments)
                result = resp.json()
            
            else:
                result = {"error": f"Unknown tool: {name}"}
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        except httpx.ConnectError:
            return [TextContent(type="text", text=json.dumps({
                "error": "Cannot connect to VPS API. Make sure SSH tunnel is running:\n  ssh -L 8000:localhost:8000 -N root@72.61.147.47"
            }))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
    
    return server


async def main():
    server = create_local_mcp()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())


