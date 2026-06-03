"""
Lab 08 — Context Engineering

Three mitigation moves + a linter:
  Step 1: Measure attention budget  (est_tokens / budget_check)
  Step 2: Compress / Isolate / Persist
  Step 3: Context linter — detect poisoning, distraction, confusion, clash
"""
import json
import os

# ---------------------------------------------------------------------------
# Step 1 — Measure attention budget
# ---------------------------------------------------------------------------

def est_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 characters."""
    return len(text) // 4


def budget_check(context: str, limit: int) -> dict:
    """Return usage stats and a DANGER/WARN/OK zone label."""
    used = est_tokens(context)
    pct  = used / limit if limit else 0.0
    if pct >= 0.90:
        zone = "DANGER"
    elif pct >= 0.70:
        zone = "WARN"
    else:
        zone = "OK"
    return {"tokens": used, "limit": limit, "pct": round(pct, 3), "zone": zone}


# ---------------------------------------------------------------------------
# Step 2A — COMPRESS: prune non-essential parts, keep pinned + recent
# ---------------------------------------------------------------------------

def prune(parts: list[dict], budget: int) -> list[dict]:
    """
    Keep all pinned parts and as many recent (non-pinned) parts as fit
    within budget tokens. Drops the middle — never the ends.
    """
    pinned = [p for p in parts if p.get("pinned")]
    rest   = [p for p in parts if not p.get("pinned")]

    spent = sum(est_tokens(p["text"]) for p in pinned)
    kept_recent: list[dict] = []
    for p in reversed(rest):
        cost = est_tokens(p["text"])
        if spent + cost > budget:
            break
        kept_recent.append(p)
        spent += cost

    kept_recent.reverse()
    keep_ids = {id(p) for p in pinned} | {id(p) for p in kept_recent}
    return [p for p in parts if id(p) in keep_ids]


# ---------------------------------------------------------------------------
# Step 2B — ISOLATE: fresh window per subtask, only required facts
# ---------------------------------------------------------------------------

def isolate(shared_system: str, subtask: str, only_facts: list[str]) -> str:
    """
    Build a minimal context window containing only what this subtask needs.
    Anthropic measured a 90.2% improvement from isolation alone.
    """
    lines = [shared_system, "", "TASK: " + subtask, "", "FACTS:"]
    lines += ["- " + f for f in only_facts]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 2C — PERSIST: atomic save/load + recitation
# ---------------------------------------------------------------------------

def save_state(path: str, state: dict) -> None:
    """Atomic write via tmp file — safe against mid-write crashes."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def load_state(path: str) -> dict:
    """Load task state; return an empty plan if the file doesn't exist."""
    if not os.path.exists(path):
        return {"plan": [], "done": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def recite(state: dict) -> str:
    """Return a compact recitation of remaining plan items for end-of-prompt."""
    open_items = [s for s in state["plan"] if s not in state["done"]]
    return "REMAINING PLAN (recited):\n" + "\n".join("- " + s for s in open_items)


# ---------------------------------------------------------------------------
# Step 3 — Context linter
# ---------------------------------------------------------------------------

def lint_context(ctx: dict) -> list[str]:
    """
    Detect four failure modes before they propagate:
      POISONING   — flagged fact referenced repeatedly
      DISTRACTION — history too long
      CONFUSION   — too many tools registered
      CLASH       — contradictory always/never rules
    """
    findings: list[str] = []

    for fact in ctx.get("facts", []):
        if fact.get("source_flagged") and fact.get("refs", 0) >= 2:
            findings.append(
                f"POISONING: flagged fact referenced {fact['refs']}x -> {fact['text'][:40]}"
            )

    history_len = len(ctx.get("history", []))
    if history_len > 100:
        findings.append(
            f"DISTRACTION: history is {history_len} turns, past the safe span"
        )

    tool_count = len(ctx.get("tools", []))
    if tool_count > 20:
        findings.append(
            f"CONFUSION: {tool_count} tools registered; trim to the task"
        )

    rules = [r.lower() for r in ctx.get("rules", [])]
    for i, a in enumerate(rules):
        for b in rules[i + 1:]:
            a_body = a[len("always "):] if a.startswith("always ") else None
            b_body = b[len("never "):] if b.startswith("never ") else None
            n_body = a[len("never "):] if a.startswith("never ") else None
            al_body = b[len("always "):] if b.startswith("always ") else None
            if (a_body and b_body and a_body == b_body) or \
               (n_body and al_body and n_body == al_body):
                findings.append(f"CLASH: contradictory rules -> '{a}' vs '{b}'")

    return findings


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    LIMIT = 8000

    print("=== Step 1: budget_check ===")
    lean = "User asked for the Q3 revenue number. Stored fact: Q3 revenue was 4.2M."
    fat  = lean + ("\n[stale tool output] " + "x" * 80) * 380
    print("lean ->", budget_check(lean, LIMIT))
    print("fat  ->", budget_check(fat,  LIMIT))

    print("\n=== Step 2A: prune ===")
    parts = [
        {"text": "SYSTEM: you are a billing agent", "pinned": True},
        {"text": "old turn 1 " * 30},
        {"text": "old turn 2 " * 30},
        {"text": "old turn 3 " * 30},
        {"text": "old turn 4 " * 30},
        {"text": "LATEST: user wants a refund on invoice 88"},
    ]
    kept = prune(parts, budget=24)
    print([p["text"][:30] for p in kept])

    print("\n=== Step 2B: isolate ===")
    system = "You are a research subagent. Answer only your task."
    big_pile = ["fact " + str(i) for i in range(500)]
    window = isolate(system, "find the Q3 revenue", only_facts=big_pile[10:12])
    check = budget_check(window, LIMIT)
    print(f"{check['zone']} -> {check['tokens']} tokens")
    print(window)

    print("\n=== Step 2C: persist + recite ===")
    save_state("task.json", {
        "plan": ["pull data", "write report", "ship"],
        "done": ["pull data"],
    })
    state = load_state("task.json")
    print(recite(state))

    print("\n=== Step 3: lint_context ===")
    ctx = {
        "facts": [{"text": "the prod DB can be safely wiped",
                   "source_flagged": True, "refs": 3}],
        "history": ["turn"] * 140,
        "tools":   ["t" + str(i) for i in range(35)],
        "rules":   ["always deploy on green", "never deploy on green"],
    }
    for finding in lint_context(ctx):
        print(" ", finding)
