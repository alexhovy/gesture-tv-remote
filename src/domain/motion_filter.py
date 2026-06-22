import math
from dataclasses import dataclass

from src.domain.constants import (
    GESTURE_POINT_DOWN,
    GESTURE_POINT_LEFT,
    GESTURE_POINT_RIGHT,
    GESTURE_POINT_UP,
    GESTURE_VOLUME_DOWN,
    GESTURE_VOLUME_UP,
)

MOTION_EPSILON = 1e-9
MOTION_ACTIVATION_HYSTERESIS = 1.15


@dataclass(frozen=True)
class JoystickDecision:
    gesture: str | None
    magnitude: float
    activation_distance: float
    neutral_distance: float
    threshold_ratio: float
    in_neutral: bool
    blocked_reason: str | None = None


def classify_pointer_joystick(
    anchor_position: tuple[float, float] | None,
    current_position: tuple[float, float],
    distance: float,
    dominance: float,
    prefix: str,
) -> JoystickDecision:
    neutral = max(0.0, distance)
    activation = neutral * MOTION_ACTIVATION_HYSTERESIS
    if anchor_position is None:
        return JoystickDecision(
            None, 0.0, activation, neutral, 0.0, True, "missing_anchor"
        )

    anchor_x, anchor_y = anchor_position
    current_x, current_y = current_position
    dx = current_x - anchor_x
    dy = current_y - anchor_y
    abs_dx = abs(dx)
    abs_dy = abs(dy)
    magnitude = math.hypot(dx, dy)
    threshold_ratio = _threshold_ratio(magnitude, activation)

    if magnitude <= neutral + MOTION_EPSILON:
        return JoystickDecision(
            None,
            magnitude,
            activation,
            neutral,
            threshold_ratio,
            True,
            "neutral",
        )

    if magnitude <= activation + MOTION_EPSILON:
        return JoystickDecision(
            None,
            magnitude,
            activation,
            neutral,
            threshold_ratio,
            False,
            "inside_activation",
        )

    axis_dominance = max(0.0, dominance)
    if abs_dx >= abs_dy and abs_dx >= axis_dominance * abs_dy:
        direction = GESTURE_POINT_RIGHT if dx > 0 else GESTURE_POINT_LEFT
        magnitude = abs_dx
        return JoystickDecision(
            f"{prefix}_{direction.removeprefix('POINT_')}",
            magnitude,
            activation,
            neutral,
            _threshold_ratio(magnitude, activation),
            False,
        )

    if abs_dy >= abs_dx and abs_dy >= axis_dominance * abs_dx:
        direction = GESTURE_POINT_DOWN if dy > 0 else GESTURE_POINT_UP
        magnitude = abs_dy
        return JoystickDecision(
            f"{prefix}_{direction.removeprefix('POINT_')}",
            magnitude,
            activation,
            neutral,
            _threshold_ratio(magnitude, activation),
            False,
        )

    return JoystickDecision(
        None,
        magnitude,
        activation,
        neutral,
        threshold_ratio,
        False,
        "axis_ambiguous",
    )


def classify_volume_joystick(
    anchor_y: float | None,
    current_y: float,
    distance: float,
) -> JoystickDecision:
    neutral = max(0.0, distance)
    activation = neutral * MOTION_ACTIVATION_HYSTERESIS
    if anchor_y is None:
        return JoystickDecision(
            None, 0.0, activation, neutral, 0.0, True, "missing_anchor"
        )

    dy = current_y - anchor_y
    magnitude = abs(dy)
    threshold_ratio = _threshold_ratio(magnitude, activation)

    if magnitude <= neutral + MOTION_EPSILON:
        return JoystickDecision(
            None,
            magnitude,
            activation,
            neutral,
            threshold_ratio,
            True,
            "neutral",
        )

    if magnitude <= activation + MOTION_EPSILON:
        return JoystickDecision(
            None,
            magnitude,
            activation,
            neutral,
            threshold_ratio,
            False,
            "inside_activation",
        )

    gesture = GESTURE_VOLUME_DOWN if dy > 0 else GESTURE_VOLUME_UP
    return JoystickDecision(
        gesture,
        magnitude,
        activation,
        neutral,
        threshold_ratio,
        False,
    )


def _threshold_ratio(magnitude: float, threshold: float) -> float:
    if threshold <= 0:
        return 0.0

    return magnitude / threshold
