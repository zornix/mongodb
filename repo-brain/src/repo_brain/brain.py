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
"""

import json
import time
from datetime import datetime, timezone
from functools import lru_cache

import voyageai
from langchain_google_genai import ChatGoogleGenerativeAI

from repo_brain.config import (
    EMBEDDING_DIMS,
    EMBEDDING_MODEL,
    GEMINI_MODEL,
    LESSONS_COLLECTION,
    VECTOR_INDEX_NAME,
    db,
)

RUNS_COLLECTION = "runs"  # written by crew.run_task, read by stats()

LESSON_TYPES = ("convention", "past_fix", "gotcha")

_DISTILL_PROMPT = """\
You maintain the long-term memory of an AI coding crew working in one repository.
Below is the accumulated reviewer feedback from one task. Extract the DURABLE lessons:
rules that will apply to future tasks in this repo, not one-off remarks about this diff.

Return ONLY a JSON array (no prose, no markdown fences). Each element:
  {{"type": "convention" | "past_fix" | "gotcha",
   "rule": "<one imperative sentence, self-contained, repo-general>",
   "evidence": "<short quote or paraphrase of the feedback that proves it>"}}

Return [] if nothing durable. Do not invent rules the feedback doesn't support.

Reviewer feedback for task "{source_task}":
{review_feedback}
"""


@lru_cache(maxsize=1)
def _voyage() -> voyageai.Client:
    return voyageai.Client()  # reads VOYAGE_API_KEY


def _lessons():
    return db()[LESSONS_COLLECTION]


def embed(text: str) -> list[float]:
    """Embed `text` with EMBEDDING_MODEL."""
    # Free-tier Voyage keys are capped at 3 requests/minute — wait out the window
    # instead of crashing mid-demo.
    for attempt in range(3):
        try:
            result = _voyage().embed(
                [text], model=EMBEDDING_MODEL, output_dimension=EMBEDDING_DIMS
            )
            return result.embeddings[0]
        except voyageai.error.RateLimitError:
            if attempt == 2:
                raise
            time.sleep(25)


def add_lesson(type_: str, rule: str, evidence: str, source_task: str) -> str:
    """Insert a lesson (with embedding). Returns inserted id."""
    doc = {
        "type": type_,
        "rule": rule,
        "evidence": evidence,
        "source_task": source_task,
        "embedding": embed(rule),
        "hit_count": 0,
        "created_at": datetime.now(timezone.utc),
    }
    return str(_lessons().insert_one(doc).inserted_id)


def distill_lessons(review_feedback: str, source_task: str) -> list[str]:
    """LLM call: turn raw reviewer feedback into 0..n durable lessons, store them."""
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0)
    response = llm.invoke(
        _DISTILL_PROMPT.format(source_task=source_task, review_feedback=review_feedback)
    )
    raw = response.text.strip()  # .content is a list of blocks — .text joins them
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.removeprefix("json").strip()
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []

    ids = []
    for item in items:
        if not isinstance(item, dict) or not item.get("rule"):
            continue
        type_ = item.get("type") if item.get("type") in LESSON_TYPES else "convention"
        ids.append(add_lesson(type_, item["rule"], item.get("evidence", ""), source_task))
    return ids


def search_lessons(task_description: str, k: int = 5) -> list[dict]:
    """Vector-search lessons relevant to a task; bump hit_count on returned docs."""
    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": embed(task_description),
                "numCandidates": max(50, k * 10),
                "limit": k,
            }
        },
        {"$project": {"embedding": 0}},
        {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
    ]
    docs = list(_lessons().aggregate(pipeline))
    if docs:
        _lessons().update_many(
            {"_id": {"$in": [d["_id"] for d in docs]}}, {"$inc": {"hit_count": 1}}
        )
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs


def list_lessons(limit: int = 50) -> list[dict]:
    """All lessons, newest first — no retrieval side effects (unlike search_lessons,
    this does not bump hit_count). Used by `crew brain` to dump the full list without
    corrupting the hit-count stat that `stats()` reports."""
    docs = list(_lessons().find({}, {"embedding": 0}).sort("created_at", -1).limit(limit))
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs


def stats() -> dict:
    """Lesson counts, total hits, per-task correction cycles — feeds the demo stats line."""
    by_type = {
        row["_id"]: row["n"]
        for row in _lessons().aggregate([{"$group": {"_id": "$type", "n": {"$sum": 1}}}])
    }
    hits = list(_lessons().aggregate([{"$group": {"_id": None, "hits": {"$sum": "$hit_count"}}}]))
    runs = [
        {"task": r.get("task"), "cycles": r.get("cycles")}
        for r in db()[RUNS_COLLECTION].find({}, {"_id": 0, "task": 1, "cycles": 1})
    ]
    return {
        "lessons_total": sum(by_type.values()),
        "lessons_by_type": by_type,
        "total_hits": hits[0]["hits"] if hits else 0,
        "runs": runs,
    }
