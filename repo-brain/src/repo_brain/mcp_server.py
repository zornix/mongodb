"""FastMCP server exposing the crew's brain to external agents (Claude Code, Codex).

Tools:
- search_lessons(query, k) -> lessons relevant to what the caller is working on
- add_lesson(type, rule, evidence) -> external agents can teach the crew too
- brain_stats() -> what the crew knows

Run: uv run python -m repo_brain.mcp_server   (stdio transport)
"""

from fastmcp import FastMCP

from repo_brain import brain

mcp = FastMCP("repo-brain")


@mcp.tool
def search_lessons(query: str, k: int = 5) -> list[dict]:
    """Retrieve lessons (conventions, past fixes, gotchas) relevant to a task."""
    return brain.search_lessons(query, k=k)


@mcp.tool
def add_lesson(type: str, rule: str, evidence: str = "") -> str:
    """Teach the crew a lesson. type: convention | past_fix | gotcha."""
    return brain.add_lesson(type, rule, evidence, source_task="mcp")


@mcp.tool
def brain_stats() -> dict:
    """Lesson counts, retrieval hits, and per-task correction cycles."""
    return brain.stats()


if __name__ == "__main__":
    mcp.run()
