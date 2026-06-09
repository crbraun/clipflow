from __future__ import annotations

import typer
from rich.console import Console

from clipflow.config import OverlayConfig
from clipflow.ffmpeg import process_job
from clipflow.interactive import build_job_interactively
from clipflow.progress import create_job_progress

app = typer.Typer(no_args_is_help=False, add_completion=False, help="Race camera merge and mirror composite.")
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Run the interactive clipflow workflow when no subcommand is provided."""
    if ctx.invoked_subcommand is not None:
        return
    run_interactive()


@app.command()
def run() -> None:
    """Interactive workflow: select forward/rear clips and build the composite."""
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

    try:
        with create_job_progress(job.forward_clips, job.rear_clips) as progress:
            output_path = process_job(job, overlay=overlay, progress=progress)
    except RuntimeError as exc:
        console.print(f"\n[red]FFmpeg error:[/red]\n{exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(f"\n[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"\n[green]Done.[/green] Saved to [bold]{output_path}[/bold]")


if __name__ == "__main__":
    app()
