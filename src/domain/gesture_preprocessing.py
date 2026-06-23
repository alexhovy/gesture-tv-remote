from dataclasses import dataclass
from typing import Any

from src.domain.gesture_classification import classify_static_hand_pose
from src.domain.landmarks import hand_center, hand_is_upright
from src.domain.session_types import HandState
from src.shared.config import GestureConfig


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
