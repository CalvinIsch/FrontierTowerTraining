"""
Lab 07 — Memory Mixes

Four distinct stores, one composition layer, episodic-to-semantic promotion.

  Working    → RAM dict          (volatile, per-turn)
  Episodic   → episodes.jsonl    (append-only log)
  Semantic   → facts.json        (durable verified facts)
  Procedural → rules.md          (standing rules, loaded every turn)
"""
import json
import os
import re
import time
from collections import Counter

BASE = os.path.dirname(__file__)

EPISODES_FILE  = os.path.join(BASE, "episodes.jsonl")
FACTS_FILE     = os.path.join(BASE, "facts.json")
RULES_FILE     = os.path.join(BASE, "rules.md")


class MemoryMix:
    # ------------------------------------------------------------------
    # Working memory — RAM only, lost when the program ends
    # ------------------------------------------------------------------

    def __init__(self):
        self._tasks: list[str] = []

    def set_task(self, *items: str) -> None:
        """Replace the current to-do list."""
        self._tasks = list(items)

    def check_off(self, item: str) -> None:
        """Remove a completed item from working memory."""
        self._tasks = [t for t in self._tasks if t != item]

    # ------------------------------------------------------------------
    # Episodic memory — append-only JSONL log
    # ------------------------------------------------------------------

    def log_episode(self, event: str, detail: str = "") -> None:
        """Append one event to the episodic log."""
        record = {"ts": time.time(), "event": event, "detail": detail}
        with open(EPISODES_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")

    def episodes(self, n: int = 10) -> list[dict]:
        """Return the n most recent episodes."""
        if not os.path.exists(EPISODES_FILE):
            return []
        with open(EPISODES_FILE) as f:
            lines = [l.strip() for l in f if l.strip()]
        return [json.loads(l) for l in lines[-n:]]

    # ------------------------------------------------------------------
    # Semantic memory — durable facts dict
    # ------------------------------------------------------------------

    def write_fact(self, key: str, value: str) -> None:
        """Upsert a fact into the semantic store."""
        facts = self._facts()
        facts[key] = value
        with open(FACTS_FILE, "w") as f:
            json.dump(facts, f, indent=2)

    def _facts(self) -> dict:
        if not os.path.exists(FACTS_FILE):
            return {}
        with open(FACTS_FILE) as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Procedural memory — rules loaded fresh every turn
    # ------------------------------------------------------------------

    def rules(self) -> str:
        """Return the standing rules. If none exist, return a sensible default."""
        if not os.path.exists(RULES_FILE):
            return "# Rules\n- Always verify before acting.\n- Prefer existing tools.\n"
        with open(RULES_FILE) as f:
            return f.read()

    # ------------------------------------------------------------------
    # Step 2 — Compose the turn prompt
    # ------------------------------------------------------------------

    def assemble(self, task: str, budget_chars: int = 1200) -> str:
        """
        Build a context string in priority order:
          1. Procedural  — rules always apply
          2. Semantic    — facts relevant to this task
          3. Episodic    — recent events
          4. Working     — current to-do (also repeated at end)

        Trims from the middle when over budget.
        Recites working state last (Manus recitation trick).
        """
        todo_block = (
            "## To-Do\n" + "\n".join(f"- {t}" for t in self._tasks) + "\n"
            if self._tasks else ""
        )

        # Semantic: include facts whose key overlaps with task words
        task_words = set(task.lower().split())
        relevant_facts = {
            k: v for k, v in self._facts().items()
            if task_words & set(k.lower().replace("-", " ").split())
        }
        if not relevant_facts:
            relevant_facts = self._facts()   # fall back to all facts

        facts_block = ""
        if relevant_facts:
            facts_block = "## Facts\n" + "".join(
                f"- {k}: {v}\n" for k, v in relevant_facts.items()
            )

        # Episodic: last 5 events
        recent = self.episodes(5)
        epi_block = ""
        if recent:
            epi_block = "## Recent Events\n" + "".join(
                f"- {e['event']}: {e['detail']}\n" for e in recent
            )

        # Assemble in order: procedural → semantic → episodic → working
        sections = [
            ("rules",    self.rules()),
            ("todo",     todo_block),
            ("facts",    facts_block),
            ("episodes", epi_block),
            ("working",  todo_block),   # recited again at end
        ]

        # Trim middle sections if over budget
        core = sections[0][1] + sections[-1][1]   # rules + final todo (never trim)
        middle = [(k, v) for k, v in sections[1:-1] if v]
        used = len(core)
        kept_middle = []
        for _, v in middle:
            if used + len(v) <= budget_chars:
                kept_middle.append(v)
                used += len(v)
            # else: silently drop this middle block

        parts = [sections[0][1]] + kept_middle + [sections[-1][1]]
        return "\n".join(p for p in parts if p).strip()

    # ------------------------------------------------------------------
    # Step 3 — Promote recurring episodic facts to semantic memory
    # ------------------------------------------------------------------

    def promote_recurring(self, min_count: int = 2) -> list[str]:
        """
        Scan episodic logs for events that appear at least min_count times.
        Verify any file paths still exist (Lab 06 freshness guard).
        Promote verified recurring facts into semantic memory.
        Returns a list of promoted keys.
        """
        if not os.path.exists(EPISODES_FILE):
            return []

        with open(EPISODES_FILE) as f:
            records = [json.loads(l) for l in f if l.strip()]

        counts = Counter(r["event"] for r in records)
        recurring = {ev: cnt for ev, cnt in counts.items() if cnt >= min_count}

        promoted = []
        for event, count in recurring.items():
            # Grab the most recent detail for this event
            detail = next(
                (r["detail"] for r in reversed(records) if r["event"] == event), ""
            )

            # Freshness guard: check any paths mentioned in the detail
            paths = re.findall(r"[\w./\-]+\.(?:sh|py|yaml|yml|json|toml|env|txt)", detail)
            stale = [p for p in paths if not os.path.exists(p)]
            if stale:
                print(f"  [SKIP] '{event}' — stale paths: {stale}")
                continue

            key = event.lower().replace(" ", "-")
            value = f"{detail} (seen {count}x)"
            self.write_fact(key, value)
            promoted.append(key)
            print(f"  [PROMOTE] '{key}' → semantic memory")

        return promoted


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Write standing rules
    with open(RULES_FILE, "w") as f:
        f.write(
            "# Rules\n"
            "- Always verify a fact before acting on it.\n"
            "- Prefer typed Results over raw dicts.\n"
            "- Never expose a secret in a log line.\n"
        )

    mm = MemoryMix()

    print("=== Step 1: populate all four stores ===")

    # Working
    mm.set_task("fetch user record", "classify error", "write telemetry")
    print("working:", mm._tasks)

    # Episodic
    mm.log_episode("deploy-succeeded", "scripts/deploy.sh --env production")
    mm.log_episode("fetch-failed", "HTTP 429 on user 42")
    mm.log_episode("deploy-succeeded", "scripts/deploy.sh --env production")
    mm.log_episode("fetch-failed", "HTTP 404 on user 99")
    mm.log_episode("deploy-succeeded", "scripts/deploy.sh --env production")
    print(f"episodes logged: {len(mm.episodes(10))}")

    # Semantic
    mm.write_fact("package-manager", "pnpm — never use npm")
    mm.write_fact("error-taxonomy", "AUTH_EXPIRED / RATE_LIMIT / NOT_FOUND / TRANSIENT")
    print("facts:", list(mm._facts().keys()))

    print("\n=== Step 2: assembled prompt (budget=900) ===")
    mm.set_task("fetch user record", "write telemetry")
    prompt = mm.assemble("fetch user error", budget_chars=900)
    print(prompt)

    print("\n=== Step 3: promote recurring episodic facts ===")
    promoted = mm.promote_recurring(min_count=2)
    print("promoted keys:", promoted)
    print("semantic store now:", mm._facts())
