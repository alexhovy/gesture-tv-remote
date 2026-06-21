from typing import Any

import cv2

from src.infrastructure.camera.landmark_projection import (
    landmarks_to_crop_space,
    landmarks_to_original_space,
)
from src.infrastructure.camera.video_overlay import draw_simple_landmarks
from src.infrastructure.camera.video_preprocessing import CropRect
from src.infrastructure.hand_tracking.hand_tracking import DetectedHand
from src.shared.logging import AppLogger


class DisplayPipeline:
    def __init__(self, logger: AppLogger) -> None:
        self._logger = logger

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
        for detected_hand in detected_hands:
            original_landmarks = landmarks_to_original_space(
                detected_hand.landmarks,
                source_crop,
            )
            draw_simple_landmarks(
                frame,
                landmarks_to_crop_space(original_landmarks, display_crop),
            )

    def render(self, app_name: str, frame: Any) -> bool:
        cv2.imshow(app_name, frame)
        return bool(cv2.pollKey() & 0xFF == ord("q"))


def _debug_crop(crop: CropRect) -> str:
    return (
        f"({crop.x:.2f},{crop.y:.2f},"
        f"{crop.width:.2f},{crop.height:.2f})"
    )
