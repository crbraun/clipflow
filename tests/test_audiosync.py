from pathlib import Path
from unittest.mock import patch

import numpy as np

from clipflow.audiosync import ENVELOPE_RATE, AudioOffset, _correlate, estimate_audio_offset


def _make_pair(lag: int, n: int = 4000, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Build two normalized envelopes whose best alignment is `lag` samples.

    Positive `lag` means the rear envelope's events appear `lag` samples later in
    the forward timeline (rear started later).
    """
    rng = np.random.default_rng(seed)
    base = rng.standard_normal(n + abs(lag))
    base = (base - base.mean()) / base.std()
    if lag >= 0:
        forward = base[:n]
        rear = base[lag : lag + n]
    else:
        shift = -lag
        forward = base[shift : shift + n]
        rear = base[:n]
    return forward.copy(), rear.copy()


def test_correlate_recovers_positive_lag() -> None:
    lag = 37
    forward, rear = _make_pair(lag)
    result = _correlate(forward, rear, prior_seconds=0.0, search_window=2.0)
    assert result is not None
    assert abs(result.seconds - lag / ENVELOPE_RATE) < 1e-6
    assert result.confidence > 0.8


def test_correlate_recovers_negative_lag() -> None:
    lag = -25
    forward, rear = _make_pair(lag)
    result = _correlate(forward, rear, prior_seconds=0.0, search_window=2.0)
    assert result is not None
    assert abs(result.seconds - lag / ENVELOPE_RATE) < 1e-6
    assert result.confidence > 0.8


def test_estimate_audio_offset_returns_none_when_extraction_fails() -> None:
    with patch("clipflow.audiosync.extract_envelope", return_value=None):
        assert estimate_audio_offset(Path("f.mov"), Path("r.mov")) is None


def test_estimate_audio_offset_uses_prior_window() -> None:
    lag = 90
    forward, rear = _make_pair(lag, n=8000)
    with patch("clipflow.audiosync.extract_envelope", side_effect=[forward, rear]):
        result = estimate_audio_offset(
            Path("f.mov"),
            Path("r.mov"),
            prior_seconds=lag / ENVELOPE_RATE,
            search_window=2.0,
        )
    assert isinstance(result, AudioOffset)
    assert abs(result.seconds - lag / ENVELOPE_RATE) < 1e-6
    assert result.confidence > 0.8
