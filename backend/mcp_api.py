from mcp.server.fastmcp import FastMCP
import httpx # Using httpx is better for async agent environments

# Create a FastMCP instance
mcp = FastMCP("Node-RED Auditor")

NODE_RED_URL = "http://localhost:1880/flows"

@mcp.tool()
async def fetch_active_flow() -> str:
    """
    Fetch the current active Node-RED flow JSON. 
    Use this to inspect the industrial logic for security risks.
    """
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(NODE_RED_URL)
            res.raise_for_status()
            return str(res.json())
        except Exception as e:
            return f"Error fetching flow: {str(e)}"

if __name__ == "__main__":
    mcp.run()