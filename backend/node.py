from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any
import requests

app = FastAPI()

NODE_RED_URL = "http://localhost:1880/flows"

@app.get("/tools")
def list_tools():
    return {
        "tools": [
            {
                "name": "fetch_active_flow",
                "description": "Fetch current Node-RED flow JSON",
                "input_schema": {}
            }
        ]
    }


@app.post("/tools/fetch_active_flow")
def fetch_active_flow():
    try:
        res = requests.get(NODE_RED_URL)
        res.raise_for_status()

        return {
            "flow": res.json()
        }
    except Exception as e:
        return {
            "error": str(e)
        }

