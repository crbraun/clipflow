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

PHASE_FORWARD = "forward"
PHASE_REAR = "rear"
PHASE_COMPOSITE = "composite"

PHASE_LABELS = {
    PHASE_FORWARD: "Phase 1/3: Concat forward",
    PHASE_REAR: "Phase 2/3: Concat rear",
    PHASE_COMPOSITE: "Phase 3/3: Composite overlay",
}


class JobProgressTracker:
    def __init__(
        self,
        forward_seconds: float | None,
        rear_seconds: float | None,
        composite_seconds: float | None,
    ) -> None:
        self._durations = {
            PHASE_FORWARD: forward_seconds,
            PHASE_REAR: rear_seconds,
            PHASE_COMPOSITE: composite_seconds,
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
        forward_seconds = total_duration(forward_clips)
        rear_seconds = total_duration(rear_clips)
        composite_seconds = forward_seconds
    except RuntimeError:
        forward_seconds = None
        rear_seconds = None
        composite_seconds = None

    return JobProgressTracker(forward_seconds, rear_seconds, composite_seconds)
