import math
from typing import Any

from src.domain.constants import HANDEDNESS_LEFT

LANDMARK_WRIST = 0
LANDMARK_THUMB_CMC = 1
LANDMARK_THUMB_MCP = 2
LANDMARK_THUMB_IP = 3
LANDMARK_THUMB_TIP = 4
LANDMARK_INDEX_MCP = 5
LANDMARK_INDEX_PIP = 6
LANDMARK_INDEX_DIP = 7
LANDMARK_INDEX_TIP = 8
LANDMARK_MIDDLE_MCP = 9
LANDMARK_MIDDLE_PIP = 10
LANDMARK_MIDDLE_DIP = 11
LANDMARK_MIDDLE_TIP = 12
LANDMARK_RING_MCP = 13
LANDMARK_RING_PIP = 14
LANDMARK_RING_DIP = 15
LANDMARK_RING_TIP = 16
LANDMARK_PINKY_MCP = 17
LANDMARK_PINKY_PIP = 18
LANDMARK_PINKY_DIP = 19
LANDMARK_PINKY_TIP = 20
LANDMARK_COUNT = 21

HAND_CONNECTIONS = [
    (LANDMARK_WRIST, LANDMARK_THUMB_CMC),
    (LANDMARK_THUMB_CMC, LANDMARK_THUMB_MCP),
    (LANDMARK_THUMB_MCP, LANDMARK_THUMB_IP),
    (LANDMARK_THUMB_IP, LANDMARK_THUMB_TIP),
    (LANDMARK_WRIST, LANDMARK_INDEX_MCP),
    (LANDMARK_INDEX_MCP, LANDMARK_INDEX_PIP),
    (LANDMARK_INDEX_PIP, LANDMARK_INDEX_DIP),
    (LANDMARK_INDEX_DIP, LANDMARK_INDEX_TIP),
    (LANDMARK_INDEX_MCP, LANDMARK_MIDDLE_MCP),
    (LANDMARK_MIDDLE_MCP, LANDMARK_MIDDLE_PIP),
    (LANDMARK_MIDDLE_PIP, LANDMARK_MIDDLE_DIP),
    (LANDMARK_MIDDLE_DIP, LANDMARK_MIDDLE_TIP),
    (LANDMARK_MIDDLE_MCP, LANDMARK_RING_MCP),
    (LANDMARK_RING_MCP, LANDMARK_RING_PIP),
    (LANDMARK_RING_PIP, LANDMARK_RING_DIP),
    (LANDMARK_RING_DIP, LANDMARK_RING_TIP),
    (LANDMARK_RING_MCP, LANDMARK_PINKY_MCP),
    (LANDMARK_PINKY_MCP, LANDMARK_PINKY_PIP),
    (LANDMARK_PINKY_PIP, LANDMARK_PINKY_DIP),
    (LANDMARK_PINKY_DIP, LANDMARK_PINKY_TIP),
    (LANDMARK_WRIST, LANDMARK_PINKY_MCP),
]


def finger_is_extended(landmarks: list[Any], tip_id: int, pip_id: int) -> bool:
    return landmarks[tip_id].y < landmarks[pip_id].y


def thumb_is_extended(landmarks: list[Any], handedness: str) -> bool:
    thumb_tip = landmarks[LANDMARK_THUMB_TIP]
    thumb_ip = landmarks[LANDMARK_THUMB_IP]

    if handedness == HANDEDNESS_LEFT:
        return thumb_tip.x > thumb_ip.x
    return thumb_tip.x < thumb_ip.x


def hand_upright_metrics(landmarks: list[Any]) -> tuple[float, float, float]:
    wrist = landmarks[LANDMARK_WRIST]
    middle_mcp = landmarks[LANDMARK_MIDDLE_MCP]
    dx = middle_mcp.x - wrist.x
    dy = middle_mcp.y - wrist.y

    if dy == 0:
        return dx, dy, math.inf

    return dx, dy, abs(dx) / abs(dy)


def hand_is_upright(landmarks: list[Any], max_tilt_ratio: float) -> bool:
    dx, dy, tilt_ratio = hand_upright_metrics(landmarks)

    if dy >= 0:
        return False

    return tilt_ratio <= max(0.0, max_tilt_ratio)


def hand_upright_reason(landmarks: list[Any], max_tilt_ratio: float) -> str:
    _, dy, tilt_ratio = hand_upright_metrics(landmarks)

    if dy >= 0:
        return "upside_down"

    if tilt_ratio > max(0.0, max_tilt_ratio):
        return "tilted"

    return "ok"


def hand_center(landmarks: list[Any]) -> tuple[float, float, float]:
    x = sum(landmark.x for landmark in landmarks) / len(landmarks)
    y = sum(landmark.y for landmark in landmarks) / len(landmarks)
    size = max(
        max(landmark.x for landmark in landmarks)
        - min(landmark.x for landmark in landmarks),
        max(landmark.y for landmark in landmarks)
        - min(landmark.y for landmark in landmarks),
    )
    return x, y, size


def landmark_distance(landmarks: list[Any], first_id: int, second_id: int) -> float:
    first = landmarks[first_id]
    second = landmarks[second_id]
    return math.hypot(first.x - second.x, first.y - second.y)


def landmark_position(landmarks: list[Any], landmark_id: int) -> tuple[float, float]:
    landmark = landmarks[landmark_id]
    return landmark.x, landmark.y
