import math
from typing import Any

from src.domain.constants import HANDEDNESS_LEFT


HAND_CONNECTIONS = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (0, 17),
]


def finger_is_extended(landmarks: list[Any], tip_id: int, pip_id: int) -> bool:
    return landmarks[tip_id].y < landmarks[pip_id].y


def thumb_is_extended(landmarks: list[Any], handedness: str) -> bool:
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]

    if handedness == HANDEDNESS_LEFT:
        return thumb_tip.x > thumb_ip.x
    return thumb_tip.x < thumb_ip.x


def hand_center(landmarks: list[Any]) -> tuple[float, float, float]:
    x = sum(landmark.x for landmark in landmarks) / len(landmarks)
    y = sum(landmark.y for landmark in landmarks) / len(landmarks)
    size = max(
        max(landmark.x for landmark in landmarks) - min(landmark.x for landmark in landmarks),
        max(landmark.y for landmark in landmarks) - min(landmark.y for landmark in landmarks),
    )
    return x, y, size


def landmark_distance(landmarks: list[Any], first_id: int, second_id: int) -> float:
    first = landmarks[first_id]
    second = landmarks[second_id]
    return math.hypot(first.x - second.x, first.y - second.y)


def landmark_position(landmarks: list[Any], landmark_id: int) -> tuple[float, float]:
    landmark = landmarks[landmark_id]
    return landmark.x, landmark.y
