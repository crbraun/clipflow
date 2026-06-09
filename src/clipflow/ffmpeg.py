from __future__ import annotations

import re
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from clipflow.config import DEFAULT_OVERLAY, DEFAULT_REAR, OverlayConfig, RearConfig
from clipflow.models import JobConfig
from clipflow.progress import (
    PHASE_COMPOSITE,
    PHASE_FORWARD,
    PHASE_REAR,
    JobProgressTracker,
)

console = Console()
TIME_RE = re.compile(r"out_time_ms=(\d+)")


def natural_sort_key(path: Path) -> list[str | int]:
    name = path.name
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def sort_clips(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=natural_sort_key)


def validate_pairing(forward: list[Path], rear: list[Path]) -> None:
    if not forward:
        raise ValueError("Select at least one forward video.")
    if not rear:
        raise ValueError("Select at least one rear video.")
    if len(forward) != len(rear):
        raise ValueError(
            f"Forward and rear clip counts must match ({len(forward)} forward, {len(rear)} rear)."
        )


def write_concat_list(clips: list[Path], list_path: Path) -> None:
    lines = [f"file '{clip.resolve().as_posix()}'" for clip in clips]
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_rear_filter(overlay: OverlayConfig, rear: RearConfig) -> str:
    scale = overlay.scale
    keep_fraction = 1 - rear.bottom_trim_fraction
    chain = f"crop=iw:ih*{keep_fraction}:0:0,scale=iw*{scale}:ih*{scale}"
    if rear.mirror:
        chain = f"{chain},hflip"
    return chain


def build_overlay_filter(overlay: OverlayConfig) -> str:
    rear_filter = build_rear_filter(overlay, DEFAULT_REAR)
    return (
        f"[1:v]{rear_filter}[rear];"
        f"[0:v][rear]overlay={overlay.x_expr}:{overlay.y_expr}[outv]"
    )


def run_ffmpeg(
    args: list[str],
    *,
    description: str,
    on_progress: Callable[[float | None], None] | None = None,
) -> None:
    command = ["ffmpeg", "-hide_banner", "-nostats", "-y", *args]
    if on_progress is None:
        console.print(f"[cyan]{description}[/cyan]")
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "FFmpeg failed.")
        return

    command.extend(["-progress", "pipe:2", "-nostats"])
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stderr is not None
    stderr_lines: list[str] = []
    for line in process.stderr:
        stderr_lines.append(line)
        match = TIME_RE.search(line)
        if match:
            on_progress(int(match.group(1)) / 1_000_000)
    return_code = process.wait()
    if return_code != 0:
        tail = "".join(stderr_lines[-40:]).strip()
        raise RuntimeError(tail or "FFmpeg failed.")


def concat_clips(
    clips: list[Path],
    output_path: Path,
    *,
    on_progress: Callable[[float | None], None] | None = None,
) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        list_path = Path(handle.name)
        write_concat_list(clips, list_path)

    try:
        run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                str(output_path),
            ],
            description=f"Concatenating {len(clips)} clips -> {output_path.name}",
            on_progress=on_progress,
        )
    except RuntimeError:
        run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c:v",
                "libx264",
                "-crf",
                "23",
                "-c:a",
                "aac",
                str(output_path),
            ],
            description=f"Re-encoding concat -> {output_path.name}",
            on_progress=on_progress,
        )
    finally:
        list_path.unlink(missing_ok=True)


def composite_videos(
    forward_path: Path,
    rear_path: Path,
    output_path: Path,
    *,
    overlay: OverlayConfig = DEFAULT_OVERLAY,
    on_progress: Callable[[float | None], None] | None = None,
) -> None:
    filter_graph = build_overlay_filter(overlay)
    run_ffmpeg(
        [
            "-i",
            str(forward_path),
            "-i",
            str(rear_path),
            "-filter_complex",
            filter_graph,
            "-map",
            "[outv]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-crf",
            "23",
            "-preset",
            "medium",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        description=f"Compositing mirror overlay -> {output_path.name}",
        on_progress=on_progress,
    )


def process_job(
    job: JobConfig,
    *,
    overlay: OverlayConfig = DEFAULT_OVERLAY,
    progress: JobProgressTracker | None = None,
) -> Path:
    forward_clips = sort_clips(job.forward_clips)
    rear_clips = sort_clips(job.rear_clips)
    validate_pairing(forward_clips, rear_clips)

    work_dir = job.work_dir or job.output_path.parent / ".clipflow-work"
    work_dir.mkdir(parents=True, exist_ok=True)
    forward_master = work_dir / "forward_concat.mp4"
    rear_master = work_dir / "rear_concat.mp4"

    if progress:
        progress.begin_phase(PHASE_FORWARD)
        concat_clips(forward_clips, forward_master, on_progress=progress.callback(PHASE_FORWARD))
        progress.complete_phase(PHASE_FORWARD)

        progress.begin_phase(PHASE_REAR)
        concat_clips(rear_clips, rear_master, on_progress=progress.callback(PHASE_REAR))
        progress.complete_phase(PHASE_REAR)

        progress.begin_phase(PHASE_COMPOSITE)
        composite_videos(
            forward_master,
            rear_master,
            job.output_path,
            overlay=overlay,
            on_progress=progress.callback(PHASE_COMPOSITE),
        )
        progress.complete_phase(PHASE_COMPOSITE)
        return job.output_path

    concat_clips(forward_clips, forward_master)
    concat_clips(rear_clips, rear_master)
    composite_videos(
        forward_master,
        rear_master,
        job.output_path,
        overlay=overlay,
    )
    return job.output_path
