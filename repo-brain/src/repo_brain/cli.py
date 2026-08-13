"""Demo CLI.

    crew run "add a /orders endpoint"   # run a task; renders lessons retrieved, cycles, diff
    crew resume <thread_id>             # resume a killed run from its Mongo checkpoint
    crew stats                          # run-over-run stats line (the learning curve)
    crew brain                          # dump lessons the crew has accumulated
    crew model [name]                   # show / switch the Gemini model (daily quota is per model)

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

from repo_brain import config, fake_state

app = typer.Typer(help="Repo Brain — a coding crew that never cold-starts")
console = Console()

MODEL_OPTION = typer.Option(
    None,
    "--model",
    "-m",
    help="Gemini model for this run (alias ok: 3.1, 3.5). Free-tier quota is per model.",
)


def _use_model(name: str | None) -> None:
    """Apply a --model override for this process only (nothing written to .env)."""
    if name:
        console.print(f"[dim]model: {config.set_gemini_model(name)}[/dim]")


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
def run(
    task: str,
    model: str | None = MODEL_OPTION,
    thread_id: str | None = typer.Option(
        None, "--thread-id", "-t", help="Reuse a known id so a killed run is easy to resume."
    ),
):
    """Run a task through the crew and render the full trace."""
    _use_model(model)
    thread_id = thread_id or str(uuid4())
    # Printed up front as well as at the end: the crash demo kills this mid-run, and you
    # can't resume a thread_id you never saw.
    console.print(f"[dim]thread_id: {thread_id}[/dim]")
    state = _run_task(task, thread_id)
    _render_run(state, thread_id)


@app.command()
def resume(thread_id: str, model: str | None = MODEL_OPTION):
    """Resume a killed run from its MongoDB checkpoint."""
    _use_model(model)
    state = _resume_task(thread_id)
    # resumed_from is None when the checkpoint is already complete — that's a free replay
    # of a finished run (no LLM calls), not a resume. Say which one happened.
    resumed_from = state.get("resumed_from")
    if resumed_from:
        console.print(f"[bold magenta]Resumed from: {resumed_from}[/bold magenta]\n")
    else:
        console.print(
            "[bold magenta]Run already complete — replayed from checkpoint[/bold magenta]\n"
        )
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


@app.command()
def model(
    name: str | None = typer.Argument(
        None, help="Model id or alias (3.1, 3.5). Omit to just show the current one."
    ),
    list_available: bool = typer.Option(
        False, "--list", "-l", help="Ask the API which models this key can call."
    ),
):
    """Show or switch the Gemini model (quota is per model; a cold run costs ~8 calls)."""
    if name:
        chosen = config.set_gemini_model(name, persist=True)
        console.print(
            f"[bold green]GEMINI_MODEL={chosen}[/bold green] [dim](written to .env)[/dim]"
        )
    else:
        console.print(f"[bold]GEMINI_MODEL={config.GEMINI_MODEL}[/bold]")
        console.print("[dim]demo models: " + ", ".join(config.DEMO_MODELS) + "[/dim]")

    if list_available:
        try:
            names = config.available_models()
        except Exception as exc:  # network/key problems shouldn't dump a traceback on stage
            console.print(f"[red]could not list models: {exc}[/red]")
            raise typer.Exit(1) from exc
        table = Table(title="Models this key can call")
        table.add_column("Model")
        for available in names:
            table.add_row(available)
        console.print(table)


if __name__ == "__main__":
    app()
