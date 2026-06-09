from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_SOURCE_DIR = Path.home() / "Desktop"


@dataclass(frozen=True)
class OverlayConfig:
    scale: float = 0.45
    x_expr: str = "(W-w)/2"
    y_expr: str = "0"


@dataclass(frozen=True)
class RearConfig:
    mirror: bool = True
    bottom_trim_fraction: float = 0.45


DEFAULT_OVERLAY = OverlayConfig()
DEFAULT_REAR = RearConfig()
