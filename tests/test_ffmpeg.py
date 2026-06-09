from pathlib import Path

from clipflow.config import DEFAULT_REAR, OverlayConfig
from clipflow.ffmpeg import build_overlay_filter, build_rear_filter, sort_clips, validate_pairing


def test_natural_sort_orders_numeric_suffixes() -> None:
    names = ["SCHD09710.MOV", "SCHD0973.MOV", "SCHD0974.MOV"]
    sorted_paths = sort_clips([Path(name) for name in names])
    assert [path.name for path in sorted_paths] == [
        "SCHD0973.MOV",
        "SCHD0974.MOV",
        "SCHD09710.MOV",
    ]


def test_validate_pairing_requires_equal_counts() -> None:
    try:
        validate_pairing([Path("a.mov"), Path("b.mov")], [Path("c.mov")])
    except ValueError as exc:
        assert "must match" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_rear_filter_includes_crop_mirror_and_scale() -> None:
    rear = build_rear_filter(OverlayConfig(scale=0.10), DEFAULT_REAR)
    assert "crop=iw:ih*0.55:0:0" in rear
    assert "hflip" in rear
    assert "scale=iw*0.1:ih*0.1" in rear


def test_overlay_filter_graph() -> None:
    graph = build_overlay_filter(OverlayConfig(scale=0.10))
    assert graph.startswith("[1:v]")
    assert "overlay=(W-w)/2:0:eof_action=pass,setpts=PTS-STARTPTS[outv]" in graph
    assert "aout" not in graph
    assert "asetpts" not in graph


def test_overlay_filter_delays_rear_overlay() -> None:
    graph = build_overlay_filter(OverlayConfig(scale=0.10), rear_delay=5.0)
    assert "setpts=PTS+5.000/TB" in graph
    assert "enable" not in graph


def test_overlay_filter_trims_rear_when_it_starts_early() -> None:
    graph = build_overlay_filter(OverlayConfig(scale=0.10), rear_trim_start=2.5)
    assert "trim=start=2.500,setpts=PTS-STARTPTS" in graph
