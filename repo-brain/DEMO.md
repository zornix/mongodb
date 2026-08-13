# Running the demo yourself

Everything below is run from `repo-brain/`. Commands are written with `uv run`; if you
prefer, `.venv/bin/crew ...` works identically.

The demo has one job: show the same crew doing the **same kind of task twice** and
behaving measurably better the second time, because the first run's review feedback was
distilled into lessons stored in Atlas and retrieved before the second run wrote a line.

---

## 0. Before you start (once)

```bash
uv sync
cp .env.example .env       # fill MONGODB_URI, GOOGLE_API_KEY, VOYAGE_API_KEY
uv run python scripts/setup_indexes.py     # idempotent; prints "already exists" if done
uv run python scripts/reset_demo.py        # read-only: prints what's in the brain now
```

`reset_demo.py` with no flags never writes — it's the safe "what state am I in?" check.

---

## 1. The call budget (read this before rehearsing)

Gemini's free tier caps requests **per day, per model**. One run costs:

| Run | Gemini calls | Why |
|---|---|---|
| **Cold** (empty brain) | **~8** | planner 1 + 3 × (coder + reviewer) + 1 distillation |
| **Warm** (lessons present, passes clean) | **3** | planner + coder + reviewer, no distillation |
| Full demo (cold → warm) | **~11** | |
| Resume after a kill | only the nodes that hadn't finished | checkpointed in Mongo |

So a model with a 20/day cap gives you roughly **one full demo plus a spare warm run**.
Budget accordingly, and switch models between rehearsals (§2).

Voyage embeddings are a separate budget: 1 embed per coder pass plus 1 per lesson
written. Free Voyage keys allow **3 requests/minute** — `brain.embed` sleeps 25 s and
retries rather than crashing, so a cold run can visibly stall for ~half a minute. That's
expected, not a hang.

---

## 2. Switching the model (the quota escape hatch)

```bash
uv run crew model                       # show the current model + the demo shortlist
uv run crew model 3.5                   # switch and WRITE it to .env (sticks)
uv run crew model --list                # ask the API what this key can actually call
uv run crew run "..." --model 3.1       # one run only, .env untouched
uv run crew resume <thread_id> -m 3.5   # finish a run that hit the wall on another model
```

Aliases: `3.1` → `gemini-3.1-flash-lite`, `3.5` → `gemini-3.5-flash-lite`,
`preview` → `gemini-3.1-flash-lite-preview`, `3.6` → `gemini-3.6-flash`,
`flash` → `gemini-3.5-flash`. Any full model id also works.

**Verified on this key today** (each with its own separate daily budget):

| Model | Status |
|---|---|
| `gemini-3.1-flash-lite` | ✅ works — current default in `.env` |
| `gemini-3.5-flash-lite` | ✅ works — first fallback |
| `gemini-3.1-flash-lite-preview` | ✅ works — second fallback |
| `gemini-3.6-flash`, `gemini-3.5-flash` | ✅ work (bigger models, same 8-call cost) |
| `gemini-2.5-flash-lite` | ❌ 404 — listed by the API but "no longer available to new users" |
| `gemini-3.7-flash` | ❌ daily quota already exhausted |

Three working lite models × ~20 calls ≈ **five full demos a day** if you rotate.

When the daily cap hits, the crew fails fast with a message naming the model (it does
*not* burn 80 s retrying an unretryable daily 429), and the run is checkpointed — switch
model and `crew resume <thread_id>` continues from the node that died instead of paying
for the calls already made.

---

## 3. The demo, beat by beat

### Beat 1 — empty the brain, so the crew is genuinely cold

```bash
uv run python scripts/reset_demo.py --cold
```

Deletes every lesson and every recorded run. (Add `--checkpoints` to also drop resume
history — only do that if you want a totally clean slate; it removes the threads you
could resume.) Cold vs warm is decided **purely** by whether `lessons` has anything
retrievable, so this reset *is* the demo setup.

### Beat 2 — the cold run

```bash
uv run crew run "add a /items endpoint" --thread-id items-cold
```

What to point at on screen:

- **No `⚡ lessons retrieved` line** — the brain is empty.
- The coder writes ordinary tutorial FastAPI: `HTTPException`, `list_items`, no
  `response_model`, `test_list`.
- Red **Review cycle** panels: the reviewer quotes `demo_target/CONVENTIONS.md` and
  sends it back, at most two violations per pass, up to 3 cycles.
- Ends with **"Review passed after 2 correction cycle(s)"** (2–3 is typical).
- On approval the reviewer's feedback is distilled into durable lessons.

~8 Gemini calls. This is the expensive beat — don't rehearse it more than you must.

### Beat 3 — show what it learned

```bash
uv run crew brain
```

A table of the lessons the crew wrote **for itself** out of the reviewer's corrections —
error envelope, handler naming, response models — with hit counts.

### Beat 4 — the warm run (the payoff)

```bash
uv run crew run "add a /orders endpoint" --thread-id orders-warm
```

- **`⚡ 3 lessons retrieved (score 0.74)`** prints *before* any code — retrieval happens
  before writing, which is the whole claim.
- The code comes out with `handle_orders_list` / `handle_orders_get`, `api_error`,
  `OrdersListResponse`, `test_orders__*` on the **first draft**.
- **"Review passed clean — 0 correction cycles."**

3 Gemini calls. Same crew, same prompt shape, different behaviour — because of memory.

### Beat 5 — kill it and resume (crash-proof)

Start a third task and Ctrl-C (or `kill -9`) it mid-run:

```bash
uv run crew run "add a /users endpoint" --thread-id users-crash
# ^C somewhere in the coder/reviewer loop
uv run crew resume users-crash
```

The thread id is printed **at the start** of the run as well as the end, precisely so you
can kill it and still have the id. `resume` prints **`Resumed from: <node>`** and
continues from the checkpointed node — no work, and no LLM calls, repeated.

### Beat 6 — the learning curve

```bash
uv run crew stats
```

One row per run with its correction-cycle count: `/items` at 2–3, `/orders` at 0, plus
total lessons and total retrieval hits.

---

## 4. Rehearsing without spending quota

- `crew stats`, `crew brain`, `crew model`, `reset_demo.py` (no flags) cost **zero**
  Gemini calls — rehearse the narration around them freely.
- To get a warm brain without paying for a cold run:
  ```bash
  uv run python scripts/reset_demo.py --seed    # 3 CONVENTIONS.md lessons, 0 Gemini calls
  ```
  Then Beat 4 works on its own. Use this if you're low on quota and only need the payoff
  beat — but note the honest version of the story is the distilled one from Beat 2.
- `crew resume <finished_thread_id>` re-renders a **completed** run from its checkpoint
  with no LLM calls at all. If you have one good cold run and one good warm run banked,
  you can replay both on stage for free:
  ```bash
  uv run crew resume items-cold
  uv run crew resume orders-warm
  ```
  That's the safest way to demo if the network or the quota is shaky.

---

## 5. If something goes wrong

| Symptom | Fix |
|---|---|
| `Gemini daily free-tier quota exhausted for <model>` | `uv run crew model 3.5` (or `preview`), then `crew resume <thread_id>` |
| `[crew] LLM rate-limited, retrying in 8s` | per-minute cap; it retries 4× on its own — just wait |
| Run stalls ~25 s with no output | Voyage 3 req/min limit inside `brain.embed`; it resumes itself |
| `404 ... no longer available to new users` | that model id is dead for this key — `crew model --list` and pick another |
| Warm run shows no `⚡` line | the brain is empty — `reset_demo.py --seed`, or you're still cold |
| Cold run *already* passes clean | lessons are still in Atlas — `reset_demo.py --cold` first |
| `no checkpoint for thread_id '...'` | wrong id, or `--checkpoints` wiped it; start a fresh `crew run` |
| `MONGODB_URI is not set` | `.env` missing or not in `repo-brain/` |

---

## 6. Command reference

```bash
uv run crew run "<task>" [-m MODEL] [-t THREAD_ID]   # run a task, render the full trace
uv run crew resume <thread_id> [-m MODEL]            # continue (or replay) from checkpoint
uv run crew stats                                    # learning-curve table
uv run crew brain                                    # lesson dump
uv run crew model [name] [--list]                    # show / switch the Gemini model

uv run python scripts/reset_demo.py                  # show brain state (read-only)
uv run python scripts/reset_demo.py --cold           # wipe lessons + runs
uv run python scripts/reset_demo.py --seed           # wipe, then seed 3 conventions
uv run python scripts/setup_indexes.py               # create the vector index (once)
uv run python scripts/hello_graph.py                 # checkpointer smoke test
```
