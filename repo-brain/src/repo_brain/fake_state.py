"""Hand-written fixtures matching the frozen crew state contract
({task, plan, code, review_feedback, cycles, lessons_used} — see crew.py), used by
cli.py until crew.run_task / brain.stats / brain.search_lessons land for real.

See plans/demo.md for the swap point: cli.py tries the real module first and only
falls back to these fixtures on NotImplementedError/ImportError, so no flag is needed
to demo against fakes today and against the real backend once it's up.

Note: `review_feedback` here is a list of one string per correction cycle (not a
single scalar) so the CLI can render each cycle's complaints, not just the last one.
Flagged to Person 2 in plans/demo.md open question — align crew.py's real state to
match, or the CLI will need to reshape it at the integration swap point.
"""

COLD_TASK = "add a /items endpoint"
WARM_TASK = "add a /orders endpoint"

COLD_RUN = {
    "task": COLD_TASK,
    "plan": (
        "1. Add GET /items and POST /items handlers in app/routes/items.py\n"
        "2. Define ItemsListResponse / ItemsCreateResponse Pydantic models\n"
        "3. Add tests/test_items.py using the shared `client` fixture"
    ),
    "code": '''\
+ from app.errors import api_error
+
+ def handle_items_list(...) -> ItemsListResponse:
+     ...

+ class ItemsListResponse(BaseModel):
+     items: list[Item]
''',
    "review_feedback": [
        "Cycle 1: bare `HTTPException(404, ...)` used for the not-found case — must "
        "raise via `app.errors.api_error(status, code, message)` per the error "
        "envelope convention.",
        "Cycle 2: handler named `items_list` — handler names must follow "
        "`handle_<resource>_<verb>`, so this needs to be `handle_items_list`.",
    ],
    "cycles": 2,
    "lessons_used": [],
}

WARM_RUN = {
    "task": WARM_TASK,
    "plan": (
        "1. Add GET /orders and POST /orders handlers in app/routes/orders.py\n"
        "2. Define OrdersListResponse / OrdersCreateResponse Pydantic models\n"
        "3. Add tests/test_orders.py using the shared `client` fixture"
    ),
    "code": '''\
+ from app.errors import api_error
+
+ def handle_orders_list(...) -> OrdersListResponse:
+     ...

+ class OrdersListResponse(BaseModel):
+     orders: list[Order]
''',
    "review_feedback": [],
    "cycles": 0,
    "lessons_used": [
        {
            "type": "convention",
            "rule": "Error responses use the {'error': {'code', 'message'}} envelope "
            "via app.errors.api_error(), never a bare HTTPException.",
            "score": 0.91,
        },
        {
            "type": "convention",
            "rule": "Route handlers are named handle_<resource>_<verb>, snake_case, "
            "one resource per module in app/routes/.",
            "score": 0.89,
        },
        {
            "type": "convention",
            "rule": "Every route declares response_model= with a Pydantic model named "
            "<Resource><Verb>Response in the same routes module.",
            "score": 0.85,
        },
    ],
}


def resolve_run(task: str) -> dict:
    """Pick a fixture by matching the task string — mirrors the two scripted demo tasks."""
    return WARM_RUN if "order" in task.lower() else COLD_RUN


RESUME_STATE = {
    **COLD_RUN,
    "resumed_from": "reviewer",
}

FAKE_STATS = {
    # Keys match the real brain.stats() shape ("runs" / "total_hits"), not the
    # "tasks" / "hits_total" names originally assumed in plans/demo.md open question 1.
    "runs": [
        {"task": COLD_TASK, "cycles": 2},
        {"task": WARM_TASK, "cycles": 0},
    ],
    "lessons_total": 3,
    "total_hits": 3,
}

FAKE_LESSONS = [
    {
        "type": "convention",
        "rule": "Error responses use the {'error': {'code', 'message'}} envelope via "
        "app.errors.api_error(), never a bare HTTPException.",
        "hit_count": 1,
    },
    {
        "type": "convention",
        "rule": "Route handlers are named handle_<resource>_<verb>, snake_case, one "
        "resource per module in app/routes/.",
        "hit_count": 1,
    },
    {
        "type": "convention",
        "rule": "Every route declares response_model= with a Pydantic model named "
        "<Resource><Verb>Response in the same routes module.",
        "hit_count": 1,
    },
]
