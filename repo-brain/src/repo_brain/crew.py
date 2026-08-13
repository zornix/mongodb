"""The LangGraph crew: planner -> coder -> reviewer (loop until clean or max cycles).

Graph contract (agreed pre-event, implemented at the event):
- State: {task, plan, code, review_feedback, cycles, lessons_used}
  - review_feedback: list[str], one entry per correction cycle, in order (empty list
    once clean) — cli.py renders one panel per cycle, so keep this a list, not a
    scalar overwritten each loop. See fake_state.py, which fixes this shape.
- coder node calls brain.search_lessons(task) BEFORE writing — the whole point
- reviewer node checks demo_target conventions; on violations, loops back to coder
- on approval, brain.distill_lessons(feedback) persists what was learned
- compiled with MongoDBSaver so any run can be killed and resumed by thread_id

STUB ONLY — implemented during the hackathon.
"""


def build_graph():
    """Return the compiled LangGraph app with the MongoDB checkpointer."""
    raise NotImplementedError("event-day work")


def run_task(task: str, thread_id: str) -> dict:
    """Run (or resume) a task through the crew; returns final state for the CLI to render."""
    raise NotImplementedError("event-day work")
