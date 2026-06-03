"""
Lab 12 — Reverse a Closed API

Four-layer pattern:
  Layer 1  sessions/          — captured cookie store (atomic save/load)
  Layer 2  _replay()          — curl_cffi with Chrome TLS impersonation
  Layer 3  get_notes()        — typed Result, error taxonomy
  Layer 4  CLI __main__       — JSON output agents can consume

Demo target: httpbin.org (safe public service, no real credentials needed).
Replace BASE_URL and _build_headers() with your real target's details.

Ethics: personal-use scale only, on accounts you own, respecting terms of service.
"""
import json
import os
import sys
from dataclasses import dataclass, field

from curl_cffi import requests as cffi_requests

# ---------------------------------------------------------------------------
# Configuration — swap these for your real target
# ---------------------------------------------------------------------------

SITE     = "httpbin"
BASE_URL = "https://httpbin.org"
SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "sessions")
SESSION_FILE = os.path.join(SESSIONS_DIR, f"{SITE}.json")

os.makedirs(SESSIONS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Layer 1 — Session store (atomic save, empty-value guard)
# ---------------------------------------------------------------------------

def save_session(cookies: dict) -> None:
    """
    Atomically persist cookies. Rejects any empty-string values upfront —
    an empty string slips past 'is the cookie set' checks then causes
    every subsequent request to fail with 403.
    """
    bad = [k for k, v in cookies.items() if not isinstance(v, str) or not v.strip()]
    if bad:
        raise ValueError(f"Refusing to save empty cookie values for keys: {bad}")

    tmp = SESSION_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)
    os.replace(tmp, SESSION_FILE)  # atomic — safe against mid-write crashes


def load_session() -> dict:
    """Load saved cookies, or return empty dict if no session exists."""
    if not os.path.exists(SESSION_FILE):
        return {}
    with open(SESSION_FILE, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Layer 2 — Replay with curl_cffi (Chrome TLS impersonation)
# ---------------------------------------------------------------------------

def _build_headers(cookies: dict) -> dict:
    """
    Construct the headers your target expects.
    Replace with headers captured from DevTools for a real site.
    """
    return {
        "Accept":          "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Site":  "same-origin",
        "Sec-Fetch-Mode":  "cors",
        # Real sites often require a CSRF token extracted from cookies, e.g.:
        # "X-Csrf-Token": cookies.get("csrf_token", ""),
    }


def _replay(path: str, cookies: dict) -> tuple[int, dict | None]:
    """
    Make an authenticated GET using Chrome's TLS fingerprint.
    Returns (status_code, parsed_body_or_None).
    """
    session = cffi_requests.Session(impersonate="chrome120")
    session.cookies.update(cookies)
    session.headers.update(_build_headers(cookies))

    try:
        resp = session.get(f"{BASE_URL}{path}", timeout=10)
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:200]}
        return resp.status_code, body
    except Exception as exc:
        return 0, {"_error": str(exc)}


# ---------------------------------------------------------------------------
# Layer 3 — Typed Result (same taxonomy as Lab 01)
# ---------------------------------------------------------------------------

@dataclass
class Result:
    data:       dict | None = None
    error:      str         = ""
    error_kind: str         = ""

    @property
    def ok(self) -> bool:
        return self.error_kind == "" and self.data is not None


def _classify(status: int) -> str:
    if status in (401, 403): return "auth_expired"
    if status == 429:        return "rate_limit"
    return "transient"


def get_notes() -> Result:
    """
    Layer 3 verb: fetch the /get endpoint (simulates a 'get notes' call).
    Wraps every outcome in a typed Result — never raises.
    """
    cookies = load_session()

    status, body = _replay("/get", cookies)

    if status == 200:
        # Extract a meaningful subset — on a real site this would parse
        # the actual response schema
        notes = [
            f"TLS impersonation: chrome120",
            f"cookies sent: {list(cookies.keys()) or ['(none — no session saved)']}"
        ]
        if "headers" in body:
            ua = body["headers"].get("User-Agent", "")
            notes.append(f"user-agent seen by server: {ua[:60]}")
        return Result(data={"notes": notes})

    if status == 0:
        msg = body.get("_error", "connection failed")
        return Result(error=msg, error_kind="transient")

    return Result(
        error=f"HTTP {status}",
        error_kind=_classify(status),
    )


# ---------------------------------------------------------------------------
# Layer 4 — CLI (agents consume the JSON output)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Demo: save a fake session, then call the verb
    if "--save-demo-session" in sys.argv:
        save_session({"session_id": "demo-abc123", "csrf_token": "tok-xyz"})
        print(json.dumps({"saved": SESSION_FILE}))
        sys.exit(0)

    r = get_notes()
    print(json.dumps({
        "ok":         r.ok,
        "error_kind": r.error_kind,
        "error":      r.error,
        "notes":      r.data.get("notes") if r.data else None,
    }, indent=2))
