from types import SimpleNamespace
from typing import Any

from src.domain.camera_geometry import CropRect
from src.domain.landmarks import hand_center
from src.domain.session_types import HandState


def landmarks_to_original_bounds(landmarks: list[Any], crop: CropRect) -> CropRect:
    min_x = min(landmark.x for landmark in landmarks)
    min_y = min(landmark.y for landmark in landmarks)
    max_x = max(landmark.x for landmark in landmarks)
    max_y = max(landmark.y for landmark in landmarks)
    original_x = crop.x + min_x * crop.width
    original_y = crop.y + min_y * crop.height
    original_width = (max_x - min_x) * crop.width
    original_height = (max_y - min_y) * crop.height
    return CropRect(original_x, original_y, original_width, original_height)


def hand_state_to_original_space(hand_state: HandState, crop: CropRect) -> HandState:
    landmarks = landmarks_to_original_space(hand_state.landmarks, crop)
    center_x, center_y, hand_size = hand_center(landmarks)
    return HandState(
        landmarks=landmarks,
        gesture=hand_state.gesture,
        center=(center_x, center_y),
        size=hand_size,
        upright=hand_state.upright,
    )


def hand_states_to_original_space(
    hand_states: list[HandState],
    crop: CropRect,
) -> list[HandState]:
    return [
        hand_state_to_original_space(hand_state, crop) for hand_state in hand_states
    ]


def landmarks_to_original_space(landmarks: list[Any], crop: CropRect) -> list[Any]:
    return [_landmark_to_original_space(landmark, crop) for landmark in landmarks]


def landmarks_to_crop_space(landmarks: list[Any], crop: CropRect) -> list[Any]:
    if crop.width <= 0 or crop.height <= 0:
        return landmarks

    return [_landmark_to_crop_space(landmark, crop) for landmark in landmarks]


def _landmark_to_original_space(landmark: Any, crop: CropRect) -> Any:
    mapped = SimpleNamespace(
        x=crop.x + landmark.x * crop.width,
        y=crop.y + landmark.y * crop.height,
    )
    for attribute in ("z", "visibility", "presence"):
        if hasattr(landmark, attribute):
            setattr(mapped, attribute, getattr(landmark, attribute))
    return mapped


def _landmark_to_crop_space(landmark: Any, crop: CropRect) -> Any:
    mapped = SimpleNamespace(
        x=(landmark.x - crop.x) / crop.width,
        y=(landmark.y - crop.y) / crop.height,
    )
    for attribute in ("z", "visibility", "presence"):
        if hasattr(landmark, attribute):
            setattr(mapped, attribute, getattr(landmark, attribute))
    return mapped
