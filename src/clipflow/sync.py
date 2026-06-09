from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from clipflow.probe import probe_duration


def probe_video_creation_time(path: Path) -> float | None:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format_tags=creation_time",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None

    value = result.stdout.strip()
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).timestamp()


def file_recording_end_time(path: Path) -> float:
    """File modified time when camera files use mtime as recording end."""
    return path.stat().st_mtime


def file_recording_start_time(path: Path) -> float:
    """Estimate recording start from file end time minus duration."""
    return file_recording_end_time(path) - probe_duration(path)


def clip_start_timestamp(path: Path) -> float:
    metadata_time = probe_video_creation_time(path)
    if metadata_time is not None:
        return metadata_time
    return file_recording_start_time(path)


def timestamp_sync_offset(forward: Path, rear: Path) -> tuple[float, float]:
    """Return overlay delay and rear trim start (seconds) from clip start timestamps."""
    delta = clip_start_timestamp(rear) - clip_start_timestamp(forward)
    sync_offset = max(0.0, delta)
    trim = max(0.0, -delta)
    return sync_offset, trim


def compute_rear_sync(forward: Path, rear: Path) -> tuple[float, float]:
    """Return overlay delay and rear trim start (seconds)."""
    return timestamp_sync_offset(forward, rear)
