from types import SimpleNamespace
from typing import Any

import cv2

from src.application.ports.hand_tracker import DetectedHand
from src.domain.geometry.camera_geometry import CropRect
from src.domain.geometry.landmark_projection import (
    landmarks_to_crop_space,
    landmarks_to_original_space,
)
from src.domain.session.session_types import PointerDebug, VolumeDebug
from src.infrastructure.camera.video_overlay import (
    draw_pointer_zones,
    draw_simple_landmarks,
    draw_volume_zones,
)

OVERLAY_SMOOTHING_ALPHA = 0.45
OVERLAY_MISSING_GRACE_FRAMES = 2


class OpenCvDisplay:
    def __init__(self) -> None:
        self._overlay_smoother = OverlayLandmarkSmoother()

    def debug_message(
        self,
        decision_debug_message: str,
        detection_crop: CropRect,
        display_crop: CropRect,
        zoom_frozen: bool = False,
    ) -> str:
        return (
            f"{decision_debug_message} "
            f"detection_crop={_debug_crop(detection_crop)} "
            f"display_crop={_debug_crop(display_crop)} "
            f"zoom_frozen={zoom_frozen}"
        )

    def draw_detected_hands(
        self,
        frame: Any,
        detected_hands: list[DetectedHand],
        source_crop: CropRect,
        display_crop: CropRect,
    ) -> None:
        original_landmarks_by_hand = [
            landmarks_to_original_space(detected_hand.landmarks, source_crop)
            for detected_hand in detected_hands
        ]
        for original_landmarks in self._overlay_smoother.update(
            original_landmarks_by_hand
        ):
            draw_simple_landmarks(
                frame,
                landmarks_to_crop_space(original_landmarks, display_crop),
            )

    def draw_pointer_zones(
        self,
        frame: Any,
        pointer_debug: PointerDebug | None,
        display_crop: CropRect,
    ) -> None:
        draw_pointer_zones(frame, pointer_debug, display_crop)

    def draw_volume_zones(
        self,
        frame: Any,
        volume_debug: VolumeDebug | None,
        display_crop: CropRect,
    ) -> None:
        draw_volume_zones(frame, volume_debug, display_crop)

    def render(self, app_name: str, frame: Any) -> bool:
        cv2.imshow(app_name, frame)
        return bool(cv2.pollKey() & 0xFF == ord("q"))

    def close(self) -> None:
        cv2.destroyAllWindows()


def _debug_crop(crop: CropRect) -> str:
    return f"({crop.x:.2f},{crop.y:.2f}," f"{crop.width:.2f},{crop.height:.2f})"


class OverlayLandmarkSmoother:
    def __init__(
        self,
        alpha: float = OVERLAY_SMOOTHING_ALPHA,
        missing_grace_frames: int = OVERLAY_MISSING_GRACE_FRAMES,
    ) -> None:
        self._alpha = max(0.0, min(alpha, 1.0))
        self._missing_grace_frames = max(0, missing_grace_frames)
        self._previous: list[list[Any]] = []
        self._missing_frames = 0

    def update(self, landmarks_by_hand: list[list[Any]]) -> list[list[Any]]:
        if not landmarks_by_hand:
            if self._previous and self._missing_frames < self._missing_grace_frames:
                self._missing_frames += 1
                return self._previous
            self._previous = []
            self._missing_frames = 0
            return []

        smoothed = []
        for index, landmarks in enumerate(landmarks_by_hand):
            previous = self._previous[index] if index < len(self._previous) else None
            if previous is None or len(previous) != len(landmarks):
                smoothed.append(landmarks)
            else:
                smoothed.append(_blend_landmarks(previous, landmarks, self._alpha))

        self._previous = smoothed
        self._missing_frames = 0
        return smoothed


def _blend_landmarks(
    previous: list[Any], current: list[Any], alpha: float
) -> list[Any]:
    return [
        _blend_landmark(previous_landmark, current_landmark, alpha)
        for previous_landmark, current_landmark in zip(previous, current, strict=True)
    ]


def _blend_landmark(previous: Any, current: Any, alpha: float) -> Any:
    blended = SimpleNamespace(
        x=previous.x + alpha * (current.x - previous.x),
        y=previous.y + alpha * (current.y - previous.y),
    )
    for attribute in ("z", "visibility", "presence"):
        if hasattr(current, attribute):
            current_value = getattr(current, attribute)
            if hasattr(previous, attribute):
                previous_value = getattr(previous, attribute)
                if isinstance(current_value, (int, float)) and isinstance(
                    previous_value, (int, float)
                ):
                    current_value = previous_value + alpha * (
                        current_value - previous_value
                    )
            setattr(blended, attribute, current_value)
    return blended
