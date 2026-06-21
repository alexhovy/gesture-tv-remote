from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HandState:
    landmarks: list[Any]
    gesture: str | None
    center: tuple[float, float]
    size: float
    upright: bool = True


@dataclass(frozen=True)
class GestureDecision:
    command_gesture: str | None
    activated: bool
    debug_message: str
    primary_temporarily_lost: bool = False
    zoom_landmarks: list[list[Any]] = field(default_factory=list)
