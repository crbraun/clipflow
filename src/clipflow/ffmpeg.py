from __future__ import annotations

import re
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from clipflow.config import DEFAULT_OVERLAY, DEFAULT_REAR, OverlayConfig, RearConfig
from clipflow.models import JobConfig
from clipflow.probe import compute_audio_advance_seconds, probe_duration
from clipflow.progress import PHASE_CONCAT, PHASE_PAIRS, JobProgressTracker
from clipflow.sync import compute_rear_sync

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


def build_overlay_filter(
    overlay: OverlayConfig,
    rear: RearConfig = DEFAULT_REAR,
    *,
    rear_delay: float = 0.0,
    rear_trim_start: float = 0.0,
) -> str:
    rear_filter = build_rear_filter(overlay, rear)
    if rear_trim_start > 0:
        rear_filter = f"{rear_filter},trim=start={rear_trim_start:.3f},setpts=PTS-STARTPTS"
    if rear_delay > 0:
        # Shift the rear content later so rear frame 0 appears at t=rear_delay.
        # (Gating with overlay `enable` would only hide the inset, not move it,
        # leaving the rear running ahead by the offset.)
        rear_filter = f"{rear_filter},setpts=PTS+{rear_delay:.3f}/TB"
    # eof_action=pass keeps the output at the forward clip's length: the inset
    # simply disappears before the rear starts or after it ends, without
    # stretching the timeline.
    return (
        f"[1:v]{rear_filter}[rear];"
        f"[0:v][rear]overlay={overlay.x_expr}:{overlay.y_expr}:eof_action=pass,"
        f"setpts=PTS-STARTPTS[outv]"
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
    rear: RearConfig = DEFAULT_REAR,
    rear_delay: float = 0.0,
    rear_trim_start: float = 0.0,
    on_progress: Callable[[float | None], None] | None = None,
) -> None:
    filter_graph = build_overlay_filter(
        overlay,
        rear,
        rear_delay=rear_delay,
        rear_trim_start=rear_trim_start,
    )
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
            "-an",
            "-c:v",
            "libx264",
            "-crf",
            "23",
            "-preset",
            "medium",
            "-x264-params",
            "bframes=0",
            "-avoid_negative_ts",
            "make_zero",
            "-muxpreload",
            "0",
            "-muxdelay",
            "0",
            str(output_path),
        ],
        description=f"Compositing mirror overlay -> {output_path.name}",
        on_progress=on_progress,
    )


def extract_forward_audio(
    forward_path: Path,
    output_path: Path,
    *,
    on_progress: Callable[[float | None], None] | None = None,
) -> None:
    run_ffmpeg(
        [
            "-i",
            str(forward_path),
            "-map",
            "0:a:0",
            "-vn",
            "-c:a",
            "copy",
            str(output_path),
        ],
        description=f"Copying forward audio -> {output_path.name}",
        on_progress=on_progress,
    )


def mux_to_mp4(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    *,
    audio_advance_seconds: float = 0.0,
    on_progress: Callable[[float | None], None] | None = None,
) -> None:
    """Mux composited video with forward audio and encode AAC once."""
    args: list[str] = [
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
    ]
    if audio_advance_seconds > 0:
        args.extend(
            [
                "-filter_complex",
                f"[1:a]asetpts=PTS-{audio_advance_seconds:.6f}/TB[aout]",
                "-map",
                "0:v:0",
                "-map",
                "[aout]",
            ]
        )
    else:
        args.extend(["-map", "0:v:0", "-map", "1:a:0"])

    args.extend(
        [
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-avoid_negative_ts",
            "make_zero",
            "-muxpreload",
            "0",
            "-muxdelay",
            "0",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    run_ffmpeg(
        args,
        description=f"Exporting MP4 -> {output_path.name}",
        on_progress=on_progress,
    )


def process_job(
    job: JobConfig,
    *,
    overlay: OverlayConfig = DEFAULT_OVERLAY,
    rear: RearConfig = DEFAULT_REAR,
    progress: JobProgressTracker | None = None,
) -> Path:
    forward_clips = sort_clips(job.forward_clips)
    rear_clips = list(job.rear_clips)
    validate_pairing(forward_clips, rear_clips)

    work_dir = job.work_dir or job.output_path.parent / ".clipflow-work"
    work_dir.mkdir(parents=True, exist_ok=True)

    video_segments: list[Path] = []
    audio_segments: list[Path] = []
    cumulative_seconds = 0.0

    if progress:
        progress.begin_phase(PHASE_PAIRS)

    for index, (forward, rear_clip) in enumerate(zip(forward_clips, rear_clips)):
        rear_delay, rear_trim_start = compute_rear_sync(forward, rear_clip)
        video_segment = work_dir / f"segment_{index:04d}_video.mov"
        audio_segment = work_dir / f"segment_{index:04d}_audio.mov"

        if progress:
            segment_base = cumulative_seconds
            pair_callback = progress.callback(PHASE_PAIRS)

            def on_progress(seconds: float | None, base: float = segment_base) -> None:
                if seconds is not None:
                    pair_callback(base + seconds)
        else:
            on_progress = None

        composite_videos(
            forward,
            rear_clip,
            video_segment,
            overlay=overlay,
            rear=rear,
            rear_delay=rear_delay,
            rear_trim_start=rear_trim_start,
            on_progress=on_progress,
        )
        extract_forward_audio(forward, audio_segment)
        cumulative_seconds += probe_duration(forward)
        video_segments.append(video_segment)
        audio_segments.append(audio_segment)

    master_video = work_dir / "master_video.mov"
    master_audio = work_dir / "master_audio.mov"
    audio_advance_seconds = compute_audio_advance_seconds(forward_clips[0])

    if progress:
        progress.complete_phase(PHASE_PAIRS)
        progress.begin_phase(PHASE_CONCAT)
        concat_callback = progress.callback(PHASE_CONCAT)
        concat_clips(video_segments, master_video, on_progress=concat_callback)
        concat_clips(audio_segments, master_audio, on_progress=concat_callback)
        mux_to_mp4(
            master_video,
            master_audio,
            job.output_path,
            audio_advance_seconds=audio_advance_seconds,
            on_progress=concat_callback,
        )
        progress.complete_phase(PHASE_CONCAT)
    else:
        concat_clips(video_segments, master_video)
        concat_clips(audio_segments, master_audio)
        mux_to_mp4(
            master_video,
            master_audio,
            job.output_path,
            audio_advance_seconds=audio_advance_seconds,
        )

    return job.output_path
