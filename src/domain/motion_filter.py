import math
from dataclasses import dataclass

from src.domain.constants import (
    GESTURE_POINT_DOWN,
    GESTURE_POINT_LEFT,
    GESTURE_POINT_RIGHT,
    GESTURE_POINT_UP,
)


@dataclass(frozen=True)
class MotionFilterState:
    active_gesture: str | None
    peak_distance: float
    returning_to_neutral: bool


@dataclass(frozen=True)
class MotionFilterResult:
    command_gesture: str | None
    active_gesture: str | None
    peak_distance: float
    returning_to_neutral: bool
    blocked_reason: str | None = None


def filter_motion_gesture(
    gesture: str,
    magnitude: float,
    activation_distance: float,
    state: MotionFilterState,
) -> MotionFilterResult:
    if state.returning_to_neutral:
        return MotionFilterResult(
            command_gesture=None,
            active_gesture=state.active_gesture,
            peak_distance=state.peak_distance,
            returning_to_neutral=True,
            blocked_reason="returning_to_neutral",
        )

    if state.active_gesture is not None and gesture != state.active_gesture:
        return MotionFilterResult(
            command_gesture=None,
            active_gesture=state.active_gesture,
            peak_distance=state.peak_distance,
            returning_to_neutral=True,
            blocked_reason="direction_changed_before_neutral",
        )

    if gesture != state.active_gesture:
        return MotionFilterResult(
            command_gesture=gesture,
            active_gesture=gesture,
            peak_distance=magnitude,
            returning_to_neutral=False,
        )

    if magnitude >= state.peak_distance:
        return MotionFilterResult(
            command_gesture=None,
            active_gesture=state.active_gesture,
            peak_distance=magnitude,
            returning_to_neutral=False,
        )

    release_delta = activation_distance * 0.75
    if magnitude <= state.peak_distance - release_delta:
        return MotionFilterResult(
            command_gesture=None,
            active_gesture=state.active_gesture,
            peak_distance=state.peak_distance,
            returning_to_neutral=True,
            blocked_reason="returning_to_neutral",
        )

    return MotionFilterResult(
        command_gesture=None,
        active_gesture=state.active_gesture,
        peak_distance=state.peak_distance,
        returning_to_neutral=False,
    )


def is_motion_neutral(magnitude: float, activation_distance: float) -> bool:
    return magnitude <= activation_distance


def pointer_motion_magnitude(
    gesture: str,
    start_position: tuple[float, float],
    current_position: tuple[float, float],
) -> float:
    start_x, start_y = start_position
    current_x, current_y = current_position
    if gesture in {GESTURE_POINT_LEFT, GESTURE_POINT_RIGHT}:
        return abs(current_x - start_x)
    if gesture in {GESTURE_POINT_UP, GESTURE_POINT_DOWN}:
        return abs(current_y - start_y)
    return math.dist(start_position, current_position)
