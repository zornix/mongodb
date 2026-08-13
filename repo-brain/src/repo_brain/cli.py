"""Demo CLI. Planned commands (implemented at the event):

    crew run "add a /orders endpoint"   # run a task; renders lessons retrieved, cycles, diff
    crew resume <thread_id>             # resume a killed run from its Mongo checkpoint
    crew stats                          # run-over-run stats line (the learning curve)
    crew brain                          # dump lessons the crew has accumulated

STUB ONLY — implemented during the hackathon.
"""

import typer

app = typer.Typer(help="Repo Brain — a coding crew that never cold-starts")


@app.command()
def run(task: str):
    raise NotImplementedError("event-day work")


if __name__ == "__main__":
    app()
