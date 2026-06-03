"""
Lab 05 — Auth Without Rolling Your Own

Demonstrates:
  - RFC 9728 protected-resource metadata  (/.well-known/oauth-protected-resource)
  - 401 handshake with WWW-Authenticate breadcrumb            (/whoami)
  - Scope-gated MCP tools                                     (/mcp)

Fake token registry (in lieu of a real IdP):
  tok_reader  -> scope: "notes:read"
  tok_writer  -> scope: "notes:read notes:write"
  tok_admin   -> scope: "notes:read notes:write admin:notes"
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastapi import Request
from fastapi.responses import JSONResponse

BASE = "http://127.0.0.1:8000"
METADATA_URL = f"{BASE}/.well-known/oauth-protected-resource"
CHALLENGE = f'Bearer resource_metadata="{METADATA_URL}"'

# ---------------------------------------------------------------------------
# Fake token store — in production this is your IdP (Clerk, Auth0, etc.)
# ---------------------------------------------------------------------------
_TOKENS: dict[str, dict] = {
    "tok_reader": {"sub": "alice", "scope": "notes:read"},
    "tok_writer": {"sub": "bob",   "scope": "notes:read notes:write"},
    "tok_admin":  {"sub": "carol", "scope": "notes:read notes:write admin:notes"},
}

_STORE: dict[str, list[str]] = {}

TOOL_SCOPES = {
    "read_notes":   "notes:read",
    "add_note":     "notes:write",
    "admin_purge":  "admin:notes",
}


def _claims_for(token: str) -> dict:
    if token not in _TOKENS:
        raise ToolError("401 unauthorized: unknown token")
    return _TOKENS[token]


def _require_scope(token: str, tool_name: str) -> dict:
    needed = TOOL_SCOPES[tool_name]
    claims = _claims_for(token)
    held = claims.get("scope", "").split()
    if needed not in held:
        raise ToolError(f"403 forbidden: tool '{tool_name}' requires scope '{needed}', token holds {held}")
    return claims


# ---------------------------------------------------------------------------
# Step 1 — RFC 9728 protected-resource metadata
# ---------------------------------------------------------------------------
mcp = FastMCP("scoped-toolsmith")


@mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
async def protected_resource(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "resource": f"{BASE}/mcp/",
            "authorization_servers": ["https://your-idp.example.com"],
            "bearer_methods_supported": ["header"],
            "scopes_supported": list(TOOL_SCOPES.values()),
        },
        headers={"Access-Control-Allow-Origin": "*"},
    )


# ---------------------------------------------------------------------------
# Step 2 — 401 handshake endpoint
# ---------------------------------------------------------------------------
@mcp.custom_route("/whoami", methods=["GET"])
async def whoami(request: Request) -> JSONResponse:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(
            {"error": "unauthorized", "detail": "present a bearer token"},
            status_code=401,
            headers={"WWW-Authenticate": CHALLENGE},
        )
    token = auth.split(" ", 1)[1]
    if token not in _TOKENS:
        return JSONResponse(
            {"error": "unauthorized", "detail": "unknown token"},
            status_code=401,
            headers={"WWW-Authenticate": CHALLENGE},
        )
    claims = _TOKENS[token]
    return JSONResponse({"ok": True, "sub": claims["sub"], "scope": claims["scope"]})


# ---------------------------------------------------------------------------
# Step 3 — scope-gated tools
# ---------------------------------------------------------------------------
@mcp.tool
def read_notes(token: str, user_id: str) -> list[str]:
    """Return all notes for a user. Requires scope: notes:read.

    Pass the bearer token as the first argument. The server validates
    that the token holds the notes:read scope before returning data.
    """
    _require_scope(token, "read_notes")
    return _STORE.get(user_id, [])


@mcp.tool
def add_note(token: str, user_id: str, note: str) -> str:
    """Append a note for a user. Requires scope: notes:write.

    Pass the bearer token as the first argument. Callers without
    notes:write receive a 403 ToolError regardless of their identity.
    """
    _require_scope(token, "add_note")
    _STORE.setdefault(user_id, []).append(note)
    return f"stored note for {user_id}"


@mcp.tool
def admin_purge(token: str, user_id: str) -> str:
    """Delete all notes for a user. Requires scope: admin:notes.

    Gated behind the highest privilege scope. Scopes freeze at token
    creation — a user upgrade requires a new token.
    """
    _require_scope(token, "admin_purge")
    removed = len(_STORE.pop(user_id, []))
    return f"purged {removed} notes for {user_id}"


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)
