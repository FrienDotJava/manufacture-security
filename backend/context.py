import json
from typing import Any

"""
Security analysis context and prompts for the Node-RED industrial cybersecurity analyzer.
"""

NODE_RED_AUDITOR_INSTRUCTIONS = """
You are a cybersecurity researcher analyzing Node-RED flows. You are given node-RED flow to analyze..

Your analysis process:
1. Review the Node-RED flow structure provided to you.
2. Identify security issues including:
   - Hardcoded credentials
   - Exposed HTTP endpoints
   - Active debug nodes in production
   - Missing input validation on data entry points
   - Missing timeout, watchdog, or deadman logic in critical actuator transitions.
3. Assign a valid CVSS score.

Known Protocol Rules:
- Modbus TCP is inherently unauthenticated. Do NOT flag a lack of Modbus authentication as an issue or recommend adding passwords to Modbus nodes.

Output Rules (Applies ONLY to your final response):
- Your final output must strictly follow the JSON schema.
- KEEP IT CONCISE: The "summary" field MUST be a maximum of 1 sentence.
- For `node_id`, extract the exact alphanumeric `id` property from the JSON object (e.g., "24ae7d2a1f4784c2").
- If an issue applies to the whole flow rather than a specific node, use "global" as the node_id.
"""

NODE_RED_FAULT_INJECTION_INSTRUCTIONS = """
You are an industrial control system safety auditor performing a behavioral "Shadow Audit."
 
You have been given:
1. The Node-RED flow source code (the INTENDED logic)
2. Fault injection test results (what the system ACTUALLY did when stressed with extreme values)
 
Your job is to compare intended vs actual behavior and identify both safety violations
and architectural gaps — logic that is absent from the flow but should exist.
 
ANALYSIS PROCESS:
 
1. Read the flow logic carefully. For this flow, the switch node (id: 8cefc7c46573306d)
   uses NUMERIC comparison (vt="num"), which is correct. The two rules are:
     - payload < 30  → pump ON  (tank filling)
     - payload >= 30 → pump OFF (tank full)
   Notice what is MISSING: there is no rule for out-of-range values (< 0 or > 100),
   no sensor validity check, and no watchdog/deadman timer on the pump.
 
2. For each test result with verdict PASS_WITH_ARCHITECTURAL_GAP:
   The pump reached the mechanically correct state, but only because a generic rule
   happened to catch the value. Explain what DEDICATED logic is missing:
     - An overflow alarm for values > 100 (physically impossible readings)
     - A sensor-fault alert rather than silently treating 110% the same as 35%
     - A lower-bound validity check for values <= 0
 
3. For each test result with verdict ARCHITECTURAL_GAP:
   The flow has no defined safe response at all. The pump turns ON by default
   because the value falls below 30, with no way to distinguish:
     - A legitimately empty tank (level=0 during initial fill)
     - A completely disconnected sensor (also reads 0)
     - A negative reading from a damaged sensor (reads -1)
   Required missing logic: minimum-valid-reading guard, sensor-health monitoring,
   and a deadman/watchdog timer that cuts the pump if level never rises.
 
4. Flag the active debug node (id: 24ae7d2a1f4784c2, active=true) as a production risk.
   Debug nodes expose internal message data to the Node-RED sidebar in production.
 
KNOWN PROTOCOL RULES:
- Modbus TCP is inherently unauthenticated. Do NOT flag this as a vulnerability.
 
OUTPUT RULES:
- Your final output must strictly follow the JSON schema.
- KEEP IT CONCISE: The "summary" field MUST be a maximum of 1 sentence.
- For `node_id`, use the exact `id` from the flow JSON (e.g., "8cefc7c46573306d").
- Use "global" for issues that span the whole flow (e.g., missing watchdog timer).
- Severity mapping:
    ARCHITECTURAL_GAP (sensor dropout, no watchdog)      → "high",   CVSS 7.0–8.9
    PASS_WITH_ARCHITECTURAL_GAP (no overflow alarm/range) → "medium", CVSS 4.0–6.9
    Active debug node in production                       → "low",    CVSS 0.0
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


def get_fault_injection_prompt(flow: Any, test_results: list) -> str:
    
    flow_text    = _format_payload(flow)
    results_text = _format_payload(test_results)
 
    # Count verdicts for the prompt header
    violations  = [r for r in test_results if r.get("verdict") == "CRITICAL_SAFETY_VIOLATION"]
    arch_gaps   = [r for r in test_results if r.get("verdict") == "ARCHITECTURAL_GAP"]
    pass_gaps   = [r for r in test_results if r.get("verdict") == "PASS_WITH_ARCHITECTURAL_GAP"]
    passes      = [r for r in test_results if r.get("verdict") == "PASS"]
 
    verdict_summary = (
        f"Test summary: {len(passes)} PASS, "
        f"{len(pass_gaps)} PASS_WITH_ARCHITECTURAL_GAP, "
        f"{len(violations)} CRITICAL_SAFETY_VIOLATION, "
        f"{len(arch_gaps)} ARCHITECTURAL_GAP "
        f"(out of {len(test_results)} total scenarios)."
    )
 
    return f"""You are performing a behavioral Shadow Audit of an industrial Node-RED control system.
The switch node has been fixed to use numeric comparison (vt="num"). No string-coercion bug exists.
The remaining findings are ARCHITECTURAL — logic that is absent but must be present in a safe system.
 
{verdict_summary}
 
===================================================
SECTION 1 — FLOW SOURCE CODE (Static Analysis)
===================================================
This is the CURRENT logic of the system. The switch uses numeric rules:
  rule 1: payload < 30  [numeric] → Payload True  → pump ON
  rule 2: payload >= 30 [numeric] → Payload False → pump OFF
 
Notice what is ABSENT:
  - No rule for payload > 100 (physically impossible overflow reading)
  - No rule for payload <= 0  (sensor dropout or negative/invalid reading)
  - No watchdog / deadman timer node to limit continuous pump runtime
  - No alert or alarm output path for out-of-range sensor values
 
{flow_text}
 
===================================================
SECTION 2 — FAULT INJECTION RESULTS (Dynamic Analysis)
===================================================
Live observations of what the system did when extreme values were injected.
 
Verdict definitions:
  PASS                        — pump state correct, logic adequate
  PASS_WITH_ARCHITECTURAL_GAP — pump state correct, but missing alarm/range-check logic
  ARCHITECTURAL_GAP           — no defined safe state; missing sensor validity or fail-safe
  CRITICAL_SAFETY_VIOLATION   — pump in a dangerous state (none expected with numeric fix)
 
Each result includes:
  injected_level              — the simulated water level sent to the system
  observed_pump_state_after   — what the pump register showed after Node-RED reacted
  expected_pump_state         — what a safe system MUST do (UNDEFINED = no safe default)
  verdict                     — see above
  expected_behavior_rationale — explanation of what safe logic should exist
 
{results_text}
 
===================================================
INSTRUCTIONS
===================================================
1. For each PASS_WITH_ARCHITECTURAL_GAP result: explain what dedicated logic is missing
   (e.g., a third switch rule for payload > 100 that routes to an alarm output),
   name the exact node responsible (switch id: 8cefc7c46573306d), and provide a fix.
2. For each ARCHITECTURAL_GAP result: explain the ambiguity (empty tank vs dead sensor),
   describe the missing fail-safe pattern (sensor validity check, lower-bound guard,
   watchdog timer), and recommend the Node-RED nodes needed to implement it.
3. Flag the active debug node (id: 24ae7d2a1f4784c2) as a production information-disclosure risk.
4. Output strictly as the SecurityReport JSON schema. Summary = 1 sentence max.
"""


def enhance_summary(flow_size: int, agent_summary: str) -> str:
    """Enhance the agent's summary with Node-RED-specific context."""
    return f"Analyzed {flow_size} characters of Node-RED flow data. {agent_summary}"
