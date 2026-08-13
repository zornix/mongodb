"""Demo CLI.

    crew run "add a /orders endpoint"   # run a task; renders lessons retrieved, cycles, diff
    crew resume <thread_id>             # resume a killed run from its Mongo checkpoint
    crew stats                          # run-over-run stats line (the learning curve)
    crew brain                          # dump lessons the crew has accumulated

Every command tries the real backend (repo_brain.crew / repo_brain.brain) first and
falls back to repo_brain.fake_state on NotImplementedError/ImportError, so this lane
never blocks on the others — see plans/demo.md.
"""

from uuid import uuid4

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from repo_brain import fake_state

app = typer.Typer(help="Repo Brain — a coding crew that never cold-starts")
console = Console()


def _run_task(task: str, thread_id: str) -> dict:
    try:
        from repo_brain import crew

        return crew.run_task(task, thread_id)
    except (NotImplementedError, ImportError):
        return fake_state.resolve_run(task)


def _resume_task(thread_id: str) -> dict:
    try:
        from repo_brain import crew

        return crew.run_task(None, thread_id)
    except ValueError as exc:  # no checkpoint for that thread_id — say so, don't fake it
        raise typer.BadParameter(str(exc), param_hint="thread_id") from exc
    except (NotImplementedError, ImportError, TypeError):
        return fake_state.RESUME_STATE


def _brain_stats() -> dict:
    try:
        from repo_brain import brain

        return brain.stats()
    except (NotImplementedError, ImportError):
        return fake_state.FAKE_STATS


def _brain_lessons() -> list[dict]:
    try:
        from repo_brain import brain

        return brain.list_lessons(limit=50)
    except (NotImplementedError, ImportError):
        return fake_state.FAKE_LESSONS


def _render_run(state: dict, thread_id: str) -> None:
    console.print(Panel(state["task"], title="Task", border_style="cyan"))
    console.print(Panel(state["plan"], title="Plan", border_style="blue"))

    lessons_used = state.get("lessons_used") or []
    if lessons_used:
        top_score = max(lesson.get("score", 0.0) for lesson in lessons_used)
        console.print(
            f"\n⚡ {len(lessons_used)} lessons retrieved (score {top_score:.2f})\n",
            style="bold yellow",
        )
        for lesson in lessons_used:
            console.print(f"  • \\[{lesson['type']}] {lesson['rule']}")
        console.print()

    for i, feedback in enumerate(state.get("review_feedback") or [], start=1):
        console.print(Panel(feedback, title=f"Review cycle {i}", border_style="red"))

    # Fixtures are diff-shaped; the real crew emits whole files with === FILE: markers.
    code = state["code"]
    lexer = "diff" if code.lstrip().startswith(("+", "-", "@@")) else "python"
    console.print(Panel(Syntax(code, lexer), title="Final code", border_style="green"))

    cycles = state["cycles"]
    approved = state.get("approved", True)  # fake_state fixtures predate the flag
    if not approved:
        console.print(
            f"[bold red]Stopped after {cycles} correction cycle(s) — still not approved.[/bold red]"
        )
    elif cycles == 0:
        console.print("[bold green]Review passed clean — 0 correction cycles.[/bold green]")
    else:
        console.print(f"[bold]Review passed after {cycles} correction cycle(s).[/bold]")

    console.print(f"\n[dim]thread_id: {thread_id}[/dim]")


@app.command()
def run(task: str):
    """Run a task through the crew and render the full trace."""
    thread_id = str(uuid4())
    state = _run_task(task, thread_id)
    _render_run(state, thread_id)


@app.command()
def resume(thread_id: str):
    """Resume a killed run from its MongoDB checkpoint."""
    state = _resume_task(thread_id)
    resumed_from = state.get("resumed_from", "unknown")
    console.print(f"[bold magenta]Resumed from: {resumed_from}[/bold magenta]\n")
    _render_run(state, thread_id)


@app.command()
def stats():
    """Print the run-over-run learning-curve stats line."""
    data = _brain_stats()

    table = Table(title="Runs")
    table.add_column("Task")
    table.add_column("Cycles", justify="right")
    for entry in data["runs"]:
        table.add_row(entry["task"], str(entry["cycles"]))
    console.print(table)

    console.print(
        f"\nlessons: {data['lessons_total']}, hits: {data['total_hits']}",
        style="bold",
    )


@app.command()
def brain():
    """Dump the lessons the crew has accumulated."""
    lessons = _brain_lessons()

    table = Table(title="Lessons")
    table.add_column("Type")
    table.add_column("Rule")
    table.add_column("Hits", justify="right")
    for lesson in lessons:
        table.add_row(lesson["type"], lesson["rule"], str(lesson.get("hit_count", 0)))
    console.print(table)


if __name__ == "__main__":
    app()
