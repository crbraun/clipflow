from __future__ import annotations

from pathlib import Path

import questionary
from questionary import Style
from rich.console import Console
from rich.table import Table

from clipflow.ffmpeg import sort_clips, validate_pairing
from clipflow.matching import format_mtime, format_video_label, match_rear_by_mtime
from clipflow.models import JobConfig

console = Console()
PROMPT_STYLE = Style([("qmark", "fg:cyan bold"), ("question", "bold")])


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() == ".mov"


def discover_videos(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise ValueError(f"Directory not found: {directory}")
    return sorted(
        [path for path in directory.iterdir() if path.is_file() and is_video_file(path)],
        key=lambda path: path.stat().st_mtime,
    )


def ask_directory(prompt: str, default: Path) -> Path:
    answer = questionary.path(
        prompt,
        default=str(default),
        only_directories=True,
        style=PROMPT_STYLE,
    ).ask()
    if answer is None:
        raise KeyboardInterrupt
    return Path(answer).expanduser().resolve()


def ask_video_selection(label: str, directory: Path) -> list[Path]:
    videos = discover_videos(directory)
    if not videos:
        raise ValueError(f"No .MOV files found in {directory}")

    choices = [
        questionary.Choice(title=format_video_label(video), value=video, checked=False)
        for video in videos
    ]
    selected = questionary.checkbox(
        f"{label} (sorted by modified time; timeline order uses filename after selection)",
        choices=choices,
        style=PROMPT_STYLE,
        validate=lambda value: True if value else "Select at least one clip.",
    ).ask()
    if selected is None:
        raise KeyboardInterrupt
    return [Path(path) for path in selected]


def show_pairing_preview(forward_sorted: list[Path], rear_matched: list[Path]) -> None:
    validate_pairing(forward_sorted, rear_matched)

    table = Table(title="Clip pairing (forward sorted by filename, rear matched by modified time)")
    table.add_column("#", justify="right")
    table.add_column("Forward")
    table.add_column("Forward modified")
    table.add_column("Rear")
    table.add_column("Rear modified")
    for index, (front, back) in enumerate(zip(forward_sorted, rear_matched), start=1):
        table.add_row(
            str(index),
            front.name,
            format_mtime(front),
            back.name,
            format_mtime(back),
        )
    console.print(table)


def ask_output_path(default: Path) -> Path:
    answer = questionary.path(
        "Output MP4 path",
        default=str(default),
        style=PROMPT_STYLE,
    ).ask()
    if answer is None:
        raise KeyboardInterrupt
    path = Path(answer).expanduser().resolve()
    if path.suffix.lower() != ".mp4":
        path = path.with_suffix(".mp4")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def ask_overlay_scale(default: float = 0.10) -> float:
    answer = questionary.text(
        "Rear inset scale (fraction of cropped rear size)",
        default=str(default),
        validate=lambda value: _validate_scale(value),
        style=PROMPT_STYLE,
    ).ask()
    if answer is None:
        raise KeyboardInterrupt
    return float(answer)


def _validate_scale(value: str) -> bool | str:
    try:
        number = float(value)
    except ValueError:
        return "Enter a number, e.g. 0.10"
    if not 0.01 <= number <= 1.0:
        return "Scale must be between 0.01 and 1.0"
    return True


def build_job_interactively(start_dir: Path | None = None) -> JobConfig:
    base_dir = (start_dir or Path.cwd()).resolve()
    console.print("[bold]Clipflow[/bold] — race camera merge + mirror composite")
    console.print(f"Starting directory: [dim]{base_dir}[/dim]\n")

    forward_dir = ask_directory("Forward camera folder", base_dir)
    rear_dir = ask_directory("Rear camera folder", forward_dir.parent if forward_dir.parent.exists() else base_dir)

    forward = ask_video_selection("Select forward clips", forward_dir)
    rear_pool = discover_videos(rear_dir)
    if not rear_pool:
        raise ValueError(f"No .MOV files found in {rear_dir}")

    forward_sorted = sort_clips(forward)
    rear_matched = match_rear_by_mtime(forward, rear_pool)
    console.print(
        f"[green]Auto-selected {len(rear_matched)} rear clip(s)[/green] "
        "by closest modified time to each forward clip.\n"
    )

    show_pairing_preview(forward_sorted, rear_matched)

    if not questionary.confirm("Proceed with this pairing?", default=True, style=PROMPT_STYLE).ask():
        raise KeyboardInterrupt

    output_path = ask_output_path(base_dir / "race-composite.mp4")
    overlay_scale = ask_overlay_scale()

    return JobConfig(
        forward_clips=forward_sorted,
        rear_clips=rear_matched,
        output_path=output_path,
        overlay_scale=overlay_scale,
        work_dir=output_path.parent / ".clipflow-work",
    )
