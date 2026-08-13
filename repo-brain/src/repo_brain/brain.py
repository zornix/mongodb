"""The shared memory layer: lessons stored in Atlas, retrieved via Vector Search.

Lesson document shape (agreed pre-event, implemented at the event):
    {
        "type": "convention" | "past_fix" | "gotcha",
        "rule": "Error responses use the {'error': {'code', 'message'}} envelope",
        "evidence": "<reviewer comment or diff excerpt that produced this lesson>",
        "source_task": "add-items-endpoint",
        "embedding": [...],          # EMBEDDING_DIMS floats over `rule`
        "hit_count": 0,              # incremented on retrieval — the demo stat
        "created_at": <datetime>,
    }

STUBS ONLY — implemented during the hackathon.
"""


def embed(text: str) -> list[float]:
    """Embed `text` with EMBEDDING_MODEL."""
    raise NotImplementedError("event-day work")


def add_lesson(type_: str, rule: str, evidence: str, source_task: str) -> str:
    """Insert a lesson (with embedding). Returns inserted id."""
    raise NotImplementedError("event-day work")


def distill_lessons(review_feedback: str, source_task: str) -> list[str]:
    """LLM call: turn raw reviewer feedback into 0..n durable lessons, store them."""
    raise NotImplementedError("event-day work")


def search_lessons(task_description: str, k: int = 5) -> list[dict]:
    """Vector-search lessons relevant to a task; bump hit_count on returned docs."""
    raise NotImplementedError("event-day work")


def stats() -> dict:
    """Lesson counts, total hits, per-task correction cycles — feeds the demo stats line."""
    raise NotImplementedError("event-day work")
