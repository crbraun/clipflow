from clipflow.progress import PHASE_CONCAT, PHASE_PAIRS, JobProgressTracker


def test_job_progress_tracker_updates_and_completes_phases() -> None:
    tracker = JobProgressTracker(pairs_seconds=100.0, concat_seconds=100.0)
    tracker.begin_phase(PHASE_PAIRS)
    tracker.update(PHASE_PAIRS, 25.0)
    tracker.complete_phase(PHASE_PAIRS)
    tracker.begin_phase(PHASE_CONCAT)
    tracker.update(PHASE_CONCAT, 50.0)
    tracker.complete_phase(PHASE_CONCAT)
