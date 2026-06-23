from typing import Any

from src.domain.constants import (
    GESTURE_FIST,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_POINT,
    GESTURE_TWO_FINGERS,
)
from src.domain.geometry.landmarks import (
    LANDMARK_INDEX_PIP,
    LANDMARK_INDEX_TIP,
    LANDMARK_MIDDLE_PIP,
    LANDMARK_MIDDLE_TIP,
    LANDMARK_PINKY_PIP,
    LANDMARK_PINKY_TIP,
    LANDMARK_RING_PIP,
    LANDMARK_RING_TIP,
    LANDMARK_THUMB_TIP,
    finger_is_extended,
    hand_center,
    hand_is_upright,
    landmark_distance,
)


def classify_static_hand_pose(
    landmarks: list[Any],
    handedness: str,
    pinch_distance_ratio: float,
    require_upright_hand: bool = True,
    upright_max_tilt_ratio: float = 0.75,
) -> str | None:
    if require_upright_hand and not hand_is_upright(landmarks, upright_max_tilt_ratio):
        return None

    _, _, size = hand_center(landmarks)
    index_up = finger_is_extended(landmarks, LANDMARK_INDEX_TIP, LANDMARK_INDEX_PIP)
    middle_up = finger_is_extended(landmarks, LANDMARK_MIDDLE_TIP, LANDMARK_MIDDLE_PIP)
    ring_up = finger_is_extended(landmarks, LANDMARK_RING_TIP, LANDMARK_RING_PIP)
    pinky_up = finger_is_extended(landmarks, LANDMARK_PINKY_TIP, LANDMARK_PINKY_PIP)
    pinch_distance = landmark_distance(
        landmarks, LANDMARK_THUMB_TIP, LANDMARK_INDEX_TIP
    )

    fingers_up = [index_up, middle_up, ring_up, pinky_up]

    if all(fingers_up):
        return GESTURE_OPEN_PALM

    if not any(fingers_up):
        return GESTURE_FIST

    if size > 0 and pinch_distance <= pinch_distance_ratio * size:
        return GESTURE_PINCH

    if index_up and middle_up and not ring_up and not pinky_up:
        return GESTURE_TWO_FINGERS

    if index_up and not middle_up and not ring_up and not pinky_up:
        return GESTURE_POINT

    return None
