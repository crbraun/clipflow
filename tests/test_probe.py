from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from clipflow.probe import compute_audio_advance_seconds, probe_duration, total_duration


def test_probe_duration_parses_ffprobe_output() -> None:
    with patch("clipflow.probe.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = "123.456789\n"
        run.return_value.stderr = ""
        assert probe_duration(Path("clip.mov")) == 123.456789


def test_total_duration_sums_clip_lengths() -> None:
    with patch("clipflow.probe.probe_duration", side_effect=[10.0, 20.5, 4.5]):
        assert total_duration([Path("a.mov"), Path("b.mov"), Path("c.mov")]) == 35.0


def test_compute_audio_advance_seconds() -> None:
    with (
        patch("clipflow.probe.probe_av_offset", return_value=0.966667),
        patch("clipflow.probe.probe_frame_rate", return_value=30.0),
    ):
        advance = compute_audio_advance_seconds(Path("forward.mov"))
    assert advance == 0.966667 + (23 / 30)
