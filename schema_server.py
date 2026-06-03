import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastmcp import FastMCP

mcp = FastMCP("schema-demo")

# ---------------------------------------------------------------------------
# Step 1: BAD schema — swap SHOW_BAD = True to see what agents receive
# ---------------------------------------------------------------------------
SHOW_BAD = False

if SHOW_BAD:
    @mcp.tool
    def proc(u, q, n=None):
        """proc"""
        notes = _STORE.get(u, [])
        if q:
            return [x for x in notes if q in x]
        if n:
            _STORE.setdefault(u, []).append(n)
            return True
        return notes

# ---------------------------------------------------------------------------
# Shared in-memory store (identical logic for both schema versions)
# ---------------------------------------------------------------------------
_STORE: dict[str, list[str]] = {}


# ---------------------------------------------------------------------------
# Step 2: GOOD schema — three explicit, well-named tools
# ---------------------------------------------------------------------------

@mcp.tool
def get_notes(user_id: str) -> list[str]:
    """Return all notes stored for a single user.

    Call this when you need to retrieve the complete note history for one
    specific user. Use search_notes instead when you want to query across
    all users.
    """
    return _STORE.get(user_id, [])


@mcp.tool
def search_notes(query: str) -> dict[str, list[str]]:
    """Search all users' notes for lines containing the query string.

    Call this when the user asks a broad question and you don't know which
    user's notes contain the answer. Returns a mapping of user_id → matching
    notes so the caller can route the result correctly.
    """
    return {uid: [n for n in notes if query in n]
            for uid, notes in _STORE.items()
            if any(query in n for n in notes)}


@mcp.tool
def add_note(user_id: str, note: str) -> bool:
    """Append a new note for the given user and confirm success.

    Call this whenever you need to persist a piece of information tied to a
    specific user. Returns True on success. The note is stored in insertion
    order and is immediately visible to get_notes and search_notes.
    """
    _STORE.setdefault(user_id, []).append(note)
    return True


# ---------------------------------------------------------------------------
# Step 3: Startup validation — fail fast if any tool lacks a description
# ---------------------------------------------------------------------------

def _validate_schemas(server: FastMCP) -> None:
    """Assert every registered tool has a non-empty description."""
    import asyncio
    tools = asyncio.run(server.list_tools())
    bad = [t.name for t in tools if not (t.description or "").strip()]
    assert not bad, (
        f"Schema validation failed — tools missing descriptions: {bad}\n"
        "Every tool needs a docstring that covers WHAT it does AND WHEN to call it."
    )


_validate_schemas(mcp)


if __name__ == "__main__":
    mcp.run()
