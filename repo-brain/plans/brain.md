# Plan — Person 1: Brain + MCP

Scope: implement the five frozen functions in `src/repo_brain/brain.py`, then
`mcp_server.py` (stretch). No contract changes needed — signatures stay exactly as
stubbed, lesson doc shape stays as documented at the top of `brain.py`.

## Functions

### 1. `embed(text) -> list[float]`
- Module-level cached `voyageai.Client()` (reads `VOYAGE_API_KEY` from env; `.env` is
  loaded by `config` import).
- `client.embed([text], model=EMBEDDING_MODEL, output_dimension=EMBEDDING_DIMS)` →
  `.embeddings[0]`. Symmetric embeddings (no `input_type`) so one function serves both
  storage and query sides.
- Verify: `uv run python -c "from repo_brain.brain import embed; v = embed('hi'); print(len(v))"` → `1024`.

### 2. `add_lesson(type_, rule, evidence, source_task) -> str`
- Insert into `lessons`: exactly the documented doc shape — embedding computed over
  `rule`, `hit_count: 0`, `created_at: datetime.now(timezone.utc)`.
- Returns `str(inserted_id)`.
- Verify: insert one, `find_one` it back, check keys + 1024-dim embedding.

### 3. `search_lessons(task_description, k=5) -> list[dict]`
- `$vectorSearch` on `lessons_vector_index`: `queryVector=embed(task_description)`,
  `numCandidates=max(50, k*10)`, `limit=k`; add `score: {$meta: "vectorSearchScore"}`,
  drop `embedding` from the projection (docs stay light for prompts/CLI).
- `$inc: {hit_count: 1}` via one `update_many` on the returned `_id`s, then stringify
  `_id` in the returned dicts (JSON-safe for CLI/MCP).
- Verify: after seeding, search "add an items endpoint with error handling" → returns
  the error-envelope lesson with a score; re-run bumps `hit_count`.

### 4. `distill_lessons(review_feedback, source_task) -> list[str]`
- One `ChatGoogleGenerativeAI(model=config.GEMINI_MODEL)` call. Prompt: extract 0..n
  *durable, repo-general* lessons as a JSON array of `{type, rule, evidence}`,
  `type ∈ {convention, past_fix, gotcha}`; empty array if nothing durable.
- Read `response.text` (NOT `.content` — this client returns content blocks), strip
  ```json fences, `json.loads`. Malformed JSON or bad items → skip gracefully
  (return what parsed; never crash the reviewer node).
- Store each via `add_lesson`, return the ids.
- Verify: feed it a canned reviewer complaint about the error envelope → ≥1 lesson
  lands in Mongo with a sensible `rule`.

### 5. `stats() -> dict`
- Lessons: one aggregation — total, counts by `type`, sum of `hit_count`.
- Runs: read the `runs` collection Person 2 writes (`{task, cycles}` per finished
  run, insertion order = chronology). Returned shape:
  `{lessons_total, lessons_by_type, total_hits, runs: [{task, cycles}, ...]}`.
- Empty `runs` is fine (Person 2 hasn't landed) — returns `runs: []`.
- Verify: call it after seeding; counts match what's in Atlas.

### 6. `mcp_server.py` (stretch — the designated cut)
- `FastMCP("repo-brain")`, three `@mcp.tool`s delegating to the module above:
  `search_lessons(query, k=5)`, `add_lesson(type, rule, evidence)` (source_task
  `"mcp"`), `brain_stats()`. `mcp.run()` = stdio.
- Verify: `uv run python -c "from repo_brain import mcp_server"` + a FastMCP
  in-process client call.

## Fakes / swap points
- Nothing faked in this lane — it's the bottom of the dependency stack. `stats()`
  degrades gracefully until Person 2's `runs` collection exists.

## Ops checklist (also this lane)
- [x] `uv sync` + env verify (deps OK, Atlas OK)
- [x] `setup_indexes.py` — `lessons_vector_index` already exists and is queryable
- [x] `hello_graph.py` twice — second run must print "resumed" (it did, twice)
- [x] Seeded 3 lessons from `demo_target/CONVENTIONS.md` (error envelope, handler
      naming, response models) — retrieval verified, `hit_count` bumping works

## Field note discovered during build
Voyage free-tier keys are limited to **3 requests/minute** until a payment method is
added to the org. `embed()` now retries through the window (25s sleep, 3 attempts),
but back-to-back rehearsals will feel it — consider adding billing before the demo.

## Open questions
- None blocking. One note for Person 2: `search_lessons` returns `_id` as a string
  and no `embedding` field — matches what the CLI/prompt rendering wants.
