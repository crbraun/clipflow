from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from clipflow.audiosync import MIN_CONFIDENCE, estimate_audio_offset
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


@dataclass(frozen=True)
class RearSync:
    """Resolved rear overlay timing for a forward/rear pair."""

    delay: float
    trim: float
    offset: float
    source: str  # "audio" or "metadata"
    confidence: float | None = None


def _resolve_rear_sync(forward: Path, rear: Path) -> RearSync:
    metadata_offset = clip_start_timestamp(rear) - clip_start_timestamp(forward)

    offset = metadata_offset
    source = "metadata"
    confidence: float | None = None

    audio = estimate_audio_offset(forward, rear, prior_seconds=metadata_offset)
    if audio is not None:
        confidence = audio.confidence
        if audio.confidence >= MIN_CONFIDENCE:
            offset = audio.seconds
            source = "audio"

    return RearSync(
        delay=max(0.0, offset),
        trim=max(0.0, -offset),
        offset=offset,
        source=source,
        confidence=confidence,
    )


def _file_key(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return (str(path), stat.st_size, int(stat.st_mtime))


@lru_cache(maxsize=None)
def _resolve_rear_sync_cached(forward_key: tuple, rear_key: tuple) -> RearSync:
    return _resolve_rear_sync(Path(forward_key[0]), Path(rear_key[0]))


def resolve_rear_sync(forward: Path, rear: Path) -> RearSync:
    """Resolve rear overlay timing, preferring audio correlation over metadata.

    Cached per (path, size, mtime) so the pairing preview and the encode pass
    share a single audio analysis per clip pair.
    """
    return _resolve_rear_sync_cached(_file_key(forward), _file_key(rear))


def compute_rear_sync(forward: Path, rear: Path) -> tuple[float, float]:
    """Return overlay delay and rear trim start (seconds)."""
    result = resolve_rear_sync(forward, rear)
    return result.delay, result.trim
