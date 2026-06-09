from __future__ import annotations

from datetime import datetime
from pathlib import Path

from clipflow.ffmpeg import sort_clips


def format_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def format_video_label(path: Path) -> str:
    return f"{format_mtime(path)}  {path.name}"


def match_rear_by_mtime(forward_clips: list[Path], rear_candidates: list[Path]) -> list[Path]:
    """Pair each forward clip with the closest unused rear clip by modified time."""
    forward_sorted = sort_clips(forward_clips)
    if not rear_candidates:
        raise ValueError("No rear videos available to match.")

    available = list(rear_candidates)
    matched: list[Path] = []
    for forward in forward_sorted:
        if not available:
            raise ValueError(
                f"Not enough rear clips to match {len(forward_sorted)} forward clips "
                f"({len(forward_sorted) - len(matched)} unmatched)."
            )
        forward_mtime = forward.stat().st_mtime
        best_rear = min(available, key=lambda rear: abs(rear.stat().st_mtime - forward_mtime))
        available.remove(best_rear)
        matched.append(best_rear)
    return matched
