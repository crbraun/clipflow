from __future__ import annotations

import os
from pathlib import Path

from clipflow.matching import match_rear_by_mtime


def test_match_rear_by_mtime_pairs_closest_times(tmp_path: Path) -> None:
    forward_a = tmp_path / "F001.MOV"
    forward_b = tmp_path / "F002.MOV"
    rear_a = tmp_path / "R001.MOV"
    rear_b = tmp_path / "R002.MOV"
    for path in (forward_a, forward_b, rear_a, rear_b):
        path.write_bytes(b"test")

    base = 1_700_000_000
    os.utime(forward_a, (base + 10, base + 10))
    os.utime(forward_b, (base + 30, base + 30))
    os.utime(rear_a, (base + 11, base + 11))
    os.utime(rear_b, (base + 29, base + 29))

    matched = match_rear_by_mtime([forward_b, forward_a], [rear_a, rear_b])
    assert matched == [rear_a, rear_b]


def test_match_rear_by_mtime_requires_enough_rear_clips(tmp_path: Path) -> None:
    forward = tmp_path / "F001.MOV"
    rear = tmp_path / "R001.MOV"
    forward.write_bytes(b"test")
    rear.write_bytes(b"test")

    try:
        match_rear_by_mtime([forward, forward], [rear])
    except ValueError as exc:
        assert "Not enough rear clips" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
