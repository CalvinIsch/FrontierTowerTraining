from __future__ import annotations
import json
import time
from fetch_user import fetch_user
from result import AUTH_EXPIRED, RATE_LIMIT, NOT_FOUND

TELEMETRY_FILE = "kernel_telemetry.jsonl"


def _log(verb: str, ok: bool, error_kind: str | None, elapsed_ms: float) -> None:
    line = json.dumps({"verb": verb, "ok": ok, "error_kind": error_kind, "ms": round(elapsed_ms, 2)})
    with open(TELEMETRY_FILE, "a") as f:
        f.write(line + "\n")


def call_fetch_user(user_id: int) -> None:
    t0 = time.monotonic()
    r = fetch_user(user_id)
    elapsed = (time.monotonic() - t0) * 1000
    _log("fetch_user", r.ok, r.error_kind, elapsed)

    if r.ok:
        print(f"[OK] user={r.value}")
        return

    if r.error_kind == AUTH_EXPIRED:
        print(f"[AUTH_EXPIRED] Re-authenticating... ({r.error})")
    elif r.error_kind == RATE_LIMIT:
        print(f"[RATE_LIMIT] Backing off... ({r.error})")
    elif r.error_kind == NOT_FOUND:
        print(f"[NOT_FOUND] Skipping user {user_id} — {r.error}")
    else:
        print(f"[TRANSIENT] Will retry later — {r.error}")


if __name__ == "__main__":
    import random
    random.seed(0)
    for _ in range(5):
        call_fetch_user(user_id=1)
    print(f"\nTelemetry written to {TELEMETRY_FILE}")
