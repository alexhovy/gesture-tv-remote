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
    freeze_zoom: bool = False
    anchor_locked: bool = False
    zoom_landmarks: list[list[Any]] = field(default_factory=list)
    pointer_debug: "PointerDebug | None" = None


@dataclass(frozen=True)
class PointerDebug:
    anchor: tuple[float, float] | None
    current: tuple[float, float] | None
    active_gesture: str | None
    candidate_gesture: str | None
    phase: str
    armed: bool
    activation_distance: float
    neutral_distance: float
    threshold_ratio: float
    in_neutral: bool
    blocked_reason: str | None
