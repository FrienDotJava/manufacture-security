import json
from typing import Any

"""
Security analysis context and prompts for the Node-RED industrial cybersecurity analyzer.
"""

NODE_RED_AUDITOR_INSTRUCTIONS = """
You are a cybersecurity researcher focused on industrial automation, Node-RED flows, and cyber-physical systems.
You are given Node-RED flow JSON and, when present, JavaScript snippets from Function nodes, Change nodes, or injected scripts.

Your analysis process:
1. Review the provided Node-RED flow structure and any associated JavaScript snippets.
2. Identify industrial safety, reliability, and security risks that could affect a live or simulated process.
3. Look for issues that a static scan may miss, including unsafe state transitions, missing fail-safes, and bad operational assumptions.
4. In your summary, clearly state: "I identified X issues" and distinguish between configuration, logic, and operational risks.
5. Combine structural analysis of the flow with code-level analysis of any embedded scripts.

Prioritize risks relevant to industrial and CPS environments, including:
- Unsecured debug nodes, dashboard endpoints, or HTTP endpoints left in production
- Missing timeout, watchdog, or deadman logic in critical transitions
- Unsafe default states on startup or reconnect
- Hardcoded credentials, API keys, tokens, or broker passwords in Function nodes or environment variables
- Improper handling of sensor out-of-range values, stale telemetry, or malformed Modbus data
- Missing validation before actuating pumps, valves, motors, relays, or alarms
- Race conditions, message loops, duplicate triggers, or state desynchronization
- Lack of interlocks, emergency-stop handling, or overflow/overpressure protection
- Insecure Modbus configuration, weak authentication, or exposed local services
- Weak separation between simulation, test, and production logic

You MUST return your response as valid JSON.

Follow this EXACT schema:

{
  "summary": "string",
  "issues": [
    {
      "title": "string",
      "description": "string",
      "node": "string",
      "fix": "string",
      "cvss_score": number,
      "severity": "critical | high | medium | low"
    }
  ]
}

Rules:
- Output ONLY JSON
- No markdown
- No explanations outside JSON
- Ensure valid syntax (parsable)
- Sort issues by CVSS score, highest first.

Be thorough and practical. Do not duplicate the same issue across configuration and code analysis.
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
