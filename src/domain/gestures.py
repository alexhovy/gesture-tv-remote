from typing import Any

from src.domain.constants import (
    DIRECTION_DOWN,
    DIRECTION_LEFT,
    DIRECTION_RIGHT,
    DIRECTION_UP,
    GESTURE_FIST,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_POINT,
    GESTURE_TWO_FINGERS,
    GESTURE_VOLUME_DOWN,
    GESTURE_VOLUME_UP,
)
from src.domain.landmarks import (
    finger_is_extended,
    hand_center,
    landmark_distance,
    thumb_is_extended,
)


def detect_direction(
    start: tuple[float, float] | None,
    end: tuple[float, float],
    distance: float,
    dominance: float,
    prefix: str,
) -> str | None:
    if start is None:
        return None

    start_x, start_y = start
    end_x, end_y = end
    dx = end_x - start_x
    dy = end_y - start_y

    if abs(dx) < distance and abs(dy) < distance:
        return None

    if abs(dx) >= distance and abs(dx) >= dominance * abs(dy):
        return (
            f"{prefix}_{DIRECTION_RIGHT}"
            if dx > 0
            else f"{prefix}_{DIRECTION_LEFT}"
        )

    if abs(dy) >= distance and abs(dy) >= dominance * abs(dx):
        return f"{prefix}_{DIRECTION_DOWN}" if dy > 0 else f"{prefix}_{DIRECTION_UP}"

    return None


def detect_volume(start_y: float | None, current_y: float, distance: float) -> str | None:
    if start_y is None:
        return None

    dy = current_y - start_y

    if dy <= -distance:
        return GESTURE_VOLUME_UP

    if dy >= distance:
        return GESTURE_VOLUME_DOWN

    return None


def detect_gesture(
    landmarks: list[Any],
    handedness: str,
    pinch_distance_ratio: float,
) -> str | None:
    _, _, size = hand_center(landmarks)
    index_up = finger_is_extended(landmarks, 8, 6)
    middle_up = finger_is_extended(landmarks, 12, 10)
    ring_up = finger_is_extended(landmarks, 16, 14)
    pinky_up = finger_is_extended(landmarks, 20, 18)
    thumb_extended = thumb_is_extended(landmarks, handedness)
    pinch_distance = landmark_distance(landmarks, 4, 8)

    fingers_up = [index_up, middle_up, ring_up, pinky_up]

    if all(fingers_up):
        return GESTURE_OPEN_PALM

    if size > 0 and pinch_distance <= pinch_distance_ratio * size:
        return GESTURE_PINCH

    if index_up and middle_up and not ring_up and not pinky_up and not thumb_extended:
        return GESTURE_TWO_FINGERS

    if index_up and not middle_up and not ring_up and not pinky_up:
        return GESTURE_POINT

    if not any(fingers_up) and not thumb_extended:
        return GESTURE_FIST

    return None
