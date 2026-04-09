from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Dict, Any, List
import requests
from context import NODE_RED_AUDITOR_INSTRUCTIONS, get_analysis_prompt
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel
from mcp_server import create_nodered_server

app = FastAPI(title="Node-RED Shadow Agent API")

MCP_URL = "http://localhost:8001/tools/fetch_active_flow"
OLLAMA_URL = "http://localhost:11434/api/chat"


class SecurityIssue(BaseModel):
    title: str = Field(description="Brief title of the security vulnerability")
    description: str = Field(
        description="Detailed description of the security issue and its potential impact"
    )
    node: str = Field(
        description="The specific vulnerable node that demonstrates the issue"
    )
    fix: str = Field(description="Recommended code fix or mitigation strategy")
    cvss_score: float = Field(description="CVSS score from 0.0 to 10.0 representing severity")
    severity: str = Field(description="Severity level: critical, high, medium, or low")


class SecurityReport(BaseModel):
    summary: str = Field(description="Executive summary of the security analysis")
    issues: List[SecurityIssue] = Field(description="List of identified security vulnerabilities")


ollama_client = AsyncOpenAI(
    base_url='http://localhost:11434/v1',
    api_key="ollama"
)

local_model = OpenAIChatCompletionsModel(
    model='deepseek-coder-v2', 
    openai_client=ollama_client
)

def create_auditor_agent(nodered_server) -> Agent:
    return Agent(
        name="Industrial Security Auditor",
        instructions=NODE_RED_AUDITOR_INSTRUCTIONS,
        model=local_model,
        mcp_servers=[nodered_server],
        output_type=SecurityReport
    )


def get_flow_from_mcp():
    try:
        res = requests.post(MCP_URL)
        res.raise_for_status()
        return res.json().get("flow", [])
    except Exception as e:
        print(f"Error fetching flow: {e}")
        return []


@app.post("/api/analyze")
async def analyze():
    async with create_nodered_server() as nodered_server:
        agent = create_auditor_agent(nodered_server)
        result = await Runner.run(agent, input="Analyze the current Node-RED flow.")
        return result.final_output


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
