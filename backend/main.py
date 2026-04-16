from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List
from ollama import AsyncClient
import json

from context import (
    NODE_RED_AUDITOR_INSTRUCTIONS, 
    NODE_RED_FAULT_INJECTION_INSTRUCTIONS, 
    get_analysis_prompt, 
    get_fault_injection_prompt
)
from mcp_server import create_nodered_server
from mcp_api import fetch_active_flow
from fault_injector import run_all_fault_scenarios

app = FastAPI(title="Node-RED Shadow Agent API")

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = 'deepseek-auditor'

ollama_client = AsyncClient(host=OLLAMA_HOST)

class SecurityIssue(BaseModel):
    title: str = Field(description="Brief title of the security vulnerability")
    description: str = Field(
        description="Detailed description of the security issue and its potential impact"
    )
    node_id: str = Field(
        description="The EXACT 'id' string of the specific vulnerable node from the JSON flow (e.g., '10bdf115b9a4e47d'). Do not use generic names."
    )
    fix: str = Field(description="Recommended code fix or mitigation strategy")
    cvss_score: float = Field(
        description="CVSS score (0.1 to 10.0) for software vulnerabilities. Use exactly 0.0 for architectural or operational logic flaws."
    )
    severity: str = Field(description="Severity level: critical, high, medium, or low")


class SecurityReport(BaseModel):
    summary: str = Field(description="A strict, 1-sentence executive summary. DO NOT list issues here. Save them for the issues array.")
    issues: List[SecurityIssue] = Field(description="List of identified security vulnerabilities")


@app.post("/api/analyze", response_model=SecurityReport)
async def analyze():
    try:
        async with create_nodered_server() as nodered_server:
            flow_json = await fetch_active_flow() 
            
            analysis_prompt = get_analysis_prompt(flow=flow_json)
            
            # Use pure Ollama chat with native Pydantic schema formatting
            response = await ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=[
                    {'role': 'system', 'content': NODE_RED_AUDITOR_INSTRUCTIONS},
                    {'role': 'user', 'content': analysis_prompt}
                ],
                format=SecurityReport.model_json_schema(),
                options={"temperature": 0.0} # Recommended for strict structured outputs
            )
            
            raw_output = response['message']['content']
            print("AI Raw Output:", raw_output)

            # Validate and parse the JSON string back into the Pydantic model
            return SecurityReport.model_validate_json(raw_output)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")

@app.post("/api/fault-inject", response_model=SecurityReport)
async def fault_inject():
    try:
        flow_json = await fetch_active_flow()
 
        print("Starting fault injection scenarios...")
        test_results = await run_all_fault_scenarios()
 
        for r in test_results:
            print(f"  [{r['verdict']:35s}] {r['scenario_name']} "
                  f"(level={r['injected_level']:>4}, pump={r['observed_pump_state_after']})")
 
        fault_prompt = get_fault_injection_prompt(
            flow=flow_json,
            test_results=test_results,
        )
 
        response = await ollama_client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {'role': 'system', 'content': NODE_RED_FAULT_INJECTION_INSTRUCTIONS},
                {'role': 'user', 'content': fault_prompt}
            ],
            format=SecurityReport.model_json_schema(),
            options={"temperature": 0.0}
        )
 
        raw_output = response['message']['content']
        print("AI Raw Output:", raw_output)
        
        return SecurityReport.model_validate_json(raw_output)
 
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fault injection audit failed: {str(e)}")
 

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)