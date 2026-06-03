import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP
from result import ok_result, err_result, AUTH_EXPIRED, RATE_LIMIT, NOT_FOUND, TRANSIENT
from fetch_user import fetch_user as _fetch_user

mcp = FastMCP("toolsmith")


@mcp.tool
def add(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return a + b


@mcp.tool
def fetch_user(user_id: int) -> dict:
    """Fetch a user by ID. Returns ok/value or ok/error_kind on failure."""
    r = _fetch_user(user_id)
    return {"ok": r.ok, "value": r.value, "error": r.error, "error_kind": r.error_kind}


@mcp.tool
def classify_status(status_code: int) -> str:
    """Map an HTTP status code to an error taxonomy constant."""
    if status_code in (401, 403):
        return AUTH_EXPIRED
    if status_code == 429:
        return RATE_LIMIT
    if status_code == 404:
        return NOT_FOUND
    return TRANSIENT


if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    if transport == "http":
        mcp.run(transport="http", host="127.0.0.1", port=8000)
    else:
        mcp.run()
