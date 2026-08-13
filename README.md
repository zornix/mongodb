# mongodb

Workspace for the **MongoDB Persistent Context Sprint Hackathon** (.Local Build Fest,
Pier 48, San Francisco, 2026-08-13). The hackathon submission is **Repo Brain**; the
rest of this workspace is supporting tooling (MongoDB agent skills for coding agents).

## Repo Brain — the submission

**A coding crew that never cold-starts.**

A LangGraph crew (planner → coder → reviewer) works tasks on a small seeded FastAPI
codebase. Every reviewer correction is distilled into a **lesson** (a convention, a
past fix, a gotcha) and stored in MongoDB Atlas with vector embeddings. On the next
task, the coder retrieves relevant lessons *before* writing a line of code — so a
"warm" run measurably behaves differently than a "cold" one: fewer correction cycles,
conventions applied up front.

Three persistence mechanisms, all MongoDB:

| Mechanism | MongoDB feature | What it demos |
|---|---|---|
| Shared brain (`lessons` collection) | Atlas Vector Search | Coder retrieves reviewer's past feedback before writing |
| Self-improvement | outcome stats + `hit_count` | Run-over-run correction cycles drop; stats prove it |
| Crash recovery | `langgraph-checkpoint-mongodb` | Kill mid-task → restart → resumes at the exact node |
| Portable memory (kicker) | same brain, via MCP server | Claude Code (or any MCP client) answers questions from what the crew learned |

Status as of the last commit: the brain + MCP layer (`brain.py`, `mcp_server.py`) is
implemented and verified against live Atlas/Voyage/Gemini services; the crew graph
(`crew.py`) and demo CLI (`cli.py`) are stubs with a fixed data contract between them,
next up to be built out.

Full architecture, the frozen data contracts, setup instructions, and the scoping
decisions behind the project live in:

- [`repo-brain/README.md`](repo-brain/README.md) — architecture, module-by-module
  breakdown, Atlas collection layout, setup/run instructions
- [`repo-brain/DECISIONS.md`](repo-brain/DECISIONS.md) — pre-event scoping record,
  demo script, hackathon constraints
- [`repo-brain/TEAM_SPLIT.md`](repo-brain/TEAM_SPLIT.md) — the 3-person lane split and
  frozen contracts each lane codes against

## Everything else in this workspace

Supporting tooling for coding agents working in this repo — not part of the hackathon
submission itself:

- **`agent-skills/`** — a checkout of MongoDB's official
  [`mongodb/agent-skills`](https://github.com/mongodb/agent-skills) repo (its own git
  history), the source of the MongoDB skills installed below.
- **`.claude/skills/`, `.agents/skills/`, `skills-lock.json`** — MongoDB agent skills
  (connection tuning, schema design, query optimization, Atlas Search/Vector Search,
  natural-language querying, stream processing) installed for use by coding agents in
  this workspace, pinned by hash in `skills-lock.json`.
- **`start.py`** — a scratch MongoDB connectivity smoke test.

## Setup

See [`repo-brain/README.md`](repo-brain/README.md#setup) for installing dependencies
(`uv sync`), configuring `repo-brain/.env`, and running the index setup / checkpoint
smoke test.
