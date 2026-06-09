from __future__ import annotations

from collections.abc import Callable

from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn


def create_progress_callback(label: str) -> tuple[Progress, Callable[[float | None], None]]:
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        transient=False,
    )
    task_id = progress.add_task(label, total=None)

    def update(seconds: float | None) -> None:
        if seconds is None:
            return
        if progress.tasks[task_id].total is None:
            progress.update(task_id, total=max(seconds * 2, 1))
        progress.update(task_id, completed=min(seconds, progress.tasks[task_id].total or seconds))

    return progress, update
