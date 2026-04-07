import os
from agents.mcp import MCPServerStdio

def create_nodered_server() -> MCPServerStdio:
    """Create and configure the Node-RED MCP server instance."""
    return MCPServerStdio(
        params={
            "command": "python",
            "args": ["mcp_api.py"], 
            "env": os.environ.copy(),
        },
        client_session_timeout_seconds=60,
    )