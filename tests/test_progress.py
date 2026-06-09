from __future__ import annotations

from clipflow.progress import PHASE_COMPOSITE, PHASE_FORWARD, JobProgressTracker


def test_job_progress_tracker_updates_and_completes_phases() -> None:
    tracker = JobProgressTracker(forward_seconds=100.0, rear_seconds=80.0, composite_seconds=100.0)
    tracker.begin_phase(PHASE_FORWARD)
    tracker.update(PHASE_FORWARD, 25.0)
    tracker.complete_phase(PHASE_FORWARD)
    tracker.begin_phase(PHASE_COMPOSITE)
    tracker.update(PHASE_COMPOSITE, 50.0)
    tracker.complete_phase(PHASE_COMPOSITE)
