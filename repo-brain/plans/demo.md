# Plan — Person 3: Demo surface (`cli.py`) + video

Owner scope per [TEAM_SPLIT.md](../TEAM_SPLIT.md#person-3--demo-surface-clipy--video).
State shape is frozen (crew state contract in TEAM_SPLIT.md) — code against it, don't
redesign it.

## Fake state module (unblocks everything below immediately)

New file `src/repo_brain/fake_state.py` — hand-written dicts matching the frozen crew
state `{task, plan, code, review_feedback, cycles, lessons_used}`, plus a fake
`brain.stats()`-shaped dict. Two fixtures:

- `COLD_RUN`: `task="add a /items endpoint"`, `cycles=2`, `lessons_used=[]` on first
  pass then populated on retry, `review_feedback` with 3 CONVENTIONS.md violations
  (error envelope, handler naming, response model naming) worded like a real reviewer.
- `WARM_RUN`: `task="add a /orders endpoint"`, `cycles=0`, `lessons_used=` 3 lesson
  dicts (`type`, `rule`, `evidence`, `score`) pulled straight from CONVENTIONS.md rules,
  `review_feedback=None`.
- `FAKE_STATS`: `{"tasks": [{"task": ..., "cycles": 2}, {"task": ..., "cycles": 0}],
  "lessons_total": 3, "hits_total": 3}` — the run-over-run learning curve line.
- `FAKE_LESSONS`: list of lesson dicts for `crew brain`.

This is the only file that needs edits to swap fakes for real: once Person 2's
`crew.run_task` and Person 1's `brain.stats`/`brain.search_lessons` land, the CLI calls
those directly and `fake_state.py` becomes dead/deleted. Every command below is written
against the *shape*, not the fake module, so the swap is a one-line import change per
command, not a rewrite.

## Commands (`src/repo_brain/cli.py`, Typer app already scaffolded)

1. **`crew run "<task>"`**
   - Try `from repo_brain import crew` and call `crew.run_task(task, thread_id=str(uuid4()))`;
     on `NotImplementedError` (or `ImportError` during early build), fall back to
     `fake_state.COLD_RUN` / `WARM_RUN` picked by matching `task` string, so the same
     command works before and after integration without a flag.
   - Rich rendering, in order: `⚡ N lessons retrieved (score X.XX)` line per entry in
     `lessons_used` (before code — that ordering *is* the point per DECISIONS.md) →
     panel with `plan` → for each review cycle so far, a red panel with
     `review_feedback` → final `code` as a syntax-highlighted diff (`rich.syntax.Syntax`,
     lexer `python`, diff via `difflib.unified_diff` against nothing/empty since we only
     have final code, or against previous `code` if the fake models a before/after) →
     green "lessons written" panel listing what `distill_lessons` produced.
   - Print the `thread_id` clearly at the end — `crew resume` needs it.
   - Verify: `uv run crew run "add a /items endpoint"` renders cold path;
     `uv run crew run "add a /orders endpoint"` renders warm path with the `⚡` line.

2. **`crew resume <thread_id>`**
   - Call `crew.run_task(task=None, thread_id=thread_id)` (resume path) when real;
     fake fallback prints a canned "resumed from node: reviewer" line plus the rest of
     `COLD_RUN` from where it left off.
   - Print which node it resumed from prominently (`Resumed from: <node>`) — that's the
     entire point of the crash-demo beat.
   - Verify: `uv run crew resume test-thread-1` prints a resume line without error.

3. **`crew stats`**
   - Real: `brain.stats()`. Fake: `fake_state.FAKE_STATS`.
   - Rich table: one row per task (`task`, `cycles`), plus a summary line
     `lessons: N, hits: M`. This is the run-over-run proof line from the demo script.
   - Verify: `uv run crew stats` prints a 2-row table + summary with no real backend.

4. **`crew brain`**
   - Real: iterate `brain.search_lessons("", k=50)` or a dedicated dump — flag to Person
     1 if there's no "list all" function (see Open questions). Fake:
     `fake_state.FAKE_LESSONS`.
   - Rich table: `type`, `rule`, `hit_count`.
   - Cut line per TEAM_SPLIT.md — if short on time, skip and fold a stats print into
     `crew run` instead. Build last, after 1–3.

5. **Demo script ownership** (not code, but in scope and time-boxed):
   - Confirm/lock the two tasks: `/items` (cold) and `/orders` (warm) — already fixed by
     DECISIONS.md and mirrored in the fakes above, so rehearsal can start against fakes
     immediately, before real integration.
   - From 3:30: rehearse `run /items` → `run /orders` → kill -9 mid third task → `resume`
     → `stats`, coordinate with Person 1 to reset the `lessons` collection between
     rehearsals (`db.lessons.delete_many({})` — confirm this is fine to run against
     shared Atlas, not local).
   - Record + submit by 4:45.

## Verification summary (run after each step)

```bash
uv run crew run "add a /items endpoint"     # cold: 3 violations, 2 cycles, no ⚡ line
uv run crew run "add a /orders endpoint"    # warm: ⚡ 3 lessons retrieved, 0 cycles
uv run crew resume <thread_id-from-above>   # prints resumed-from node
uv run crew stats                           # 2-row learning-curve table
uv run crew brain                           # lesson dump table (build last)
```

All five must work against `fake_state.py` with zero network calls before touching
integration — that's what keeps this lane unblocked.

## Open questions (raising now, not at 3:30)

1. **`brain.stats()` shape** — plan assumes `{"tasks": [{"task", "cycles"}, ...],
   "lessons_total", "hits_total"}`. Person 1: does `stats()` match this, or does the CLI
   need to reshape whatever it returns?
2. **No "list all lessons" function in the frozen Brain API** (`embed`, `add_lesson`,
   `distill_lessons`, `search_lessons`, `stats` — five functions, no dump/list). For
   `crew brain` I'll call `search_lessons("", k=50)` unless Person 1 confirms empty-query
   vector search behaves reasonably, or adds a `list_lessons()`/broadens `stats()` to
   include full lesson bodies. Given this is the designated cut line, defaulting to
   punting rather than requesting a new contract function — flagging in case it's cheap.
3. **`crew.run_task` resume signature** — TEAM_SPLIT.md says `run_task(task, thread_id)`;
   for resume, is `task` required (e.g. re-pass the original) or optional/`None` when
   `thread_id` already has a checkpoint? CLI needs to know what to pass on `crew resume`.
