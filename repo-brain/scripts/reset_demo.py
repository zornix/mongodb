"""Put the brain into a known state before a demo run.

    uv run python scripts/reset_demo.py            # just show what's in Atlas now
    uv run python scripts/reset_demo.py --cold     # wipe lessons + runs -> next run is COLD
    uv run python scripts/reset_demo.py --seed     # wipe, then insert the 3 CONVENTIONS.md
                                                   #   lessons -> next run is WARM
    uv run python scripts/reset_demo.py --cold --checkpoints   # also drop resume history

The cold/warm contrast is the whole demo, and it is decided purely by whether
`lessons` has anything the coder can retrieve — so reset before every rehearsal.

--seed costs 3 Voyage embed calls; free-tier Voyage keys allow 3/minute, so brain.embed
sleeps through the window and this can take ~1 minute. It costs zero Gemini calls.
"""

import argparse

from repo_brain import brain
from repo_brain.config import CHECKPOINTS_COLLECTION, LESSONS_COLLECTION, RUNS_COLLECTION, db

# The house conventions, pre-distilled. Seeding these makes a warm run possible without
# first paying for a cold run — same rules a cold run's distillation writes for itself.
SEED_LESSONS = [
    (
        (
            "Every non-2xx response body must be {'error': {'code': '<SCREAMING_SNAKE>', "
            "'message': '<human text>'}} — raise via app.errors.api_error(status, code, "
            "message), never a bare HTTPException."
        ),
        "demo_target/CONVENTIONS.md #1",
    ),
    (
        (
            "Route handlers are named handle_<resource>_<verb> in snake_case "
            "(e.g. handle_items_list), one resource per module in app/routes/."
        ),
        "demo_target/CONVENTIONS.md #2",
    ),
    (
        (
            "Every route declares response_model= with a Pydantic model defined in the same "
            "routes module, named <Resource><Verb>Response."
        ),
        "demo_target/CONVENTIONS.md #3",
    ),
]


def show() -> None:
    stats = brain.stats()
    print(f"lessons: {stats['lessons_total']} {stats['lessons_by_type']}")
    print(f"retrieval hits: {stats['total_hits']}")
    print(f"runs recorded: {len(stats['runs'])}")
    print(f"checkpointed threads: {len(db()[CHECKPOINTS_COLLECTION].distinct('thread_id'))}")
    for lesson in brain.list_lessons(50):
        print(f"  [{lesson['type']}] ({lesson['source_task']}) {lesson['rule'][:90]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cold", action="store_true", help="delete all lessons and runs")
    parser.add_argument("--seed", action="store_true", help="delete lessons, insert the 3 seeds")
    parser.add_argument(
        "--checkpoints", action="store_true", help="also drop checkpoints (kills resume history)"
    )
    args = parser.parse_args()

    if args.cold or args.seed:
        deleted = db()[LESSONS_COLLECTION].delete_many({}).deleted_count
        print(f"deleted {deleted} lessons")
    if args.cold:
        print(f"deleted {db()[RUNS_COLLECTION].delete_many({}).deleted_count} runs")
    if args.checkpoints:
        print(f"deleted {db()[CHECKPOINTS_COLLECTION].delete_many({}).deleted_count} checkpoints")
    if args.seed:
        for rule, evidence in SEED_LESSONS:
            brain.add_lesson("convention", rule, evidence, "seed")
            print(f"seeded: {rule[:70]}...")

    print()
    show()


if __name__ == "__main__":
    main()
