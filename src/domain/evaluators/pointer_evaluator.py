from dataclasses import dataclass

from src.domain.constants import GESTURE_POINT
from src.domain.motion_filter import classify_pointer_joystick
from src.domain.motion_gesture import MotionJoystickState
from src.shared.config import AppConfig


@dataclass(frozen=True)
class PointerEvaluation:
    command_gesture: str | None
    position: tuple[float, float] | None
    distance: float


def evaluate_pointer_motion(
    pointer: MotionJoystickState,
    pointer_position: tuple[float, float],
    pointer_reference_size: float,
    config: AppConfig,
    now: float,
) -> PointerEvaluation:
    if not isinstance(pointer.anchor, tuple):
        pointer.anchor = pointer_position

    distance = pointer_distance(
        pointer_reference_size,
        config.gesture.pointer_screen_radius_ratio,
    )
    decision = classify_pointer_joystick(
        pointer.anchor if isinstance(pointer.anchor, tuple) else None,
        pointer_position,
        distance,
        config.gesture.pointer_dominance,
        GESTURE_POINT,
    )
    pointer.record_decision(decision)
    return PointerEvaluation(
        command_gesture=pointer.command(
            decision,
            pointer_position,
            now,
            config.gesture.debounce_seconds,
        ),
        position=pointer_position,
        distance=distance,
    )


def pointer_distance(reference_size: float, radius_ratio: float) -> float:
    return max(0.0, reference_size) * radius_ratio
