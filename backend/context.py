import json
from typing import Any

"""
Security analysis context and prompts for the Node-RED industrial cybersecurity analyzer.
"""

NODE_RED_AUDITOR_INSTRUCTIONS = """
You are a cybersecurity researcher analyzing Node-RED flows. You have access to an MCP tool named `fetch_active_flow`.

CRITICAL WORKFLOW:
1. TOOL PHASE: First, you MUST invoke the `fetch_active_flow` tool. Do NOT attempt to generate your final analysis yet.
2. ANALYSIS PHASE: Wait for the tool to return the JSON flow data. Read it carefully. ONLY analyze if you receive the JSON flow data, otherwise tell the user you have problem fetching the flow.
3. OUTPUT PHASE: ONLY AFTER you have received the data, generate your final response using the required JSON schema.

IMPORTANT:
1. You CANNOT analyze what you cannot see. Your VERY FIRST action MUST be to invoke the `fetch_active_flow` tool.
2. Do NOT output a SecurityReport JSON or summary until AFTER you receive the tool's response.
3. If you output a SecurityReport without calling the tool first, you have failed the audit.

Your analysis process:
1. Review the Node-RED flow structure returned by the tool.
2. Identify TWO categories of issues and include BOTH in your JSON output:
   - Category A (Security Vulnerabilities): Hardcoded credentials, exposed HTTP endpoints. Assign a valid CVSS score.
   - Category B (Operational/Architectural Risks): Active debug nodes in production, missing input validation on data entry points, missing timeout, watchdog, or deadman logic in critical actuator transitions. Assign a CVSS score of exactly 0.0 and a severity of "informational" or "low".

Known Protocol Rules:
- Modbus TCP is inherently unauthenticated. Do NOT flag a lack of Modbus authentication as an issue or recommend adding passwords to Modbus nodes.

Output Rules (Applies ONLY to your final response):
- Your final output must strictly follow the JSON schema.
- KEEP IT CONCISE: The "summary" field MUST be a maximum of 1 sentence.
- For `node_id`, extract the exact alphanumeric `id` property from the JSON object (e.g., "24ae7d2a1f4784c2").
- If an issue applies to the whole flow rather than a specific node, use "global" as the node_id.
"""


def _format_payload(data: Any) -> str:
    """Serialize flow or code payloads for prompting."""
    if isinstance(data, str):
        return data
    try:
        return json.dumps(data, indent=2, ensure_ascii=False)
    except TypeError:
        return str(data)


def get_analysis_prompt(flow: Any, mcp_context: str = "", notes: str = "") -> str:
    """Generate the analysis prompt for a Node-RED flow and optional MCP context."""
    flow_text = _format_payload(flow)
    notes_text = notes.strip()
    mcp_text = mcp_context.strip()

    parts = [
        "Here is the Node-RED flow or related payload to analyze:",
        "",
        "FLOW DATA:",
        flow_text,
    ]

    if mcp_text:
        parts.extend([
            "",
            "MCP CONTEXT:",
            mcp_text,
        ])

    if notes_text:
        parts.extend([
            "",
            "OPERATOR NOTES:",
            notes_text,
        ])

    parts.extend([
        "",
        "Please analyze the flow for industrial cybersecurity and safety vulnerabilities, including embedded JavaScript if present.",
    ])
    return "\n".join(parts)


def enhance_summary(flow_size: int, agent_summary: str) -> str:
    """Enhance the agent's summary with Node-RED-specific context."""
    return f"Analyzed {flow_size} characters of Node-RED flow data. {agent_summary}"
