"""Smoke test: a 2-node LangGraph with the MongoDB checkpointer, no LLM needed.

Verifies before the event that:
  1. langgraph + langgraph-checkpoint-mongodb import and run on this machine
  2. the Atlas cluster accepts checkpoint writes
  3. a second invocation on the same thread_id resumes prior state (count keeps growing)

    uv run python scripts/hello_graph.py
"""

from typing import TypedDict

from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph import END, START, StateGraph

from repo_brain.config import MONGODB_DB, MONGODB_URI


class State(TypedDict):
    count: int
    log: list[str]


def step_a(state: State) -> dict:
    return {"count": state["count"] + 1, "log": state["log"] + ["a ran"]}


def step_b(state: State) -> dict:
    return {"count": state["count"] + 1, "log": state["log"] + ["b ran"]}


def main() -> None:
    graph = StateGraph(State)
    graph.add_node("a", step_a)
    graph.add_node("b", step_b)
    graph.add_edge(START, "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", END)

    with MongoDBSaver.from_conn_string(MONGODB_URI, db_name=MONGODB_DB) as saver:
        app = graph.compile(checkpointer=saver)
        config = {"configurable": {"thread_id": "hello-graph-smoke-test"}}

        prior = app.get_state(config)
        start_count = (prior.values or {}).get("count", 0)
        result = app.invoke({"count": start_count, "log": []}, config)

        print(f"run finished: count={result['count']}, log={result['log']}")
        if start_count:
            print(f"resumed from checkpointed count={start_count} — persistence works ✔")
        else:
            print("first run checkpointed — run again to see it resume ✔")


if __name__ == "__main__":
    main()
