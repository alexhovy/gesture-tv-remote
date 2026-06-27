import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.domain.geometry.landmarks import hand_center, hand_is_upright
from src.domain.gestures.gesture_classification import classify_static_hand_pose
from src.domain.session.session_types import HandState
from src.shared.config import GestureConfig

DUPLICATE_HAND_MAX_CENTER_DISTANCE_RATIO = 0.35
DUPLICATE_HAND_MIN_BOX_IOU = 0.55


@dataclass(frozen=True)
class RawDetectedHandState:
    landmarks: list[Any]
    handedness: str


@dataclass(frozen=True)
class NormalizedLandmarkData:
    landmarks: list[Any]
    center: tuple[float, float]
    size: float
    upright: bool


def normalize_hand_landmarks(
    raw_hand: RawDetectedHandState,
    config: GestureConfig,
) -> NormalizedLandmarkData:
    center_x, center_y, hand_size = hand_center(raw_hand.landmarks)
    upright = not config.require_upright_hands or hand_is_upright(
        raw_hand.landmarks, config.hand_upright_max_tilt_ratio
    )
    return NormalizedLandmarkData(
        landmarks=raw_hand.landmarks,
        center=(center_x, center_y),
        size=hand_size,
        upright=upright,
    )


def raw_hand_to_state(
    raw_hand: RawDetectedHandState, config: GestureConfig
) -> HandState:
    normalized = normalize_hand_landmarks(raw_hand, config)
    return HandState(
        landmarks=normalized.landmarks,
        gesture=classify_static_hand_pose(
            normalized.landmarks,
            raw_hand.handedness,
            config.pinch_distance_ratio,
            config.require_upright_hands,
            config.hand_upright_max_tilt_ratio,
        ),
        center=normalized.center,
        size=normalized.size,
        upright=normalized.upright,
    )


def deduplicate_raw_hands(
    raw_hands: list[RawDetectedHandState],
) -> list[RawDetectedHandState]:
    return deduplicate_hands_by_landmarks(
        raw_hands,
        lambda raw_hand: raw_hand.landmarks,
    )


def deduplicate_hands_by_landmarks[T](
    hands: list[T],
    landmarks_for_hand: Callable[[T], list[Any]],
) -> list[T]:
    deduplicated: list[T] = []
    for hand in hands:
        duplicate_index = _find_duplicate_index(
            deduplicated,
            hand,
            landmarks_for_hand,
        )
        if duplicate_index is None:
            deduplicated.append(hand)
            continue

        if _hand_size(landmarks_for_hand(hand)) > _hand_size(
            landmarks_for_hand(deduplicated[duplicate_index])
        ):
            deduplicated[duplicate_index] = hand
    return deduplicated


def hand_landmark_sets_are_duplicates(
    first_landmarks: list[Any],
    second_landmarks: list[Any],
) -> bool:
    first_center_x, first_center_y, first_size = hand_center(first_landmarks)
    second_center_x, second_center_y, second_size = hand_center(second_landmarks)
    center_distance = math.hypot(
        first_center_x - second_center_x,
        first_center_y - second_center_y,
    )
    center_threshold = (
        min(first_size, second_size) * DUPLICATE_HAND_MAX_CENTER_DISTANCE_RATIO
    )
    if center_distance <= center_threshold:
        return True

    return (
        _box_iou(_landmark_box(first_landmarks), _landmark_box(second_landmarks))
        >= DUPLICATE_HAND_MIN_BOX_IOU
    )


def _find_duplicate_index[T](
    hands: list[T],
    candidate: T,
    landmarks_for_hand: Callable[[T], list[Any]],
) -> int | None:
    candidate_landmarks = landmarks_for_hand(candidate)
    for index, hand in enumerate(hands):
        if hand_landmark_sets_are_duplicates(
            landmarks_for_hand(hand),
            candidate_landmarks,
        ):
            return index
    return None


def _hand_size(landmarks: list[Any]) -> float:
    _, _, size = hand_center(landmarks)
    return size


def _landmark_box(landmarks: list[Any]) -> tuple[float, float, float, float]:
    return (
        min(landmark.x for landmark in landmarks),
        min(landmark.y for landmark in landmarks),
        max(landmark.x for landmark in landmarks),
        max(landmark.y for landmark in landmarks),
    )


def _box_iou(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    first_min_x, first_min_y, first_max_x, first_max_y = first
    second_min_x, second_min_y, second_max_x, second_max_y = second
    intersection_width = max(
        0.0,
        min(first_max_x, second_max_x) - max(first_min_x, second_min_x),
    )
    intersection_height = max(
        0.0,
        min(first_max_y, second_max_y) - max(first_min_y, second_min_y),
    )
    intersection_area = intersection_width * intersection_height
    if intersection_area == 0:
        return 0.0

    first_area = max(0.0, first_max_x - first_min_x) * max(
        0.0, first_max_y - first_min_y
    )
    second_area = max(0.0, second_max_x - second_min_x) * max(
        0.0, second_max_y - second_min_y
    )
    union_area = first_area + second_area - intersection_area
    if union_area <= 0:
        return 0.0
    return intersection_area / union_area
