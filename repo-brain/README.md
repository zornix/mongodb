# Repo Brain

**A coding crew that never cold-starts.** Built for the MongoDB Persistent Context Sprint
Hackathon (.Local Build Fest, San Francisco).

A LangGraph crew (planner → coder → reviewer) works tasks on a small FastAPI codebase.
Every reviewer correction is distilled into a **lesson** (convention, past fix, gotcha)
stored in MongoDB Atlas with vector embeddings. On the next task the coder **retrieves
lessons before writing** — so run 2 measurably behaves differently than run 1.

- **Shared brain**: `lessons` collection in Atlas + Vector Search, consumed by every agent
- **Self-improving**: review feedback → lessons → fewer correction cycles on later tasks
- **Crash-proof**: LangGraph MongoDB checkpointer; kill it mid-task and it resumes
- **Portable memory**: a thin MCP server exposes the same brain, so Claude Code (or any
  MCP client) can read what the crew learned

## Layout

```
src/repo_brain/
  config.py      # env + Mongo client
  brain.py       # the shared memory layer (lessons: add / distill / search)
  crew.py        # LangGraph graph: planner -> coder -> reviewer
  mcp_server.py  # FastMCP server exposing the brain to external agents
  cli.py         # `crew run "<task>"`, `crew stats`, `crew brain`
scripts/
  setup_indexes.py  # creates the Atlas Vector Search index (run once, before demo)
  hello_graph.py    # smoke test: 2-node graph + MongoDB checkpointer round-trip
demo_target/        # seeded toy FastAPI app the crew operates on (demo fixture)
```

## Setup

```bash
uv sync                       # or: pip install -e .
cp .env.example .env          # fill in MONGODB_URI + an LLM key
uv run python scripts/setup_indexes.py
uv run python scripts/hello_graph.py   # verifies Mongo checkpointing works
```

## Hackathon provenance

Committed **before** the event (per the rules, so judges can see the boundary):
project scaffolding, dependencies, this README, the Atlas index setup script, the
`hello_graph.py` smoke test, the seeded demo fixture in `demo_target/`, and **empty
stubs** in `src/repo_brain/` (signatures + TODOs only, no logic).

Built **during** the event: everything that makes this interesting — the lesson
schema/distillation, vector retrieval, the planner/coder/reviewer graph, checkpoint
resume wiring, the MCP server, and the demo CLI.

Patterns were studied (not copied) from MongoDB's
[GenAI-Showcase](https://github.com/mongodb-developer/GenAI-Showcase) (MIT), the
official starter resource for this hackathon.
