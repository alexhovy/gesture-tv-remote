from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from src.application.ports.hand_tracker import DetectedHand
from src.domain.geometry.camera_geometry import CropRect
from src.domain.geometry.landmark_projection import (
    landmarks_to_crop_space,
    landmarks_to_original_space,
)
from src.domain.session.session_types import PointerDebug, VolumeDebug
from src.infrastructure.web.debug_stream import BrowserDebugStream

OVERLAY_SMOOTHING_ALPHA = 0.45
OVERLAY_MISSING_GRACE_FRAMES = 2


class BrowserDebugDisplay:
    def __init__(self, stream: BrowserDebugStream) -> None:
        self._stream = stream
        self._overlay_smoother = OverlayLandmarkSmoother()
        self._snapshot: dict[str, Any] = {}

    def debug_message(
        self,
        decision_debug_message: str,
        detection_crop: CropRect,
        display_crop: CropRect,
        zoom_frozen: bool = False,
    ) -> str:
        self._snapshot = {
            "debugMessage": decision_debug_message,
            "detectionCrop": _crop_to_json(detection_crop),
            "displayCrop": _crop_to_json(display_crop),
            "zoomFrozen": zoom_frozen,
            "hands": [],
            "pointer": None,
            "volume": None,
        }
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
        del frame
        original_landmarks_by_hand = [
            landmarks_to_original_space(detected_hand.landmarks, source_crop)
            for detected_hand in detected_hands
        ]
        hands = []
        for original_landmarks in self._overlay_smoother.update(
            original_landmarks_by_hand
        ):
            crop_landmarks = landmarks_to_crop_space(original_landmarks, display_crop)
            hands.append([_landmark_to_json(landmark) for landmark in crop_landmarks])
        self._snapshot["hands"] = hands

    def draw_pointer_zones(
        self,
        frame: Any,
        pointer_debug: PointerDebug | None,
        display_crop: CropRect,
    ) -> None:
        del frame, display_crop
        self._snapshot["pointer"] = _pointer_to_json(pointer_debug)

    def draw_volume_zones(
        self,
        frame: Any,
        volume_debug: VolumeDebug | None,
        display_crop: CropRect,
    ) -> None:
        del frame, display_crop
        self._snapshot["volume"] = _volume_to_json(volume_debug)

    def render(self, app_name: str, frame: Any) -> bool:
        del app_name, frame
        self._stream.publish(self._snapshot)
        return False

    def close(self) -> None:
        pass


def _crop_to_json(crop: CropRect) -> dict[str, float]:
    return {
        "x": crop.x,
        "y": crop.y,
        "width": crop.width,
        "height": crop.height,
    }


def _landmark_to_json(landmark: Any) -> dict[str, float]:
    return {
        "x": float(landmark.x),
        "y": float(landmark.y),
    }


def _pointer_to_json(pointer: PointerDebug | None) -> dict[str, Any] | None:
    if pointer is None:
        return None
    return {
        "anchor": _point_to_json(pointer.anchor),
        "current": _point_to_json(pointer.current),
        "activeGesture": pointer.active_gesture,
        "candidateGesture": pointer.candidate_gesture,
        "phase": pointer.phase,
        "armed": pointer.armed,
        "activationDistance": pointer.activation_distance,
        "neutralDistance": pointer.neutral_distance,
        "thresholdRatio": pointer.threshold_ratio,
        "inNeutral": pointer.in_neutral,
        "blockedReason": pointer.blocked_reason,
        "motionScaleX": pointer.motion_scale_x,
        "motionScaleY": pointer.motion_scale_y,
    }


def _volume_to_json(volume: VolumeDebug | None) -> dict[str, Any] | None:
    if volume is None:
        return None
    return {
        "anchor": _point_to_json(volume.anchor),
        "anchorY": volume.anchor_y,
        "current": _point_to_json(volume.current),
        "activeGesture": volume.active_gesture,
        "candidateGesture": volume.candidate_gesture,
        "phase": volume.phase,
        "armed": volume.armed,
        "activationDistance": volume.activation_distance,
        "neutralDistance": volume.neutral_distance,
        "thresholdRatio": volume.threshold_ratio,
        "inNeutral": volume.in_neutral,
        "blockedReason": volume.blocked_reason,
        "motionScaleX": volume.motion_scale_x,
        "motionScaleY": volume.motion_scale_y,
    }


def _point_to_json(point: tuple[float, float] | None) -> dict[str, float] | None:
    if point is None:
        return None
    return {"x": point[0], "y": point[1]}


def _debug_crop(crop: CropRect) -> str:
    return f"({crop.x:.2f},{crop.y:.2f},{crop.width:.2f},{crop.height:.2f})"


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
            setattr(blended, attribute, getattr(current, attribute))
    return blended
