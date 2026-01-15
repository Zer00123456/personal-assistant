"""
MCP Server Runner

Run this to start the MCP server for Claude/Cursor integration.
This is separate from the main bot/monitor system.
"""

import asyncio
from src.mcp.server import run_mcp_server

if __name__ == "__main__":
    asyncio.run(run_mcp_server())


