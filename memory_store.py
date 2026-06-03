"""
Lab 06 — Memory that Survives

Three capabilities:
  1. write_memory()       — persist a fact as a markdown file with frontmatter
  2. recall(query)        — retrieve the best-matching memory by description overlap
  3. verify_before_trust() — flag stale memories that reference missing files/flags/envvars
"""
import os
import re

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "memory")
INDEX_FILE = os.path.join(MEMORY_DIR, "MEMORY.md")

os.makedirs(MEMORY_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Step 1 — Write
# ---------------------------------------------------------------------------

def write_memory(name: str, description: str, mtype: str, body: str) -> str:
    """Persist a fact as memory/[name].md and register it in the index."""
    content = (
        f"---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"type: {mtype}\n"
        f"---\n\n"
        f"{body.strip()}\n"
    )
    path = os.path.join(MEMORY_DIR, f"{name}.md")
    with open(path, "w") as f:
        f.write(content)

    # Keep index entries unique (overwrite existing line for same name)
    entry = f"- [{name}]({name}.md) — {description}\n"
    lines = []
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE) as f:
            lines = f.readlines()
    lines = [l for l in lines if not re.match(rf"- \[{re.escape(name)}\]", l)]
    lines.append(entry)
    with open(INDEX_FILE, "w") as f:
        f.writelines(lines)

    return path


# ---------------------------------------------------------------------------
# Step 2 — Recall by relevance
# ---------------------------------------------------------------------------

def _score(description: str, query: str) -> int:
    """Word-overlap score between description and query (case-insensitive)."""
    q_words = set(query.lower().split())
    d_words = set(description.lower().split())
    return len(q_words & d_words)


def recall(query: str) -> str | None:
    """Return the body of the memory whose description best matches the query.

    Scans the cheap index first, opens only the single winning file.
    Returns None if no memories exist.
    """
    if not os.path.exists(INDEX_FILE):
        return None

    with open(INDEX_FILE) as f:
        lines = [l.strip() for l in f if l.strip().startswith("- [")]

    if not lines:
        return None

    # Parse "- [name](name.md) — description" lines
    best_name, best_score = None, -1
    for line in lines:
        m = re.match(r"- \[([^\]]+)\]\([^)]+\) — (.*)", line)
        if not m:
            continue
        name, desc = m.group(1), m.group(2)
        score = _score(desc, query)
        if score > best_score:
            best_score, best_name = score, name

    if best_name is None:
        return None

    path = os.path.join(MEMORY_DIR, f"{best_name}.md")
    if not os.path.exists(path):
        return None

    with open(path) as f:
        raw = f.read()

    # Strip YAML frontmatter (everything between the two --- fences)
    body = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.DOTALL).strip()
    return f"[memory:{best_name}]\n{body}"


# ---------------------------------------------------------------------------
# Step 3 — Freshness verification
# ---------------------------------------------------------------------------

# Patterns that represent verifiable claims about the live system
_PATH_RE  = re.compile(r"[\w./\-]+\.(?:sh|py|yaml|yml|json|toml|env|txt)")
_FLAG_RE  = re.compile(r"--[\w\-]+")
_ENVVAR_RE = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")


def verify_before_trust(body: str) -> dict:
    """
    Scan a recalled memory body for concrete claims (file paths, flags, env vars)
    and verify each against the live filesystem.

    Returns:
        {
          "trusted": bool,          # False if any claim failed verification
          "claims": [...],          # every claim found
          "stale": [...],           # claims that could not be verified
        }
    """
    claims = []
    stale  = []

    for m in _PATH_RE.finditer(body):
        path = m.group(0)
        claims.append({"kind": "path", "value": path})
        if not os.path.exists(path):
            stale.append({"kind": "path", "value": path, "reason": "file not found"})

    for m in _FLAG_RE.finditer(body):
        flag = m.group(0)
        claims.append({"kind": "flag", "value": flag})
        # Flags can't be filesystem-checked; mark as unverifiable but not stale
        # unless the memory explicitly tags them as file-backed

    for m in _ENVVAR_RE.finditer(body):
        var = m.group(0)
        # Skip common English words that happen to be uppercase
        if var in {"MEMORY", "TRUE", "FALSE", "NOTE", "AND", "THE", "FOR", "USE"}:
            continue
        claims.append({"kind": "envvar", "value": var})
        if os.environ.get(var) is None:
            stale.append({"kind": "envvar", "value": var, "reason": "not set in environment"})

    return {
        "trusted": len(stale) == 0,
        "claims":  claims,
        "stale":   stale,
    }


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    print("=== Step 1: write two memories ===")
    print(write_memory(
        name="package-manager",
        description="project uses pnpm as the package manager not npm or yarn",
        mtype="project",
        body="This project uses **pnpm** for all package management.\n"
             "Run `pnpm install` to set up dependencies.\n"
             "Never use `npm install` — it will create a conflicting lock file.",
    ))
    print(write_memory(
        name="deploy-script",
        description="production deployment runs via scripts/deploy.sh",
        mtype="project",
        body="Production deployments are triggered by running `scripts/deploy.sh`.\n"
             "The script requires the ENV_VAR `DEPLOY_TOKEN` to be set.\n"
             "Pass `--env production` to target the live environment.",
    ))
    # Plant a stale memory pointing to a file that does not exist
    print(write_memory(
        name="old-deploy",
        description="old deployment used scripts/old_deploy.sh before migration",
        mtype="project",
        body="Previously deployments ran via `scripts/old_deploy.sh --env staging`.\n"
             "This script was removed after the 2024 infra migration.",
    ))

    print("\n=== Step 2: recall by query ===")
    result = recall("how do I deploy to production")
    print(result)

    print("\n=== Step 3: verify freshness ===")
    for name in ("deploy-script", "old-deploy"):
        body_path = os.path.join(MEMORY_DIR, f"{name}.md")
        with open(body_path) as f:
            raw = f.read()
        body = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.DOTALL).strip()
        verdict = verify_before_trust(body)
        status = "TRUSTED" if verdict["trusted"] else "STALE"
        print(f"\n[{name}] → {status}")
        if verdict["stale"]:
            for s in verdict["stale"]:
                print(f"  stale {s['kind']}: {s['value']} — {s['reason']}")
