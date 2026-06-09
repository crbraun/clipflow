from __future__ import annotations

from datetime import datetime
from pathlib import Path

from clipflow.ffmpeg import sort_clips
from clipflow.sync import clip_start_timestamp, resolve_rear_sync


def format_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def format_mtime(path: Path) -> str:
    return format_timestamp(path.stat().st_mtime)


def format_creation_time(path: Path) -> str:
    return format_timestamp(clip_start_timestamp(path))


def format_sync_delay(forward: Path, rear: Path) -> str:
    result = resolve_rear_sync(forward, rear)

    if result.trim > 0:
        timing = f"trim {result.trim:.1f}s rear"
    elif result.delay > 0:
        timing = f"+{result.delay:.1f}s overlay"
    else:
        timing = "aligned"

    if result.source == "audio" and result.confidence is not None:
        method = f"audio {result.confidence:.2f}"
    elif result.confidence is not None:
        method = f"metadata (audio {result.confidence:.2f} too weak)"
    else:
        method = "metadata"
    return f"{timing} [{method}]"


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
