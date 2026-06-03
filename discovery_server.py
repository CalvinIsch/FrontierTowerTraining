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

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from schema_server import mcp  # reuse the validated tool set from Lab 03

WELL_KNOWN_DIR = os.path.join(os.path.dirname(__file__), "public", ".well-known")


def _load(filename: str) -> dict:
    with open(os.path.join(WELL_KNOWN_DIR, filename)) as f:
        return json.load(f)


async def ai_agent_manifest(request: Request) -> Response:
    return JSONResponse(
        _load("ai-agent.json"),
        headers={"Access-Control-Allow-Origin": "*"},
    )


async def agent_card(request: Request) -> Response:
    return JSONResponse(
        _load("agent-card.json"),
        headers={"Access-Control-Allow-Origin": "*"},
    )


# Build the combined ASGI app: start from FastMCP's own app, add well-known routes
app = mcp.http_app(path="/mcp")
app.add_route("/.well-known/ai-agent.json", ai_agent_manifest, methods=["GET"])
app.add_route("/.well-known/agent-card.json", agent_card, methods=["GET"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
