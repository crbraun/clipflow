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


def _first_packet_pts(path: Path, stream: str) -> float | None:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            stream,
            "-show_entries",
            "packet=pts_time",
            "-read_intervals",
            "0%+#1",
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

    value = result.stdout.strip().splitlines()
    if not value or value[0] == "N/A":
        return None
    return float(value[0])


def probe_av_offset(path: Path) -> float:
    """Seconds the first video packet trails the first audio packet."""
    video_pts = _first_packet_pts(path, "v:0")
    audio_pts = _first_packet_pts(path, "a:0")
    if video_pts is None or audio_pts is None:
        return 0.0
    return max(0.0, video_pts - audio_pts)


def probe_frame_rate(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=avg_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Could not probe frame rate for {path.name}")

    value = result.stdout.strip()
    if not value or value == "N/A" or value == "0/0":
        raise RuntimeError(f"No frame rate found for {path.name}")

    if "/" in value:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator)
    return float(value)


# AiM forward MOVs mux video ~1s after audio; our H.264 re-encode shifts picture earlier
# by roughly one GOP of frames unless audio is advanced at the final mux step.
REENCODE_FRAME_LEAD = 23


def compute_audio_advance_seconds(forward: Path) -> float:
    offset = probe_av_offset(forward)
    if offset <= 0:
        return 0.0
    frame_rate = probe_frame_rate(forward)
    return offset + (REENCODE_FRAME_LEAD / frame_rate)
