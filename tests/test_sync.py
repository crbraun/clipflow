from pathlib import Path
from unittest.mock import patch

from clipflow.sync import (
    clip_start_timestamp,
    compute_rear_sync,
    file_recording_start_time,
    timestamp_sync_offset,
)


def test_timestamp_sync_offset_when_rear_starts_later(tmp_path: Path) -> None:
    forward = tmp_path / "forward.mov"
    rear = tmp_path / "rear.mov"
    forward.write_bytes(b"test")
    rear.write_bytes(b"test")

    with patch(
        "clipflow.sync.clip_start_timestamp",
        side_effect=[105.0, 100.0],
    ):
        sync_offset, trim = timestamp_sync_offset(forward, rear)

    assert sync_offset == 5.0
    assert trim == 0.0


def test_compute_rear_sync_matches_timestamp_sync_offset(tmp_path: Path) -> None:
    forward = tmp_path / "forward.mov"
    rear = tmp_path / "rear.mov"
    forward.write_bytes(b"test")
    rear.write_bytes(b"test")

    with patch(
        "clipflow.sync.clip_start_timestamp",
        side_effect=[105.0, 100.0],
    ):
        assert compute_rear_sync(forward, rear) == (5.0, 0.0)


def test_timestamp_sync_offset_trims_when_rear_starts_earlier(tmp_path: Path) -> None:
    forward = tmp_path / "forward.mov"
    rear = tmp_path / "rear.mov"
    forward.write_bytes(b"test")
    rear.write_bytes(b"test")

    with patch(
        "clipflow.sync.clip_start_timestamp",
        side_effect=[100.0, 103.0],
    ):
        sync_offset, trim = timestamp_sync_offset(forward, rear)

    assert sync_offset == 0.0
    assert trim == 3.0


def test_clip_start_timestamp_prefers_embedded_metadata(tmp_path: Path) -> None:
    clip = tmp_path / "clip.mov"
    clip.write_bytes(b"test")
    with patch("clipflow.sync.probe_video_creation_time", return_value=1234.5):
        assert clip_start_timestamp(clip) == 1234.5


def test_file_recording_start_time_uses_end_minus_duration(tmp_path: Path) -> None:
    clip = tmp_path / "clip.mov"
    clip.write_bytes(b"test")
    with patch("clipflow.sync.file_recording_end_time", return_value=2000.0):
        with patch("clipflow.sync.probe_duration", return_value=100.0):
            assert file_recording_start_time(clip) == 1900.0


def test_clip_start_timestamp_falls_back_to_recording_start(tmp_path: Path) -> None:
    clip = tmp_path / "clip.mov"
    clip.write_bytes(b"test")
    with patch("clipflow.sync.probe_video_creation_time", return_value=None):
        with patch("clipflow.sync.file_recording_start_time", return_value=1900.0):
            assert clip_start_timestamp(clip) == 1900.0
