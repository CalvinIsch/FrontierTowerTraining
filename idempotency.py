"""
Lab 13 — Idempotency for Safe Retries  (Step 3)

Crashes and restarts cause duplicate side-effects (double emails, double bookings).
Solution: derive a key from the action details, claim it before executing,
record in an append-only ledger after success. Retry becomes a no-op.

Dedup windows:
  login links  → 60 seconds
  invites      → 30 days
  default      → 24 hours
"""
import hashlib
import json
import os
import time

LEDGER_FILE = os.path.join(os.path.dirname(__file__), "idempotency_ledger.jsonl")
CLAIMS_FILE = os.path.join(os.path.dirname(__file__), "idempotency_claims.json")

WINDOWS = {
    "login_link": 60,
    "invite":     30 * 24 * 3600,
    "default":    24 * 3600,
}


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

def idem_key(recipient: str, action: str, window: str = "default") -> str:
    """
    Derive a stable idempotency key from (recipient, action, current window).
    The window buckets time so the same action can repeat in the next period.
    """
    secs  = WINDOWS.get(window, WINDOWS["default"])
    bucket = int(time.time()) // secs
    raw   = f"{action}:{recipient}:{bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Claim — only one process wins; returns False if already claimed
# ---------------------------------------------------------------------------

def _load_claims() -> dict:
    if not os.path.exists(CLAIMS_FILE):
        return {}
    with open(CLAIMS_FILE) as f:
        return json.load(f)


def _save_claims(claims: dict) -> None:
    tmp = CLAIMS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(claims, f, indent=2)
    os.replace(tmp, CLAIMS_FILE)


def claim(key: str, meta: dict) -> bool:
    """
    Atomically reserve an idempotency key.
    Returns True if this process won the claim, False if already taken.
    """
    claims = _load_claims()
    if key in claims:
        return False
    claims[key] = {"ts": time.time(), **meta}
    _save_claims(claims)
    return True


# ---------------------------------------------------------------------------
# Ledger — append-only record of completed side-effects
# ---------------------------------------------------------------------------

def record(key: str, action: str, recipient: str, result: str) -> None:
    """Append a completed action to the ledger (never overwrites)."""
    entry = json.dumps({
        "key": key, "action": action,
        "recipient": recipient, "result": result,
        "ts": time.time(),
    })
    with open(LEDGER_FILE, "a") as f:
        f.write(entry + "\n")


def already_done(key: str) -> bool:
    """Check the ledger — True if this key was already successfully executed."""
    if not os.path.exists(LEDGER_FILE):
        return False
    with open(LEDGER_FILE) as f:
        return any(
            json.loads(l).get("key") == key
            for l in f if l.strip()
        )


# ---------------------------------------------------------------------------
# Safe send — the full pattern in one function
# ---------------------------------------------------------------------------

def safe_send(action: str, recipient: str, window: str = "default") -> dict:
    """
    Execute an action exactly once per dedup window.
    Returns {"status": "sent"|"skipped", "key": ...}
    """
    key = idem_key(recipient, action, window)

    # 1. Check the ledger first (survives crashes)
    if already_done(key):
        return {"status": "skipped", "reason": "already done", "key": key}

    # 2. Claim the key (prevents concurrent duplicates)
    if not claim(key, {"action": action, "recipient": recipient}):
        return {"status": "skipped", "reason": "claimed by another process", "key": key}

    # 3. Execute the side-effect (replace with real send logic)
    print(f"  → sending {action!r} to {recipient!r}")

    # 4. Record success in the append-only ledger
    record(key, action, recipient, "ok")
    return {"status": "sent", "key": key}


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== First send (should execute) ===")
    r = safe_send("welcome_email", "alice@example.com")
    print(" ", r)

    print("\n=== Retry (crash simulation — should skip) ===")
    r = safe_send("welcome_email", "alice@example.com")
    print(" ", r)

    print("\n=== Different recipient (should execute) ===")
    r = safe_send("welcome_email", "bob@example.com")
    print(" ", r)

    print("\n=== Login link (60s window — should execute) ===")
    r = safe_send("login_link", "alice@example.com", window="login_link")
    print(" ", r)

    print("\n=== Login link retry (same 60s window — should skip) ===")
    r = safe_send("login_link", "alice@example.com", window="login_link")
    print(" ", r)

    print("\n=== Ledger contents ===")
    with open(LEDGER_FILE) as f:
        for line in f:
            entry = json.loads(line)
            print(f"  {entry['key']}  {entry['action']:15s}  {entry['recipient']}")
