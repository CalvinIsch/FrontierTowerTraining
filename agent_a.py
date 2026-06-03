"""
Lab 10 — Agent A (orchestrator)

1. Discovers Agent B's card
2. Confirms the 'summarize' skill exists
3. Dispatches task envelopes
4. Verifies HMAC signatures on results
5. Handles 429 rate-limit responses
"""
import hashlib
import hmac
import json
import urllib.error
import urllib.request

NAME    = "agent-a"
B_BASE  = "http://127.0.0.1:8801"
SECRET  = b"shared-lab-secret"


# ---------------------------------------------------------------------------
# HMAC helpers (identical to agent_b — shared secret, same canonical form)
# ---------------------------------------------------------------------------

def canonical(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def verify(body: dict, sig: str) -> bool:
    expected = hmac.new(SECRET, canonical(body), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(url: str) -> dict:
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


def _post(url: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# ---------------------------------------------------------------------------
# Step 1 — Discover
# ---------------------------------------------------------------------------

def discover(base: str) -> dict:
    card = _get(f"{base}/.well-known/agent-card.json")
    skills = {s["id"] for s in card.get("skills", [])}
    print(f"[discover] {card['name']} advertises skills: {skills}")
    return card


# ---------------------------------------------------------------------------
# Step 2 — Dispatch
# ---------------------------------------------------------------------------

def dispatch(intent: str, payload: dict) -> tuple[int, dict]:
    envelope = {"from": NAME, "to": "agent-b", "intent": intent, "payload": payload}
    status, response = _post(f"{B_BASE}/tasks", envelope)
    return status, response


# ---------------------------------------------------------------------------
# Step 3 — Verify
# ---------------------------------------------------------------------------

def handle(status: int, response: dict) -> None:
    if status == 429:
        print(f"  [429] rate-limited: {response.get('error')}")
        return
    if status != 200:
        print(f"  [ERROR {status}] {response}")
        return

    body = response.get("body", {})
    sig  = response.get("sig", "")
    ok   = verify(body, sig)
    mark = "✓" if ok else "✗ INVALID SIG"
    print(f"  [{status}] sig={mark}  summary={body.get('summary')!r}")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Step 1: discover ===")
    card = discover(B_BASE)
    assert any(s["id"] == "summarize" for s in card["skills"]), "summarize skill missing"

    TEXT = (
        "Agents talking to agents is the future of software. "
        "Each handoff must be authenticated. "
        "Rate limits prevent denial-of-service floods."
    )

    print("\n=== Steps 2 & 3: dispatch + verify (6 requests — last should 429) ===")
    for i in range(6):
        status, response = dispatch("summarize", {"text": TEXT})
        print(f"  request {i + 1}:", end=" ")
        handle(status, response)
