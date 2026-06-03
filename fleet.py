"""
Lab 11 — Orchestrate a Fleet

Pattern: plan upfront → fan-out workers in parallel → barrier → gate → synthesize.

Workers simulate research agents scanning the codebase for findings about each
lab topic. The gate is adversarial — it fails anything missing required fields.
"""
import asyncio
import random
import time

# ---------------------------------------------------------------------------
# Step 1 — Plan upfront: enumerate ALL work before spawning anyone
# ---------------------------------------------------------------------------

SPECS = [
    {"id": "lab-01", "topic": "typed-result",       "file": "result.py"},
    {"id": "lab-02", "topic": "mcp-server",          "file": "server.py"},
    {"id": "lab-03", "topic": "schema-quality",      "file": "schema_server.py"},
    {"id": "lab-04", "topic": "discoverability",     "file": "discovery_server.py"},
    {"id": "lab-05", "topic": "scoped-auth",         "file": "scoped_server.py"},
    {"id": "lab-06", "topic": "memory-persistence",  "file": "memory_store.py"},
    {"id": "lab-07", "topic": "memory-mixes",        "file": "memory_mix.py"},
    {"id": "lab-08", "topic": "context-engineering", "file": "context_engineer.py"},
    {"id": "lab-09", "topic": "meta-prompting",      "file": "optimize.py"},
    {"id": "lab-10", "topic": "agent-handoff",       "file": "agent_b.py"},
]

# Simulate one bad worker that returns an incomplete result
_SABOTAGED = {"lab-07"}

REQUIRED = ("id", "topic", "claim", "evidence", "file")


async def worker(spec: dict) -> dict:
    """
    Simulate a research worker: reads the target file and returns a finding.
    Runs with a small random delay to show true parallelism.
    """
    await asyncio.sleep(random.uniform(0.05, 0.2))

    import os
    path = os.path.join(os.path.dirname(__file__), spec["file"])
    exists = os.path.exists(path)

    if spec["id"] in _SABOTAGED:
        # Missing required fields — gate will catch this
        return {"id": spec["id"], "topic": spec["topic"]}

    return {
        "id":       spec["id"],
        "topic":    spec["topic"],
        "file":     spec["file"],
        "claim":    f"{spec['topic']} is implemented in {spec['file']}",
        "evidence": "file present on disk" if exists else "file missing",
        "exists":   exists,
    }


async def run_fleet() -> list[dict]:
    """Fan-out all workers simultaneously; barrier at gather()."""
    t0 = time.monotonic()
    results = await asyncio.gather(*[worker(spec) for spec in SPECS])
    elapsed = time.monotonic() - t0
    print(f"[fleet] {len(results)} workers finished in {elapsed:.2f}s (parallel)")
    return list(results)


# ---------------------------------------------------------------------------
# Step 2 — Gate: adversarial quality check, separate from the workers
# ---------------------------------------------------------------------------

def gate(results: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Validate every result against REQUIRED invariants.
    Returns (passed, kicked_back).
    The gate works *against* the workers — any missing field is a failure.
    """
    passed, kicked = [], []
    for r in results:
        missing = [f for f in REQUIRED if f not in r]
        if missing:
            r["_gate_reason"] = f"missing fields: {missing}"
            kicked.append(r)
        else:
            passed.append(r)
    return passed, kicked


# ---------------------------------------------------------------------------
# Step 3 — Synthesize from passed results only
# ---------------------------------------------------------------------------

def synthesize(passed: list[dict]) -> str:
    """Merge and deduplicate passing results into a final report."""
    present  = [r for r in passed if r.get("exists")]
    absent   = [r for r in passed if not r.get("exists")]

    lines = [
        f"=== Fleet Report ({len(passed)} passed / {len(SPECS)} total) ===",
        "",
        f"Labs implemented ({len(present)}):",
    ]
    for r in sorted(present, key=lambda x: x["id"]):
        lines.append(f"  ✓  {r['id']:10s}  {r['file']}")

    if absent:
        lines += ["", f"Labs missing files ({len(absent)}):"]
        for r in sorted(absent, key=lambda x: x["id"]):
            lines.append(f"  ✗  {r['id']:10s}  {r['file']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main conductor
# ---------------------------------------------------------------------------

async def main() -> None:
    print(f"[conductor] planning {len(SPECS)} workers, launching all at once\n")

    results        = await run_fleet()
    passed, kicked = gate(results)

    print(f"[gate]  passed={len(passed)}  kicked={len(kicked)}")
    for r in kicked:
        print(f"  [KICK] {r['id']} — {r.get('_gate_reason')}")

    print()
    print(synthesize(passed))


if __name__ == "__main__":
    asyncio.run(main())
