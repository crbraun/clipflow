from __future__ import annotations

import subprocess
from pathlib import Path


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Could not probe duration for {path.name}")

    value = result.stdout.strip()
    if not value or value == "N/A":
        raise RuntimeError(f"No duration found for {path.name}")

    duration = float(value)
    if duration <= 0:
        raise RuntimeError(f"Invalid duration for {path.name}: {duration}")
    return duration


def total_duration(clips: list[Path]) -> float:
    return sum(probe_duration(clip) for clip in clips)
