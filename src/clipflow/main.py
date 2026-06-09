from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from clipflow.config import OverlayConfig
from clipflow.ffmpeg import process_job
from clipflow.interactive import build_job_interactively
from clipflow.progress import create_progress_callback

app = typer.Typer(no_args_is_help=False, add_completion=False, help="Race camera merge and mirror composite.")
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Run the interactive clipflow workflow when no subcommand is provided."""
    if ctx.invoked_subcommand is not None:
        return
    run_interactive()


@app.command()
def run(
    output: Path = typer.Option(
        Path("race-composite.mp4"),
        "--output",
        "-o",
        help="Output MP4 path.",
    ),
    scale: float = typer.Option(
        0.10,
        "--scale",
        min=0.01,
        max=1.0,
        help="Rear inset scale after crop (fraction).",
    ),
) -> None:
    """Interactive workflow: select forward/rear clips and build the composite."""
    _ = output
    _ = scale
    run_interactive()


def run_interactive() -> None:
    try:
        job = build_job_interactively()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    overlay = OverlayConfig(scale=job.overlay_scale)
    progress, update = create_progress_callback("Processing video")

    try:
        with progress:
            output_path = process_job(job, overlay=overlay, on_progress=update)
    except RuntimeError as exc:
        console.print(f"\n[red]FFmpeg error:[/red]\n{exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(f"\n[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"\n[green]Done.[/green] Saved to [bold]{output_path}[/bold]")


if __name__ == "__main__":
    app()
