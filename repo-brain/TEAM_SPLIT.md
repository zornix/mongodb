# Team Split — 3 People

Adaptation of the 4-person split in [DECISIONS.md](DECISIONS.md) for a 3-person team.
The MCP server (formerly role D) folds into the Brain lane: it's a thin wrapper over
`brain.py`, owned by the person who knows that module best, and stays the designated
cut if time runs short.

## Setup — every lane, before anything else (agent does this itself)

All dependencies are pinned in `pyproject.toml`; nobody hand-picks versions or
`pip install`s ad hoc. From `repo-brain/`:

```bash
# 1. Install uv if missing
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install ALL project dependencies (creates .venv, installs the package editable)
uv sync

# 3. Save the .env you received by DM as repo-brain/.env  (gitignored — NEVER commit it)

# 4. Verify: deps import, config resolves, Atlas reachable
uv run python -c "
import langgraph, voyageai, langchain_google_genai, fastmcp, rich, typer
from repo_brain.config import EMBEDDING_MODEL, EMBEDDING_DIMS, mongo_client
print('deps OK:', EMBEDDING_MODEL, EMBEDDING_DIMS)
mongo_client().admin.command('ping'); print('Atlas OK')"
```

What `uv sync` installs (already declared — run `uv add <pkg>` if you truly need
something new, and announce it):

| Package | Used by |
|---|---|
| `langgraph`, `langgraph-checkpoint-mongodb` | crew graph + Mongo checkpointing (Person 2) |
| `langchain-google-genai` | crew LLM — Gemini, use `config.GEMINI_MODEL` (Persons 1 & 2) |
| `voyageai` | embeddings — `voyage-3.5-lite`, 1024 dims (Person 1) |
| `pymongo` | Atlas client, vector search (Person 1) |
| `fastmcp` | MCP server (Person 1, stretch) |
| `rich`, `typer` | demo CLI (Person 3) |
| `python-dotenv` | `.env` loading (all) |
| `fastapi`, `uvicorn`, `httpx`, `pytest` | the seeded `demo_target/` fixture (all) |

If the Atlas ping fails: check the venue network first, then ask Person 1 (they own
the cluster's IP access list and DB users).

## Workflow — every lane: plan first, then dev

Before writing any implementation code, the agent must:

1. **Write an implementation plan** to `plans/<lane>.md` (e.g. `plans/brain.md`,
   `plans/crew.md`, `plans/demo.md`), covering:
   - every function/command in scope (from the lane's checklist below) and the
     approach for each, including exact external calls (Gemini / Voyage / Mongo ops);
   - what will be faked until other lanes land, and the swap point;
   - how each piece gets verified (a runnable command, not "should work");
   - open questions — surface them to the team *now*, not at the 3:30 merge.
2. **Check the plan against the frozen contracts** (below). If the plan needs a
   contract change, stop and raise it with the team before proceeding.
3. Get a quick human thumbs-up on the plan (30 seconds, not a review meeting).
4. **Then implement**, in small steps, running the plan's verification command after
   each step. Commit early and often to your branch.

### Frozen contracts — code against these, do NOT redesign them

- **Brain API** — the five function signatures in `src/repo_brain/brain.py`
- **Crew state** — `{task, plan, code, review_feedback, cycles, lessons_used}`,
  returned by `run_task(task, thread_id)` (see `crew.py` docstring)
- **Lesson doc shape** — the dict documented at the top of `brain.py`

Anyone who needs to change a contract announces it immediately — these three are the
only coupling points.

---

## Person 1 — Brain + MCP (`brain.py`, `mcp_server.py`)

The memory layer everyone consumes. **Build `brain.py` first — it unblocks the demo
of the core thesis.** Plan goes to `plans/brain.md`, then implement:

1. `embed(text)` — Voyage AI `voyage-3.5-lite` via the `voyageai` client (config
   fixes 1024 dims; key is `VOYAGE_API_KEY` in `.env`).
2. `add_lesson(type_, rule, evidence, source_task)` — insert with embedding,
   `hit_count: 0`, `created_at`.
3. `search_lessons(task_description, k=5)` — `$vectorSearch` against
   `lessons_vector_index` (already scripted in `scripts/setup_indexes.py`), return
   docs with scores, `$inc: {hit_count: 1}` on the returned ids.
4. `distill_lessons(review_feedback, source_task)` — one Gemini call
   (`config.GEMINI_MODEL` via `langchain-google-genai`) that turns raw reviewer feedback
   into 0..n durable lessons (JSON list of `{type, rule, evidence}`), store each via
   `add_lesson`.
5. `stats()` — lesson counts by type, total hits, per-task correction cycles (read
   cycles from a small `runs` collection that Person 2 writes to).
6. **Then** `mcp_server.py`: FastMCP over stdio exposing `search_lessons`,
   `add_lesson`, `brain_stats` — each ~3 lines calling the module above.

Also owns ops: Atlas IP access list for teammates, run `setup_indexes.py`
**immediately** (index builds take minutes), run `hello_graph.py` twice (second run
must print "resumed"), seed 2–3 hand-written lessons from `demo_target/CONVENTIONS.md`
so Persons 2 and 3 can test retrieval before real distillation works.

**Cut line:** MCP server. The crew demo stands without it.

## Person 2 — Crew (`crew.py`)

The LangGraph graph: planner → coder → reviewer, loop until clean or max cycles.
Plan goes to `plans/crew.md`, then implement:

1. `build_graph()` — `StateGraph` over the agreed state dict; all LLM nodes use
   Gemini via `langchain-google-genai` with `config.GEMINI_MODEL` — do NOT hardcode a
   model name (`gemini-2.5-flash` is retired; `gemini-3.7-flash` is verified working).
   Heads-up: this client returns `.content` as a list of content blocks — use
   `response.text` (or join the text blocks), don't assume a plain string. Nodes:
   - **planner**: LLM turns `task` into a short `plan`.
   - **coder**: calls `brain.search_lessons(task)` **before** writing (record what came
     back in `lessons_used` — the demo hinges on displaying this), then produces `code`
     honoring plan + lessons + any prior `review_feedback`.
   - **reviewer**: LLM judges `code` against `demo_target/CONVENTIONS.md` (embed the
     conventions in the prompt). Violations → `review_feedback`, `cycles += 1`,
     conditional edge back to coder (cap at 3). Clean → call
     `brain.distill_lessons(feedback_history, task)` and end.
   - Compile with `MongoDBSaver` (pattern is already proven in `scripts/hello_graph.py`).
2. `run_task(task, thread_id)` — invoke or resume by `thread_id`; on resume, pick up
   from the checkpointed node. Persist `{task, cycles}` to a `runs` collection at the
   end so `stats()` has correction-cycle history.
3. Until Person 1 lands, develop against a fake brain (return canned lessons, no-op
   distill) — swap to the real module at integration.
4. Tune prompts so the **cold run reliably produces 2 correction cycles** and the
   **warm run passes clean** — that determinism *is* the demo.

**Cut line:** the crash/resume demo step (checkpointing still ships since it's one
compile arg; only the staged kill -9 gets cut).

## Person 3 — Demo surface (`cli.py`) + video

The judges only see this lane. **Records the video by 4:45 — hard deadline.**
Plan goes to `plans/demo.md`, then implement:

1. `crew run "<task>"` — Rich-rendered run: show `⚡ N lessons retrieved (score 0.89)`
   before the code appears, each review cycle with the reviewer's complaints, the final
   diff, and lessons written at the end.
2. `crew resume <thread_id>` — re-enter a killed run; print the node it resumed from.
3. `crew stats` — the run-over-run learning-curve line (task 1: 2 cycles → task 2: 0
   cycles; lessons: N, hits: M) from `brain.stats()`.
4. `crew brain` — table dump of accumulated lessons.
5. Until Person 2 lands, render from hand-written fake final-state dicts (the state
   shape is fixed) — this lane must never block on the others.
6. Owns the **demo script**: pick the two tasks (`/items` cold, `/orders` warm),
   rehearse the full loop repeatedly from 3:30, coordinate with Person 1 to reset
   `lessons` between rehearsals, record + submit.

**Cut line:** `crew brain` dump; a stats print inside `crew run` can replace
`crew stats`.

---

## Timeline (from DECISIONS.md, unchanged)

| Time | All three |
|---|---|
| 1:30–2:00 | Setup + plans in all lanes; Person 1 kicks off index build first thing |
| 2:00–3:30 | Parallel build in the three lanes above |
| 3:30–4:15 | Integrate (fakes → real modules), run the full demo loop repeatedly |
| 4:15–4:45 | Polish; Person 3 records |
| 5:00 | Submit — public repo, all members on the form |

Integration order at 3:30: brain ↔ crew first (retrieval + distillation live), then
CLI on top, then MCP kicker if time allows.
