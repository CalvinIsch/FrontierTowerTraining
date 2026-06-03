"""
Lab 04 — agent-discoverable server.

Serves:
  GET /.well-known/ai-agent.json   — manifest
  GET /.well-known/agent-card.json — skill catalogue
  ALL /mcp                         — FastMCP endpoint (Streamable HTTP)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from schema_server import mcp  # reuse the validated tool set from Lab 03

WELL_KNOWN_DIR = os.path.join(os.path.dirname(__file__), "public", ".well-known")


def _load(filename: str) -> dict:
    with open(os.path.join(WELL_KNOWN_DIR, filename)) as f:
        return json.load(f)


# FastMCP requires its lifespan (session manager startup) passed to the parent app
_mcp_app = mcp.http_app(path="/mcp")
app = FastAPI(lifespan=_mcp_app.lifespan)


@app.get("/.well-known/ai-agent.json")
async def ai_agent_manifest() -> JSONResponse:
    return JSONResponse(
        _load("ai-agent.json"),
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/.well-known/agent-card.json")
async def agent_card() -> JSONResponse:
    return JSONResponse(
        _load("agent-card.json"),
        headers={"Access-Control-Allow-Origin": "*"},
    )


# FastAPI's specific routes above take priority; everything else goes to FastMCP
app.mount("/", _mcp_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
