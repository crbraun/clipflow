from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clipflow.config import DEFAULT_OVERLAY


@dataclass(frozen=True)
class ClipPair:
    index: int
    forward: Path
    rear: Path


@dataclass(frozen=True)
class JobConfig:
    forward_clips: list[Path]
    rear_clips: list[Path]
    output_path: Path
    overlay_scale: float = DEFAULT_OVERLAY.scale
    work_dir: Path | None = None

    @property
    def pairs(self) -> list[ClipPair]:
        return [
            ClipPair(index=i + 1, forward=f, rear=r)
            for i, (f, r) in enumerate(zip(self.forward_clips, self.rear_clips))
        ]
