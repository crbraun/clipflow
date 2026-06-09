"""Recover the true forward/rear recording offset by correlating their audio.

Both cameras sit in the same car and record the same engine and track noise, so
cross-correlating their soundtracks reveals how much later the rear clip started
relative to the forward clip. Unlike embedded timestamps, this is immune to the
two cameras' clocks disagreeing with each other.
"""

from __future__ import annotations

import subprocess
import tempfile
import wave
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

ANALYSIS_SAMPLE_RATE = 8000
ENVELOPE_HOP = 160  # 20 ms windows -> 50 Hz envelope
ENVELOPE_RATE = ANALYSIS_SAMPLE_RATE / ENVELOPE_HOP
DEFAULT_MAX_SECONDS = 900.0
DEFAULT_SEARCH_WINDOW = 120.0
WIDE_SEARCH_WINDOW = 300.0
MIN_OVERLAP_SECONDS = 60.0
MIN_CONFIDENCE = 0.30


@dataclass(frozen=True)
class AudioOffset:
    """Best-fit offset in seconds (positive = rear started later) and its score."""

    seconds: float
    confidence: float


def _extract_envelope(path: Path, max_seconds: float) -> np.ndarray | None:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        wav_path = Path(handle.name)
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-v",
                "error",
                "-y",
                "-t",
                f"{max_seconds:.3f}",
                "-i",
                str(path),
                "-map",
                "0:a:0",
                "-ac",
                "1",
                "-ar",
                str(ANALYSIS_SAMPLE_RATE),
                str(wav_path),
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        with wave.open(str(wav_path)) as wav:
            frames = wav.readframes(wav.getnframes())
    finally:
        wav_path.unlink(missing_ok=True)

    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if samples.size < ENVELOPE_HOP * 10:
        return None

    usable = (samples.size // ENVELOPE_HOP) * ENVELOPE_HOP
    rms = np.sqrt(np.mean(samples[:usable].reshape(-1, ENVELOPE_HOP) ** 2, axis=1) + 1e-9)
    envelope = np.log1p(rms)

    # Subtract a ~1s moving average so steady levels drop out and events (engine
    # load changes, shifts, track noise) dominate the correlation.
    smoothing = max(1, int(ENVELOPE_RATE))
    kernel = np.ones(smoothing) / smoothing
    envelope = envelope - np.convolve(envelope, kernel, mode="same")

    std = float(envelope.std())
    if std < 1e-6:
        return None
    return (envelope - envelope.mean()) / std


@lru_cache(maxsize=8)
def _cached_envelope(path_str: str, size: int, mtime: int, max_seconds: float) -> np.ndarray | None:
    return _extract_envelope(Path(path_str), max_seconds)


def extract_envelope(path: Path, max_seconds: float = DEFAULT_MAX_SECONDS) -> np.ndarray | None:
    stat = path.stat()
    return _cached_envelope(str(path), stat.st_size, int(stat.st_mtime), max_seconds)


def _correlate(
    forward_env: np.ndarray,
    rear_env: np.ndarray,
    prior_seconds: float,
    search_window: float,
) -> AudioOffset | None:
    center = int(round(prior_seconds * ENVELOPE_RATE))
    half = int(round(search_window * ENVELOPE_RATE))
    n_f = forward_env.size
    n_r = rear_env.size

    min_overlap = min(
        int(MIN_OVERLAP_SECONDS * ENVELOPE_RATE),
        int(0.5 * min(n_f, n_r)),
    )
    min_overlap = max(min_overlap, 1)

    best_lag: int | None = None
    best_corr = -2.0
    for lag in range(center - half, center + half + 1):
        if lag >= 0:
            a = forward_env[lag:]
            b = rear_env[: n_f - lag]
        else:
            a = forward_env[: n_f + lag]
            b = rear_env[-lag:]
        overlap = min(a.size, b.size)
        if overlap < min_overlap:
            continue
        corr = float(np.dot(a[:overlap], b[:overlap]) / overlap)
        if corr > best_corr:
            best_corr = corr
            best_lag = lag

    if best_lag is None:
        return None
    return AudioOffset(seconds=best_lag / ENVELOPE_RATE, confidence=best_corr)


def estimate_audio_offset(
    forward: Path,
    rear: Path,
    *,
    prior_seconds: float = 0.0,
    search_window: float = DEFAULT_SEARCH_WINDOW,
    max_seconds: float = DEFAULT_MAX_SECONDS,
) -> AudioOffset | None:
    """Return the rear-vs-forward offset from audio, or None if it can't be measured.

    Searches a window around ``prior_seconds`` (typically the metadata-derived
    guess). If that window yields a weak match, retries with a wider, prior-free
    search in case the timestamp prior was badly skewed.
    """
    forward_env = extract_envelope(forward, max_seconds)
    rear_env = extract_envelope(rear, max_seconds)
    if forward_env is None or rear_env is None:
        return None

    result = _correlate(forward_env, rear_env, prior_seconds, search_window)
    if result is not None and result.confidence >= MIN_CONFIDENCE:
        return result

    wider = _correlate(forward_env, rear_env, 0.0, WIDE_SEARCH_WINDOW)
    if wider is None:
        return result
    if result is None or wider.confidence > result.confidence:
        return wider
    return result
