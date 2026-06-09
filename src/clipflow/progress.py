from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from clipflow.probe import total_duration

PHASE_PAIRS = "pairs"
PHASE_CONCAT = "concat"

PHASE_LABELS = {
    PHASE_PAIRS: "Phase 1/2: Sync and composite clips",
    PHASE_CONCAT: "Phase 2/2: Concat segments",
}


class JobProgressTracker:
    def __init__(
        self,
        pairs_seconds: float | None,
        concat_seconds: float | None,
    ) -> None:
        self._durations = {
            PHASE_PAIRS: pairs_seconds,
            PHASE_CONCAT: concat_seconds,
        }
        self._tasks: dict[str, TaskID] = {}
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=False,
        )

    def __enter__(self) -> JobProgressTracker:
        self.progress.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.progress.stop()

    def begin_phase(self, phase: str) -> None:
        duration = self._durations[phase]
        total = duration if duration and duration > 0 else None
        task_id = self.progress.add_task(PHASE_LABELS[phase], total=total)
        self._tasks[phase] = task_id

    def update(self, phase: str, seconds: float | None) -> None:
        if seconds is None or phase not in self._tasks:
            return
        duration = self._durations[phase]
        completed = min(seconds, duration) if duration and duration > 0 else seconds
        self.progress.update(self._tasks[phase], completed=completed)

    def complete_phase(self, phase: str) -> None:
        if phase not in self._tasks:
            return
        duration = self._durations[phase]
        if duration and duration > 0:
            self.progress.update(self._tasks[phase], completed=duration)

    def callback(self, phase: str) -> Callable[[float | None], None]:
        return lambda seconds: self.update(phase, seconds)


def create_job_progress(forward_clips: list[Path], rear_clips: list[Path]) -> JobProgressTracker:
    try:
        total_seconds = total_duration(forward_clips)
    except RuntimeError:
        total_seconds = None

    return JobProgressTracker(total_seconds, total_seconds)
