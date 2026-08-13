"""The LangGraph crew: planner -> coder -> reviewer (loop until clean or max cycles).

Graph contract (agreed pre-event, implemented at the event):
- State: {task, plan, code, review_feedback, cycles, lessons_used}
  - review_feedback as returned by run_task() is list[str], one entry per correction
    cycle, in order (empty once clean) — cli.py renders one panel per cycle, and
    fake_state.py fixes that shape. Inside the graph the key holds only the current
    round (that's what the coder needs); run_task() swaps in the full history.
- coder node calls brain.search_lessons(task) BEFORE writing — the whole point
- reviewer node checks demo_target conventions; on violations, loops back to coder
- on approval, brain.distill_lessons(feedback) persists what was learned
- compiled with MongoDBSaver so any run can be killed and resumed by thread_id
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from repo_brain import brain
from repo_brain.config import (
    CHECKPOINTS_COLLECTION,
    GEMINI_MODEL,
    GOOGLE_API_KEY,
    MONGODB_DB,
    RUNS_COLLECTION,
    db,
    mongo_client,
)

MAX_CYCLES = 3
_DEMO_ROOT = Path(__file__).resolve().parents[2] / "demo_target"
_CONVENTIONS_PATH = _DEMO_ROOT / "CONVENTIONS.md"
_FILE_FORMAT = (
    "Output the full files to add, using this exact delimiter format and nothing else:\n"
    "=== FILE: demo_target/app/routes/<resource>.py ===\n"
    "<python>\n"
    "=== FILE: demo_target/tests/test_<resource>.py ===\n"
    "<python>\n"
    "=== FILE: demo_target/app/main.py ===\n"
    "<python — include existing health/widgets routers PLUS the new one>\n"
)


class CrewState(TypedDict, total=False):
    task: str
    plan: str
    code: str
    # In-graph this is the CURRENT round's feedback (what the coder must fix next);
    # the full per-cycle list lives in feedback_history. run_task() hands the CLI the
    # list under `review_feedback`, which is the shape cli.py/fake_state.py expect.
    review_feedback: str
    cycles: int
    lessons_used: list[dict[str, Any]]
    approved: bool
    feedback_history: list[str]
    lessons_written: list[str]


class Review(BaseModel):
    approved: bool
    issues: list[str] = Field(
        default_factory=list,
        description="At most two convention violations this pass. Empty if approved.",
    )
    feedback: str = Field(description="What the coder must change. Empty if approved.")


def _conventions() -> str:
    return _CONVENTIONS_PATH.read_text()


def _gold_standard() -> str:
    """widgets.py is the house style — shown to the coder only on revisions or with lessons."""
    route = (_DEMO_ROOT / "app" / "routes" / "widgets.py").read_text()
    tests = (_DEMO_ROOT / "tests" / "test_widgets.py").read_text()
    return (
        "Gold-standard resource (copy naming, error helper, response models, tests, imports):\n\n"
        f"=== FILE: demo_target/app/routes/widgets.py ===\n{route}\n"
        f"=== FILE: demo_target/tests/test_widgets.py ===\n{tests}\n"
    )


@lru_cache(maxsize=1)
def _chat_model() -> BaseChatModel:
    # Gemini only: brain.distill_lessons uses the same model, and the Anthropic/OpenAI
    # deps were dropped from pyproject when the brain lane standardised on Gemini.
    if not GOOGLE_API_KEY:
        raise RuntimeError("No LLM key set — fill GOOGLE_API_KEY (Gemini) in repo-brain/.env")
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0)


def _text(msg: Any) -> str:
    content = getattr(msg, "content", msg)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(str(part["text"]))
        return "".join(parts).strip()
    return str(content).strip()


def _complete(system: str, user: str) -> str:
    llm = _chat_model()
    last_exc: Exception | None = None
    for attempt in range(4):
        try:
            msg = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
            return _text(msg)
        except Exception as exc:  # Gemini free-tier 429s during rehearsal
            err = str(exc)
            if "RESOURCE_EXHAUSTED" not in err and "429" not in err:
                raise
            # Free tier has BOTH a per-minute and a per-day cap (20 requests/day/model).
            # Retrying a daily cap just burns 80s before failing — fail fast and say so.
            if "PerDay" in err or "per day" in err.lower():
                raise RuntimeError(
                    f"Gemini daily free-tier quota exhausted for {GEMINI_MODEL}. The cap is "
                    "per model, so set GEMINI_MODEL to another model (e.g. gemini-3.6-flash) "
                    "or add billing. The run is checkpointed — `crew resume <thread_id>` "
                    "picks up where it stopped."
                ) from exc
            wait = 8 * (attempt + 1)
            print(f"[crew] LLM rate-limited, retrying in {wait}s ({attempt + 1}/4)")
            time.sleep(wait)
            last_exc = exc
    raise last_exc  # type: ignore[misc]


def _strip_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:\w+)?\n(.*)\n```$", text, re.DOTALL)
    return match.group(1).strip() if match else text


def _search_lessons(task: str) -> list[dict[str, Any]]:
    """Retrieval is the demo — no fallback. A silent empty result here would look
    exactly like a cold run, so let failures surface instead of faking a warm one."""
    return list(brain.search_lessons(task) or [])


def _distill_lessons(review_feedback: str, source_task: str) -> list[str]:
    """Best-effort: an approved run should not be lost because lesson-writing hiccuped."""
    if not review_feedback.strip():
        return []
    try:
        return list(brain.distill_lessons(review_feedback, source_task) or [])
    except Exception as exc:  # noqa: BLE001
        print(f"[crew] brain.distill_lessons failed ({exc!r}); skipping")
        return []


def _format_lessons(lessons: list[dict[str, Any]]) -> str:
    if not lessons:
        return "(none retrieved — you have no prior lessons for this task)"
    lines = []
    for i, lesson in enumerate(lessons, 1):
        score = lesson.get("score")
        score_bit = f" score={score:.2f}" if isinstance(score, (int, float)) else ""
        lines.append(
            f"{i}. [{lesson.get('type', 'lesson')}]{score_bit} {lesson.get('rule', '').strip()}"
        )
    return "\n".join(lines)


def planner(state: CrewState) -> dict[str, Any]:
    task = state["task"]
    plan = _complete(
        system=(
            "You are the planner for a tiny FastAPI coding crew. "
            "Write a short, concrete plan (5-8 bullets) to complete the task against "
            "demo_target/: which files to add or edit, which routes and tests to create. "
            "Do not write code. Do not mention house conventions "
            "(no api_error, handle_* names, *Response models, or test_*__* names)."
        ),
        user=(
            f"Task: {task}\n\n"
            "Existing layout:\n"
            "- demo_target/app/main.py — FastAPI app, includes routers\n"
            "- demo_target/app/routes/widgets.py — example resource (GET list + GET by id)\n"
            "- demo_target/tests/test_widgets.py — pytest + shared client fixture\n"
        ),
    )
    return {"plan": plan}


def coder(state: CrewState) -> dict[str, Any]:
    task = state["task"]
    lessons = _search_lessons(task)
    feedback = (state.get("review_feedback") or "").strip()
    prior_code = (state.get("code") or "").strip()

    if lessons and not feedback:
        system = (
            "You write FastAPI code that obeys retrieved lessons as house law. "
            "Apply every lesson before writing a line. Mirror the gold-standard resource "
            "(handler names handle_<resource>_<verb>, api_error, <Resource><Verb>Response "
            "models, test_<resource>__<behavior>, imports from `app.` not `demo_target.app.`).\n\n"
            f"{_gold_standard()}\n{_FILE_FORMAT}"
        )
        extra = f"Retrieved lessons:\n{_format_lessons(lessons)}"
    elif feedback:
        cycles = int(state.get("cycles") or 0)
        # After two rejects, show the gold file so the last draft actually lands clean.
        gold = _gold_standard() if cycles >= 2 else ""
        system = (
            "You are fixing a FastAPI draft. The reviewer is the authority.\n"
            "Apply every change they asked for this round, and keep fixes from earlier rounds.\n"
            "Do not apply house conventions they have not mentioned yet.\n"
            "Rewrite rules (only when the reviewer asked for that item):\n"
            "- handlers: list_x → handle_<resource>_list, get_x → handle_<resource>_get\n"
            "- errors: `from app.errors import api_error`; "
            "raise api_error(status, 'RESOURCE_NOT_FOUND', message) — never HTTPException\n"
            "- models: <Resource>ListResponse / <Resource>GetResponse + response_model=\n"
            "- tests: test_<resource>__<behavior> (double underscore), shared client fixture\n"
            "- imports: `from app.errors import api_error`, never demo_target.app\n\n"
            f"{gold}{_FILE_FORMAT}"
        )
        extra = (
            f"Retrieved lessons:\n{_format_lessons(lessons)}\n\n"
            f"Reviewer feedback (must fix):\n{feedback}\n\n"
            f"Previous draft:\n{prior_code}"
        )
        earlier = list(state.get("feedback_history") or [])[:-1]
        if earlier:
            extra += (
                "\n\nEarlier reviewer rounds (already applied — keep them):\n"
                + "\n---\n".join(earlier)
            )
    else:
        system = (
            "You are a competent but generic FastAPI coder. You have NOT read this repo's "
            "CONVENTIONS.md and you have no lessons. Use ordinary tutorial patterns:\n"
            "- raise HTTPException(status_code=404, detail='...') for missing resources\n"
            "- name handlers list_<resource> / get_<resource>\n"
            "- skip response_model=\n"
            "- name tests test_list / test_get / test_not_found\n"
            "- do not invent handle_* names, *Response models, or test_*__* names\n\n"
            f"{_FILE_FORMAT}"
        )
        extra = "No lessons retrieved. First draft — tutorial style is correct."

    code = _complete(
        system=system,
        user=f"Task: {task}\n\nPlan:\n{state.get('plan', '')}\n\n{extra}\n",
    )
    return {"code": _strip_fences(code), "lessons_used": lessons}


def _parse_review(raw: str) -> Review:
    try:
        data = json.loads(raw)
        return Review.model_validate(data)
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return Review.model_validate(json.loads(match.group(0)))
        except Exception:
            pass
    approved = bool(re.search(r"\bAPPROVE", raw, re.I)) and not re.search(r"\bREJECT", raw, re.I)
    return Review(approved=approved, issues=[], feedback=raw)


def reviewer(state: CrewState) -> dict[str, Any]:
    raw = _complete(
        system=(
            "You are a strict code reviewer for this FastAPI service.\n\n"
            f"HOUSE CONVENTIONS:\n{_conventions()}\n\n"
            "Rules:\n"
            "- Approve ONLY when every convention is satisfied.\n"
            "- If the code already follows all conventions, approve immediately — "
            "even on first review.\n"
            "- On a REJECT pass, report at most TWO violations, highest priority first.\n"
            "  Priority: (1) error envelope, (2) handler naming, (3) response models, "
            "(4) test naming.\n"
            "- On later rejects, report the next unmet violations (again at most two).\n"
            "- Be specific: quote the current identifier and the required one "
            "(e.g. rename list_items → handle_items_list; "
            "raise api_error(404, 'ITEM_NOT_FOUND', ...) not HTTPException; "
            "add ItemsListResponse / ItemsGetResponse; "
            "rename test_list → test_items__list_returns_all).\n"
            "- Imports must be `from app.errors import api_error`, never demo_target.app.\n"
            "- Do not invent extra style nits. Only the listed conventions.\n"
            "- Reply with JSON only, matching: "
            '{"approved": bool, "issues": [str], "feedback": str}'
        ),
        user=(
            f"Task: {state['task']}\n\n"
            f"Plan:\n{state.get('plan', '')}\n\n"
            f"Code under review:\n{state.get('code', '')}\n"
        ),
    )
    review = _parse_review(raw)
    history = list(state.get("feedback_history") or [])
    cycles = int(state.get("cycles") or 0)
    updates: dict[str, Any] = {"approved": review.approved}

    if review.approved:
        updates["review_feedback"] = ""
        if history:
            updates["lessons_written"] = _distill_lessons("\n\n".join(history), state["task"])
        else:
            updates["lessons_written"] = []
        return updates

    cycles += 1
    feedback = review.feedback.strip() or "\n".join(f"- {i}" for i in review.issues)
    history.append(feedback)
    updates["cycles"] = cycles
    updates["review_feedback"] = feedback
    updates["feedback_history"] = history

    if cycles >= MAX_CYCLES:
        updates["lessons_written"] = _distill_lessons("\n\n".join(history), state["task"])
    return updates


def _after_review(state: CrewState) -> Literal["coder", "end"]:
    if state.get("approved") or int(state.get("cycles") or 0) >= MAX_CYCLES:
        return "end"
    return "coder"


@lru_cache(maxsize=1)
def build_graph():
    """Return the compiled LangGraph app with the MongoDB checkpointer."""
    graph = StateGraph(CrewState)
    graph.add_node("planner", planner)
    graph.add_node("coder", coder)
    graph.add_node("reviewer", reviewer)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "coder")
    graph.add_edge("coder", "reviewer")
    graph.add_conditional_edges(
        "reviewer",
        _after_review,
        {"coder": "coder", "end": END},
    )
    saver = MongoDBSaver(
        mongo_client(),
        db_name=MONGODB_DB,
        checkpoint_collection_name=CHECKPOINTS_COLLECTION,
    )
    return graph.compile(checkpointer=saver)


def _empty_state(task: str) -> CrewState:
    return {
        "task": task,
        "plan": "",
        "code": "",
        "review_feedback": "",
        "cycles": 0,
        "lessons_used": [],
        "approved": False,
        "feedback_history": [],
        "lessons_written": [],
    }


def _persist_run(thread_id: str, result: dict[str, Any]) -> None:
    db()[RUNS_COLLECTION].update_one(
        {"thread_id": thread_id},
        {
            "$set": {
                "task": result.get("task", ""),
                "cycles": int(result.get("cycles") or 0),
                "approved": bool(result.get("approved")),
                "finished_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


def run_task(task: str | None, thread_id: str) -> dict:
    """Run (or resume) a task through the crew; returns final state for the CLI to render.

    `task` is optional so `crew resume <thread_id>` can call run_task(None, thread_id):
    a resumed run reads its task back out of the checkpoint.
    """
    app = build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = app.get_state(config)
    resumed_from = snapshot.next[0] if snapshot.next else None

    if snapshot.values and snapshot.next:
        result = app.invoke(None, config)
    elif snapshot.values and not snapshot.next:
        result = snapshot.values
    else:
        if not task:
            raise ValueError(f"no checkpoint for thread_id {thread_id!r} — nothing to resume")
        result = app.invoke(_empty_state(task), config)

    out = dict(result or {})
    out["resumed_from"] = resumed_from
    out.setdefault("task", task or "")
    out.setdefault("plan", "")
    out.setdefault("code", "")
    out.setdefault("cycles", 0)
    out.setdefault("lessons_used", [])
    out.setdefault("approved", False)
    # The CLI renders one panel per correction cycle, so hand it the per-cycle list
    # (feedback_history) rather than the in-graph scalar. See CrewState.
    out["review_feedback"] = list(out.get("feedback_history") or [])

    finished = not app.get_state(config).next
    if finished:
        _persist_run(thread_id, out)
    return out


if __name__ == "__main__":
    import sys
    import uuid

    demo_task = sys.argv[1] if len(sys.argv) > 1 else "add a /items endpoint"
    tid = sys.argv[2] if len(sys.argv) > 2 else f"crew-dev-{uuid.uuid4().hex[:8]}"
    final = run_task(demo_task, tid)
    n_lessons = len(final.get("lessons_used") or [])
    print(f"thread_id={tid}")
    print(f"approved={final.get('approved')} cycles={final.get('cycles')} lessons_used={n_lessons}")
    print(f"resumed_from={final.get('resumed_from')}")
    if final.get("lessons_used"):
        for lesson in final["lessons_used"]:
            score = lesson.get("score")
            print(f"  - {lesson.get('rule', '')[:80]}  score={score}")
    print("--- code ---")
    print(final.get("code", "")[:2000])
