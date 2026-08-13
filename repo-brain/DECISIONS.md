# Repo Brain — Idea & Decisions

Scoping record for the MongoDB Persistent Context Sprint Hackathon (.Local Build Fest,
Pier 48, San Francisco). Written pre-event, 2026-08-13.

## The idea

**A coding crew that never cold-starts.**

A LangGraph crew — planner → coder → reviewer — works tasks on a small FastAPI codebase.
Every reviewer correction is distilled into a **lesson** (a convention, a past fix, a
gotcha) stored in MongoDB Atlas with vector embeddings. On the next task, the coder
**retrieves relevant lessons before writing a line of code**. So run 2 measurably behaves
differently than run 1: fewer correction cycles, conventions applied up front. The stored
memory changes what the system does next — it doesn't just fill the prompt.

Three persistence mechanisms, all in MongoDB:

| Mechanism | MongoDB feature | What it demos |
|---|---|---|
| Shared brain (`lessons` collection) | Atlas Vector Search | Coder retrieves reviewer's past feedback before writing |
| Self-improvement | outcome stats + `hit_count` | Run-over-run correction cycles drop; stats line proves it |
| Crash recovery | `langgraph-checkpoint-mongodb` | kill -9 mid-task → restart → resumes at the exact node |
| Portable memory (kicker) | same brain via MCP server | Claude Code answers questions from what the crew learned |

## Hackathon constraints that shaped the scope

- **Theme "No Cold Start"**: stored context must change behavior, not just fill prompts.
  Our cold/warm task contrast is a direct proof of that.
- **~3.5 hours of hacking** (1:30–5:00 PM), then 1-minute demo video + public repo.
- **Judging**: Creativity & Originality 35%, Demo 30%, Impact 20%. A novel, working,
  tightly staged demo beats an ambitious half-working one.
- **Banned projects**: basic RAG, Streamlit apps, dashboards-as-main-feature, basic
  chatbots, job screeners, etc. — we're in none of those categories; this is literally
  one of the guide's own example project shapes ("a coding agent that keeps repo
  conventions and past fixes in Atlas… and checkpoints through LangGraph").
- **New Work Only rule**: judges must clearly see what was built during the event.
  Drives the stubs-only skeleton and the labeled pre-event boundary commit.

## Decisions (from the scoping interview)

| # | Decision | Choice | Why (and what we rejected) |
|---|---|---|---|
| 1 | Team | 3–4 people | Full team; can parallelize crew / brain / demo / MCP. |
| 2 | Theme flavor | Coding-agent memory, blending in multi-agent shared brain + self-improvement | User liked all three flavors; this idea composes them into one architecture. Rejected voice/ElevenLabs track. |
| 3 | Stack | Python | Fastest under pressure; best scavenging surface (most GenAI-Showcase examples are Python). |
| 4 | Goal | Learn + solid demo | Lower-risk idea over a weirder moonshot; still competitive on the criteria. |
| 5 | Project | **Coding crew w/ repo brain** | Over DevOps incident crew, self-tuning research crew, and voice-fronted ops crew. Matches the guide's blessed example; cleanest cold/warm demo. |
| 6 | Demo surface | Terminal, well-staged (Rich output) | Zero frontend time; all hours go into the mechanism. Rejected web view (costs a person's afternoon). |
| 7 | Architecture | **Hybrid: LangGraph crew + MCP server** | Crew from scratch = deterministic, stageable, native Mongo checkpointer. MCP server on the same data layer adds the creativity kicker (memory portable to Claude Code). Rejected building *only* around real CLIs (Claude Code/Codex) — live-demo nondeterminism risk. MCP server is the **designated cut** if time runs short; the crew demo stands alone. |
| 8 | Demo codebase | **Seeded toy FastAPI app** (`demo_target/`) | Deliberate, visible conventions; scripted tasks; deterministic 1-minute staging. Rejected using a real repo (high variance). |
| 9 | Provenance | Stubs-only pre-event skeleton, labeled boundary commit | Rules compliance: mechanism logic (brain, crew, MCP, CLI) is all event-day work. Copy *ideas* from GenAI-Showcase (MIT), not files; attribute in README. |

## The 1-minute demo script

1. **Task 1 (cold)** — `crew run "add a /items endpoint"`: reviewer flags 3 convention
   violations (error envelope, handler naming, test naming); 2 correction cycles.
   Terminal shows lessons being written to Atlas.
2. **Task 2 (warm)** — `crew run "add a /orders endpoint"`: terminal shows
   `⚡ 3 lessons retrieved (score 0.89)` before the coder writes. Review passes clean,
   0 cycles. Show the run-1 vs run-2 stats line.
3. **Crash** — kill -9 mid-task 3, restart, resumes from the MongoDB checkpoint at the
   exact node.
4. **Kicker** — Claude Code with the repo-brain MCP attached answers "what conventions
   does this repo have?" from the crew's memory.

## Team split & timeline

- **A — Crew core**: LangGraph graph (planner/coder/reviewer), checkpointer wiring.
- **B — Brain**: `lessons` data layer (build **first**; everything consumes it):
  `{type, rule, evidence, source_task, embedding, hit_count, created_at}`, distillation,
  vector retrieval.
- **C — Demo surface**: scripted tasks, Rich terminal output, run stats; **records the
  video by 4:45**.
- **D — MCP server**: FastMCP exposing `search_lessons` / `add_lesson` / `brain_stats`
  over B's module. First thing cut if behind.

Timeline: 1:30–2:00 wire skeleton + Atlas together · 2:00–3:30 parallel build ·
3:30–4:15 integrate, run full demo loop repeatedly · 4:15–4:45 polish + record ·
5:00 submit (public repo, all members on the form).

## Tech choices

- LangGraph + `langgraph-checkpoint-mongodb` (MongoDBSaver) for the crew and resume.
- Atlas Vector Search: 1536-dim cosine index on `lessons.embedding`
  (OpenAI `text-embedding-3-small`).
- Anthropic (or OpenRouter credits) for the crew LLM; `rich` + `typer` for the CLI;
  `fastmcp` for the MCP server.

## Pre-event checklist

- [x] Skeleton repo scaffolded, deps verified on Python 3.14, fixture tests pass,
  boundary commit made
- [ ] Fill `.env` (Atlas URI + LLM key)
- [ ] `uv run python scripts/setup_indexes.py` (index builds take minutes — don't do live)
- [ ] `uv run python scripts/hello_graph.py` twice (second run must print "resumed")
- [ ] Push public: `gh repo create repo-brain --public --source . --push`
- [ ] Skim the "Build an AI Agent with LangGraph and MongoDB Atlas" tutorial from the guide
