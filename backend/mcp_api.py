from mcp.server.fastmcp import FastMCP
import httpx
import logging
import json
from pathlib import Path
import os

LOG_PATH = Path(__file__).with_name("mcp.log")

logger = logging.getLogger("mcp")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

mcp = FastMCP("Node-RED Auditor")

NODE_RED_URL = os.getenv("NODERED_URL", "http://localhost:1880")

@mcp.tool()
async def fetch_active_flow() -> str:
    """
    Fetch the current active Node-RED flow JSON. 
    Use this to inspect the industrial logic for security risks.
    """
    async with httpx.AsyncClient() as client:
        try:
            logger.info("fetch_active_flow invoked")
            res = await client.get(f"{NODE_RED_URL}/flows")
            res.raise_for_status()
            flow = res.json()

            logger.info(
                "fetch_active_flow success, node_count=%s",
                len(flow) if isinstance(flow, list) else "n/a"
            )
            logger.info("flow preview: %s", json.dumps(flow, ensure_ascii=False)[:1000])
            return str(flow)
        except Exception as e:
            logger.exception("fetch_active_flow failed")
            return f"Error fetching flow: {str(e)}"

if __name__ == "__main__":
    mcp.run()