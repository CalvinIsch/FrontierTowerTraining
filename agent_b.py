"""
Lab 10 — Agent B (worker, port 8801)

Serves:
  GET  /.well-known/agent-card.json  — skill advertisement
  POST /tasks                         — accepts envelopes, returns signed results

Security:
  - Signs every result with HMAC-SHA256
  - Rate-limits each sender to 5 requests per 60 s (drops with HTTP 429)
"""
import hashlib
import hmac
import json
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

NAME   = "agent-b"
PORT   = 8801
SECRET = b"shared-lab-secret"

RATE_LIMIT   = 5       # max requests per window
WINDOW_SECS  = 60.0

# per-sender [(timestamp, …), …] log
_rate_log: dict[str, list[float]] = {}

AGENT_CARD = {
    "schema_version": "1.0",
    "name": NAME,
    "skills": [
        {
            "id": "summarize",
            "description": (
                "Extract the first sentence from a block of text. "
                "Call this when you need a one-sentence summary."
            ),
            "input":  {"text": "string"},
            "output": {"summary": "string"},
        }
    ],
}


# ---------------------------------------------------------------------------
# HMAC helpers
# ---------------------------------------------------------------------------

def canonical(body: dict) -> bytes:
    """Deterministic JSON bytes: sorted keys, no extra spaces."""
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def sign(body: dict) -> str:
    return hmac.new(SECRET, canonical(body), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

def _allow(sender: str) -> bool:
    now = time.monotonic()
    timestamps = [t for t in _rate_log.get(sender, []) if now - t < WINDOW_SECS]
    if len(timestamps) >= RATE_LIMIT:
        _rate_log[sender] = timestamps
        return False
    timestamps.append(now)
    _rate_log[sender] = timestamps
    return True


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

def _summarize(text: str) -> str:
    """Return the first sentence (up to the first '.', '!', or '?')."""
    for i, ch in enumerate(text):
        if ch in ".!?":
            return text[: i + 1].strip()
    return text.strip()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app = FastAPI()


@app.get("/.well-known/agent-card.json")
async def agent_card() -> JSONResponse:
    return JSONResponse(AGENT_CARD, headers={"Access-Control-Allow-Origin": "*"})


@app.post("/tasks")
async def tasks(request: Request) -> JSONResponse:
    envelope = await request.json()
    sender = envelope.get("from", "unknown")

    if not _allow(sender):
        return JSONResponse(
            {"error": "over budget", "from": NAME, "to": sender},
            status_code=429,
        )

    intent  = envelope.get("intent")
    payload = envelope.get("payload", {})

    if intent == "summarize":
        result_body = {
            "from":    NAME,
            "to":      sender,
            "intent":  intent,
            "summary": _summarize(payload.get("text", "")),
        }
        return JSONResponse({"body": result_body, "sig": sign(result_body)})

    return JSONResponse({"error": f"unknown intent: {intent}"}, status_code=400)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
