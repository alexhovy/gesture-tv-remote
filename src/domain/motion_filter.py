from dataclasses import dataclass

from src.domain.constants import (
    GESTURE_POINT_DOWN,
    GESTURE_POINT_LEFT,
    GESTURE_POINT_RIGHT,
    GESTURE_POINT_UP,
    GESTURE_VOLUME_DOWN,
    GESTURE_VOLUME_UP,
)

MOTION_ACTIVATION_RATIO = 0.65
MOTION_NEUTRAL_RATIO = 0.45
MOTION_RELEASE_RATIO = 0.90
MOTION_EPSILON = 1e-9


@dataclass(frozen=True)
class JoystickDecision:
    gesture: str | None
    magnitude: float
    activation_distance: float
    neutral_distance: float
    release_distance: float
    threshold_ratio: float
    in_neutral: bool
    in_release: bool
    blocked_reason: str | None = None


def activation_distance(distance: float) -> float:
    return distance * MOTION_ACTIVATION_RATIO


def neutral_distance(activation_distance: float) -> float:
    return activation_distance * MOTION_NEUTRAL_RATIO


def release_distance(activation_distance: float) -> float:
    return activation_distance * MOTION_RELEASE_RATIO


def classify_pointer_joystick(
    anchor_position: tuple[float, float] | None,
    current_position: tuple[float, float],
    distance: float,
    dominance: float,
    prefix: str,
) -> JoystickDecision:
    activation = activation_distance(distance)
    neutral = neutral_distance(activation)
    release = release_distance(activation)
    if anchor_position is None:
        return JoystickDecision(
            None, 0.0, activation, neutral, release, 0.0, True, True, "missing_anchor"
        )

    anchor_x, anchor_y = anchor_position
    current_x, current_y = current_position
    dx = current_x - anchor_x
    dy = current_y - anchor_y
    abs_dx = abs(dx)
    abs_dy = abs(dy)
    magnitude = max(abs_dx, abs_dy)
    threshold_ratio = _threshold_ratio(magnitude, activation)

    if magnitude <= neutral + MOTION_EPSILON:
        return JoystickDecision(
            None,
            magnitude,
            activation,
            neutral,
            release,
            threshold_ratio,
            True,
            True,
            "neutral",
        )

    in_release = magnitude <= release + MOTION_EPSILON

    if abs_dx + MOTION_EPSILON < activation and abs_dy + MOTION_EPSILON < activation:
        return JoystickDecision(
            None,
            magnitude,
            activation,
            neutral,
            release,
            threshold_ratio,
            False,
            in_release,
            "below_threshold",
        )

    if abs_dx + MOTION_EPSILON >= activation and abs_dx >= dominance * abs_dy:
        direction = GESTURE_POINT_RIGHT if dx > 0 else GESTURE_POINT_LEFT
        magnitude = abs_dx
        return JoystickDecision(
            f"{prefix}_{direction.removeprefix('POINT_')}",
            magnitude,
            activation,
            neutral,
            release,
            _threshold_ratio(magnitude, activation),
            False,
            False,
        )

    if abs_dy + MOTION_EPSILON >= activation and abs_dy >= dominance * abs_dx:
        direction = GESTURE_POINT_DOWN if dy > 0 else GESTURE_POINT_UP
        magnitude = abs_dy
        return JoystickDecision(
            f"{prefix}_{direction.removeprefix('POINT_')}",
            magnitude,
            activation,
            neutral,
            release,
            _threshold_ratio(magnitude, activation),
            False,
            False,
        )

    return JoystickDecision(
        None,
        magnitude,
        activation,
        neutral,
        release,
        threshold_ratio,
        False,
        in_release,
        "axis_ambiguous",
    )


def classify_volume_joystick(
    anchor_y: float | None,
    current_y: float,
    distance: float,
) -> JoystickDecision:
    activation = activation_distance(distance)
    neutral = neutral_distance(activation)
    release = release_distance(activation)
    if anchor_y is None:
        return JoystickDecision(
            None, 0.0, activation, neutral, release, 0.0, True, True, "missing_anchor"
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
            release,
            threshold_ratio,
            True,
            True,
            "neutral",
        )

    in_release = magnitude <= release + MOTION_EPSILON

    if magnitude + MOTION_EPSILON < activation:
        return JoystickDecision(
            None,
            magnitude,
            activation,
            neutral,
            release,
            threshold_ratio,
            False,
            in_release,
            "below_threshold",
        )

    gesture = GESTURE_VOLUME_DOWN if dy > 0 else GESTURE_VOLUME_UP
    return JoystickDecision(
        gesture,
        magnitude,
        activation,
        neutral,
        release,
        threshold_ratio,
        False,
        False,
    )


def _threshold_ratio(magnitude: float, threshold: float) -> float:
    if threshold <= 0:
        return 0.0

    return magnitude / threshold
