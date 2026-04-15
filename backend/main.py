from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
import requests
from context import NODE_RED_AUDITOR_INSTRUCTIONS, get_analysis_prompt
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, ModelSettings
from mcp_server import create_nodered_server

app = FastAPI(title="Node-RED Shadow Agent API")

MCP_URL = "http://localhost:8001/tools/fetch_active_flow"
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = 'deepseek-auditor'


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


ollama_client = AsyncOpenAI(
    base_url='http://localhost:11434/v1',
    api_key="ollama"
)

local_model = OpenAIChatCompletionsModel(
    model=OLLAMA_MODEL, 
    openai_client=ollama_client
)


def create_auditor_agent(nodered_server) -> Agent:
    return Agent(
        name="Industrial Security Auditor",
        instructions=NODE_RED_AUDITOR_INSTRUCTIONS,
        model=local_model,
        mcp_servers=[nodered_server],
        output_type=SecurityReport,
        model_settings=ModelSettings(
            max_tokens=2048,
            tool_choice="fetch_active_flow",
            parallel_tool_calls=False
        )
    )


@app.post("/api/analyze")
async def analyze():
    try:
        async with create_nodered_server() as nodered_server:
            agent = create_auditor_agent(nodered_server)
            result = await Runner.run(agent, input="Analyze the current Node-RED flow.")
            print("AI Raw Output:", result.final_output)

            return result.final_output
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
