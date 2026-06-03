"""
Lab 13 — Smoke Test Real Flows  (Step 2)

HTTP 200 is not correctness. This script walks real user paths:
  - Checks a page URL for expected strings
  - Calls tools/list on an MCP server and confirms all expected tools exist

Usage:
  python smoke.py                          # tests local discovery_server on :8000
  python smoke.py https://your-app.com    # tests a deployed URL

Exit 0 = all checks passed. Non-zero = something is wrong.
"""
import json
import sys
import urllib.error
import urllib.request


def _get(url: str, timeout: int = 8) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)


def _post(url: str, body: dict, timeout: int = 8) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"_error": str(e)}


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_page(url: str, must_contain: list[str]) -> list[str]:
    """Verify a page returns 200 and contains all expected strings."""
    failures = []
    status, body = _get(url)
    if status != 200:
        return [f"FAIL {url} → HTTP {status} (expected 200)"]
    for needle in must_contain:
        if needle not in body:
            failures.append(f"FAIL {url} → missing string: {needle!r}")
    return failures


def check_mcp_tools(base: str, expected_tools: list[str]) -> list[str]:
    """Initialize an MCP session and confirm all expected tools are listed."""
    failures = []

    # Single initialize call — capture both status and session header
    req = urllib.request.Request(
        f"{base}/mcp",
        data=json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "smoke", "version": "0"}}}
        ).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            session_id = r.headers.get("mcp-session-id", "")
            if r.status != 200:
                return [f"FAIL MCP initialize → HTTP {r.status}"]
    except Exception as e:
        return [f"FAIL MCP initialize: {e}"]

    if not session_id:
        return ["FAIL MCP initialize → no mcp-session-id header"]

    # tools/list
    list_req = urllib.request.Request(
        f"{base}/mcp",
        data=json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "mcp-session-id": session_id},
        method="POST",
    )
    try:
        with urllib.request.urlopen(list_req, timeout=8) as r:
            raw = r.read().decode()
            # SSE: strip "data: " prefix if present
            payload = raw.strip()
            for line in payload.splitlines():
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    break
            data = json.loads(payload)
    except Exception as e:
        return [f"FAIL tools/list: {e}"]

    found = {t["name"] for t in data.get("result", {}).get("tools", [])}
    for name in expected_tools:
        if name not in found:
            failures.append(f"FAIL tools/list → missing tool: {name!r}")

    return failures


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------

SUITES = {
    "well-known manifest": lambda base: check_page(
        f"{base}/.well-known/ai-agent.json",
        must_contain=["toolsmith", "mcp", "endpoint"],
    ),
    "agent card skills": lambda base: check_page(
        f"{base}/.well-known/agent-card.json",
        must_contain=["get_notes", "add_note", "search_notes"],
    ),
    "mcp tools": lambda base: check_mcp_tools(
        base,
        expected_tools=["get_notes", "add_note", "search_notes"],
    ),
}


def run(base: str) -> bool:
    """Run all smoke checks. Returns True if everything passed."""
    base = base.rstrip("/")
    print(f"Smoke testing: {base}\n")
    all_pass = True
    for suite, check in SUITES.items():
        failures = check(base)
        if failures:
            all_pass = False
            for f in failures:
                print(f"  ✗  [{suite}] {f}")
        else:
            print(f"  ✓  [{suite}]")
    return all_pass


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    ok = run(base)
    sys.exit(0 if ok else 1)
