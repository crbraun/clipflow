from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OverlayConfig:
    scale: float = 0.10
    x_expr: str = "(W-w)/2"
    y_expr: str = "0"


@dataclass(frozen=True)
class RearConfig:
    mirror: bool = True


DEFAULT_OVERLAY = OverlayConfig()
DEFAULT_REAR = RearConfig()
