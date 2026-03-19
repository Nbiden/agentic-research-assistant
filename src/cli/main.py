"""CLI entry point for the Agentic Research Assistant.

Provides the `research-agent` command via Typer. Accepts a research question
as a positional argument or from stdin, runs the LangGraph agent, and outputs
either a human-readable formatted response or raw JSON.

Exit codes (per contracts/api.md):
    0 — Success
    1 — Input validation error
    2 — Agent error (tools failed, LLM fallback used)
    3 — Fatal error (LLM itself unavailable)
"""

from __future__ import annotations

import asyncio
import sys

import structlog
import typer
from rich.console import Console
from rich.rule import Rule
from rich.text import Text

from src.models.response import ResearchResponse

app = typer.Typer(
    name="research-agent",
    help="Agentic Research Assistant powered by LangGraph and Claude.",
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)
logger = structlog.get_logger(__name__)


def _read_question_from_stdin() -> str | None:
    """Read a research question from stdin if it is not a TTY."""
    if not sys.stdin.isatty():
        return sys.stdin.read().strip() or None
    return None


def _format_human_output(response: ResearchResponse) -> None:
    """Print a human-readable response to stdout."""

    console.print()
    console.print(Rule("[bold green]Answer[/bold green]"))
    console.print(Text(response.answer))
    console.print()

    if response.sources:
        console.print(Rule("[bold blue]Sources[/bold blue]"))
        for idx, source in enumerate(response.sources, start=1):
            type_label = source.source_type.value
            title = f" — {source.title}" if source.title else ""
            console.print(
                f"[{idx}] [cyan]{source.identifier}[/cyan]{title} "
                f"({type_label}, relevance: {source.relevance_score:.2f})"
            )
        console.print()

    trace_info = ""
    if response.decision_trace:
        tool_names = [tc.tool_name for tc in response.decision_trace.tool_calls]
        trace_info = f"  |  Tools: {', '.join(tool_names) if tool_names else 'none'}"

    status = "[yellow]DEGRADED[/yellow]" if response.degraded else "[green]OK[/green]"
    console.print(
        f"Confidence: [bold]{response.confidence_score:.2f}[/bold]"
        f"{trace_info}  |  Status: {status}"
    )
    console.print()


@app.command()
def main(
    question: str | None = typer.Argument(  # noqa: UP007
        default=None,
        help="Research question (reads from stdin if omitted).",
    ),
    max_sources: int = typer.Option(5, "--max-sources", "-n", help="Max sources to return."),
    no_trace: bool = typer.Option(False, "--no-trace", help="Suppress decision trace."),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
) -> None:
    """Submit a research question and receive a cited structured answer."""
    # Resolve the question from argument or stdin.
    resolved_question = question or _read_question_from_stdin()
    if not resolved_question:
        err_console.print("[red]Error:[/red] No question provided. Pass as argument or via stdin.")
        raise typer.Exit(code=1)

    if len(resolved_question) > 2000:
        err_console.print("[red]Error:[/red] Question exceeds 2000 characters.")
        raise typer.Exit(code=1)

    # Import here to avoid loading heavy deps until actually needed.
    import src.tools  # noqa: F401 — triggers tool registration
    from src.agent.graph import run

    try:
        response = asyncio.run(
            run(
                question=resolved_question,
                max_sources=max_sources,
                include_trace=not no_trace,
            )
        )
    except KeyboardInterrupt:
        err_console.print("\n[yellow]Interrupted.[/yellow]")
        raise typer.Exit(code=2) from None
    except Exception as exc:  # noqa: BLE001
        logger.error("cli.fatal_error", error=str(exc))
        err_console.print(f"[red]Fatal error:[/red] {exc}")
        raise typer.Exit(code=3) from None

    if as_json:
        typer.echo(response.model_dump_json(indent=2))
    else:
        _format_human_output(response)

    exit_code = 2 if response.degraded else 0
    raise typer.Exit(code=exit_code)


if __name__ == "__main__":
    app()
