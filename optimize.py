"""
Lab 09 — Meta Prompting  (Steps 2 & 3)

optimize()      — score all variants, return ranked list
reflect_demo()  — find failures in winning prompt, add a fix, rescore
"""
import json
import re

# ---------------------------------------------------------------------------
# Signature & test cases
# ---------------------------------------------------------------------------

SIGNATURE = {
    "task":   "classify support tickets",
    "input":  "ticket: str",
    "output": '{"label": str, "confidence": float, "reason": str}',
}

TEST_CASES = [
    {"input": "My payment failed twice this week.",              "label": "billing"},
    {"input": "The app crashes when I open settings.",           "label": "bug"},
    {"input": "How do I export my data?",                        "label": "question"},
    {"input": "I want to cancel my subscription.",               "label": "account"},
    {"input": "Please add dark mode to the mobile app.",         "label": "feature"},
]

# ---------------------------------------------------------------------------
# Five variants — deliberately ranging from vague to precise
# ---------------------------------------------------------------------------

VARIANTS = [
    # 0: vague — no JSON instruction, no categories
    "Help the user with their support ticket.",

    # 1: mentions classification but no JSON, no categories
    "Classify the support ticket into an appropriate category.",

    # 2: asks for JSON but no categories listed
    (
        "Classify the support ticket. "
        "Return JSON with keys: label, confidence, reason."
    ),

    # 3: JSON + some categories but incomplete list
    (
        "Classify the support ticket as one of: billing, bug, question. "
        "Return JSON: {\"label\": ..., \"confidence\": ..., \"reason\": ...}"
    ),

    # 4: JSON + explicit categories — wins but missing "account" so cancel→billing
    (
        "Classify the support ticket into exactly one of these categories: "
        "billing, bug, question, feature. "
        "Return ONLY JSON with keys label (string), confidence (float 0-1), "
        "and reason (one sentence). No prose outside the JSON."
    ),
]

# ---------------------------------------------------------------------------
# Stub model — replaces a real LLM, enables offline testing
# ---------------------------------------------------------------------------

# Maps ticket keywords → correct label
_LABEL_MAP = {
    "payment": "billing", "failed": "billing", "invoice": "billing",
    "crash":   "bug",     "crashes": "bug",    "error": "bug",
    "how":     "question","export": "question", "where": "question",
    "cancel":  "account", "subscription": "account", "account": "account",
    "add":     "feature", "dark mode": "feature",   "please add": "feature",
}


def run_model(prompt: str, ticket: str) -> str:
    """
    Stub model: returns JSON only when the prompt explicitly requests it
    and lists categories; otherwise returns prose.
    """
    prompt_lower = prompt.lower()
    wants_json = "json" in prompt_lower or "return only" in prompt_lower
    has_categories = any(
        cat in prompt_lower for cat in ("billing", "bug", "question", "account", "feature")
    )

    # Derive the correct label from the ticket
    ticket_lower = ticket.lower()
    label = "question"  # default
    for kw, lbl in _LABEL_MAP.items():
        if kw in ticket_lower:
            label = lbl
            break

    # Vague / no-JSON prompts return prose
    if not wants_json:
        return f"This ticket appears to be about {label} issues. You should route it accordingly."

    # JSON but no category list → sometimes picks wrong category
    if not has_categories:
        guessed = label if label in ("billing", "bug", "question") else "question"
        return json.dumps({"label": guessed, "confidence": 0.7, "reason": "matched keyword"})

    # Prompt lists categories but omits "account" → cancel ticket misclassified
    if "account" not in prompt_lower and "cancel" in ticket_lower:
        return json.dumps({"label": "billing", "confidence": 0.6,
                           "reason": "subscription sounds like billing"})

    return json.dumps({"label": label, "confidence": 0.95,
                       "reason": f"ticket contains '{ticket.split()[0].lower()}' keyword"})


# ---------------------------------------------------------------------------
# Metric & scoring
# ---------------------------------------------------------------------------

def metric(response: str, expected_label: str) -> float:
    """Score one response: 0.0 (bad JSON) → 0.4 (missing keys) → 1.0 (correct)."""
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        return 0.0
    if not all(k in data for k in ("label", "confidence", "reason")):
        return 0.4
    return 1.0 if data["label"] == expected_label else 0.6


def score_prompt(prompt: str) -> float:
    """Average metric score across all test cases."""
    scores = [
        metric(run_model(prompt, tc["input"]), tc["label"])
        for tc in TEST_CASES
    ]
    return round(sum(scores) / len(scores), 3)


def optimize() -> list[tuple[int, float, str]]:
    """Score every variant and return a ranked list of (index, score, snippet)."""
    results = [
        (i, score_prompt(v), v[:60].replace("\n", " "))
        for i, v in enumerate(VARIANTS)
    ]
    return sorted(results, key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# Step 3 — Reflection & refinement
# ---------------------------------------------------------------------------

def failures(prompt: str) -> list[dict]:
    """Return test cases where the prompt scores below 1.0."""
    return [
        {**tc, "got": run_model(prompt, tc["input"])}
        for tc in TEST_CASES
        if metric(run_model(prompt, tc["input"]), tc["label"]) < 1.0
    ]


def reflect(prompt: str) -> str:
    """
    Examine failures and append a targeted fix rule.
    (In production an LLM writes this line; here we use pattern matching.)
    """
    missed = failures(prompt)
    fixes = []
    for case in missed:
        if "cancel" in case["input"].lower() or "subscription" in case["input"].lower():
            fixes.append(
                "- Add 'account' to the category list. "
                "Cancelling or managing a subscription is label=account, not billing."
            )
    if fixes:
        refined = prompt.replace(
            "billing, bug, question, feature",
            "billing, bug, question, account, feature",
        )
        return refined + "\n\nAdditional rules:\n" + "\n".join(dict.fromkeys(fixes))
    return prompt


def reflect_demo() -> None:
    """Show the full generate → score → reflect → rescore loop."""
    ranked = optimize()
    best_idx, best_score, _ = ranked[0]
    winner = VARIANTS[best_idx]

    print(f"Winner: variant {best_idx}  score={best_score}")
    print(f"Snippet: {winner[:80]}")

    print("\nFailures:")
    for f in failures(winner):
        try:
            got_label = json.loads(f["got"])["label"]
        except Exception:
            got_label = "(prose)"
        print(f"  input={f['input'][:50]!r}  want={f['label']}  got={got_label}")

    refined = reflect(winner)
    new_score = score_prompt(refined)
    print(f"\nAfter reflection: score {best_score} → {new_score}")
    print("Added rule:", [l for l in refined.splitlines() if "cancel" in l.lower()])


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Step 2: optimize ===")
    for idx, score, snippet in optimize():
        print(f"  variant {idx}  score={score}  '{snippet}...'")

    print("\n=== Step 3: reflect & refine ===")
    reflect_demo()
