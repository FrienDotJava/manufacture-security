# FlowGuard AI
An AI-powered security analysis tool for industrial Node-RED flows. This project simulates a real-world manufacturing environment where an AI agent continuously monitors and audits industrial automation logic for security vulnerabilities and logic flaws. All running locally without sending any data to API or any cloud.

---

## Overview

Manufacturing systems often run on automation flows built with Node-RED, which control physical devices such as pumps, valves, and sensors via Modbus. These flows are rarely audited for security issues. This project builds a local AI agent that can:

- Fetch the active Node-RED flow from a running industrial system
- Analyze it for security vulnerabilities using a locally hosted LLM
- Inject simulated fault values into the system and observe how it responds
- Report findings with severity scores and recommended fixes through a web dashboard

---

## How the AI Agent Works

The core of this project is an AI agent built on top of a locally running LLM (Llama 3) served by Ollama. The agent is given two capabilities:

**Static Analysis**: The agent receives the raw Node-RED flow JSON and uses its understanding of industrial security patterns to identify issues such as hardcoded credentials, missing input validation, exposed HTTP endpoints, and active debug nodes in production.

**Fault Injection Analysis**: The agent goes beyond static analysis by actively injecting sensor values into the running system through Node-RED's HTTP API. It then reads back the Modbus register to observe how the system physically responded. The results (pump ON/OFF state, expected vs observed behavior) are passed to the agent, which classifies each scenario as a pass, architectural gap, or critical safety violation.

This two-step approach reflects how real security assessments work in industrial environments.

The agent produces structured output defined using Pydantic schemas containing a summary, a list of issues, CVSS scores, affected node IDs, and recommended fixes. The output is constrained using JSON schema to ensure consistent, parseable responses from the LLM.

---

## Architecture

```
Browser
  |
  v
Next.js Frontend (port 3000)
  |
  v
FastAPI Backend (port 8000)
  |        |              |
  v        v              v
Ollama   Node-RED      Node-RED
(LLM)   Flow API      Modbus API
        (port 1880)   (port 10502)
```

All services run in Docker containers on the same local network. No data leaves the machine.

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Model | Llama 3.2 (via Ollama) |
| Agent Framework | MCP (Model Context Protocol) with FastMCP |
| Backend | FastAPI, Python |
| Frontend | Next.js, TypeScript, Tailwind CSS |
| Industrial Protocol | Modbus TCP (pymodbus) |
| Automation Runtime | Node-RED |
| Containerization | Docker, Docker Compose |
| Package Manager | uv |

---

## Features

- Local LLM inference (no OpenAI or cloud API, all data stays on the machine)
- Static security analysis of Node-RED flow JSON
- Dynamic fault injection with real Modbus register observation
- Structured AI output with CVSS scoring and per-node vulnerability mapping
- Interactive flow graph visualization in the frontend
- Vulnerable node highlighting linked to analysis results
- Fully containerized with Docker Compose

---

## Project Structure

```
manufacture-security/
├── backend/
│   ├── main.py              # FastAPI routes
│   ├── mcp_api.py           # MCP tool: fetch Node-RED flow
│   ├── mcp_server.py        # MCP server setup
│   ├── fault_injector.py    # Fault injection scenarios and Modbus observer
│   ├── context.py           # LLM system prompts and user prompts
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── page.tsx         # Main dashboard
│   │   ├── components/
│   │   │   ├── AnalysisResults.tsx
│   │   │   └── FlowGraph.tsx  # SVG-based flow graph renderer
│   │   └── types/
│   │       └── security.ts
│   └── Dockerfile
├── nodered/
│   └── flows.json           # Node-RED flow (water pump control system)
├── ollama/
│   └── Modelfile            # Custom model definition with auditor system prompt
└── docker-compose.yml
```

---

## Getting Started

### Prerequisites

- Docker Desktop installed and running
- At least 16GB RAM (the LLM requires significant memory)

### 1. Clone the repository

```bash
git clone https://github.com/FrienDotJava/manufacture-security.git
cd manufacture-security
```

### 2. Start all services

```bash
docker compose up -d --build
```

### 3. Set up the Ollama model (first time only)

Pull the base model:
```bash
docker compose exec ollama ollama pull llama3.2:3b
```

Copy the Modelfile into the container and create the custom auditor model:
```bash
docker compose cp ./ollama/Modelfile/Modelfile ollama:/Modelfile
docker compose exec ollama ollama create auditor-model -f /Modelfile/Modelfile
```

### 4. Open the dashboard

Visit `http://localhost:3000` in your browser.

---

## Usage

**Fetch and Analyze Flow**: Fetches the active Node-RED flow and runs static security analysis using the AI agent. Results appear in the dashboard with severity badges, CVSS scores, affected node IDs, and recommended fixes.

**Inject Sensor Value and Analyze Flow**: Runs a series of predefined fault scenarios (normal operation, overflow, sensor dropout, negative reading), injects each value into the running system, observes the physical response via Modbus, and sends the behavioral results to the AI agent for analysis.

The flow graph at the top of the dashboard visualizes the active Node-RED flow. Nodes identified as vulnerable by the analysis are highlighted with a red ring.

---

## Fault Injection Scenarios

| Scenario | Injected Value | Purpose |
|---|---|---|
| Normal Operation Baseline | 25 | Verify expected pump-on behavior |
| High Level Cutoff | 35 | Verify expected pump-off behavior |
| Overflow Fault Injection | 110 | Detect missing overflow alarm logic |
| Sensor Dropout / Zero Reading | 0 | Detect missing sensor health check |
| Negative Sensor Reading | -1 | Detect missing lower-bound validation |

---

## Deployment (Local Network)

This project is designed to run on a dedicated machine inside a factory network. Workers access the dashboard through a browser (no software installation required on their end).

To make the frontend accessible on the local network, update the build argument in `docker-compose.yml`:

```yaml
frontend:
  build:
    args:
      - NEXT_PUBLIC_API_URL=http://YOUR_MACHINE_IP:8000
```

Then rebuild:

```bash
docker compose up -d --build frontend
```

---

## Notes
I was an intern in a manufacturing company and it inspires me to do this project.
This project was built as a learning exercise and portfolio project. The Node-RED flow simulates a water pump control system using Modbus TCP, representing a simplified version of real industrial automation logic. The AI agent approach (combining static analysis with dynamic fault injection) is inspired by how professional industrial security assessments are conducted.