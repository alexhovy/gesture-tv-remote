import math
from dataclasses import dataclass
from typing import Any

from src.domain.geometry.camera_geometry import CropRect
from src.domain.geometry.landmark_projection import landmarks_to_original_bounds
from src.infrastructure.camera.crop_geometry import clamp, crop_from_center_zoom
from src.infrastructure.camera.video_preprocessing import center_crop_for_zoom
from src.shared.config import AppConfig

DETECTION_ZOOM_RATIO = 0.75
DETECTION_SMOOTHING_RATIO = 0.5


@dataclass
class _ZoomState:
    center_x: float
    center_y: float
    zoom: float


class CameraZoomController:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._min_zoom = max(
            1.0,
            min(config.camera.auto_zoom_min, config.camera.auto_zoom_max),
        )
        self._max_zoom = max(self._min_zoom, config.camera.auto_zoom_max)
        self.reset()

    def update_config(self, config: AppConfig) -> None:
        previous_min_zoom = self._min_zoom
        previous_max_zoom = self._max_zoom
        previous_auto_zoom_enabled = self._config.camera.auto_zoom_enabled
        previous_camera_zoom = self._config.camera.zoom
        self._config = config
        self._min_zoom = max(
            1.0,
            min(config.camera.auto_zoom_min, config.camera.auto_zoom_max),
        )
        self._max_zoom = max(self._min_zoom, config.camera.auto_zoom_max)
        if (
            self._min_zoom != previous_min_zoom
            or self._max_zoom != previous_max_zoom
            or config.camera.auto_zoom_enabled != previous_auto_zoom_enabled
            or config.camera.zoom != previous_camera_zoom
        ):
            self.reset()

    def current_crop(self) -> CropRect:
        if not self._config.camera.auto_zoom_enabled:
            return center_crop_for_zoom(self._config.camera.zoom)

        return crop_from_center_zoom(
            self._display.center_x,
            self._display.center_y,
            self._display.zoom,
        )

    def detection_crop(self) -> CropRect:
        if not self._config.camera.auto_zoom_enabled:
            return center_crop_for_zoom(self._config.camera.zoom)

        return crop_from_center_zoom(
            self._detection.center_x,
            self._detection.center_y,
            self._detection.zoom,
        )

    def reset(self) -> None:
        zoom = clamp(
            max(self._min_zoom, self._config.camera.zoom),
            self._min_zoom,
            self._max_zoom,
        )
        self._display = _ZoomState(0.5, 0.5, zoom)
        self._detection = _ZoomState(0.5, 0.5, zoom)

    def update(self, landmarks_by_hand: list[list[Any]], crop: CropRect) -> bool:
        if not self._config.camera.auto_zoom_enabled:
            return False

        before_crop = self.current_crop()
        before_detection_crop = self.detection_crop()

        hand_bounds = [
            landmarks_to_original_bounds(landmarks, crop)
            for landmarks in landmarks_by_hand
            if landmarks
        ]
        if not hand_bounds:
            self._move_display_toward(0.5, 0.5, self._min_zoom)
            self._move_detection_toward(0.5, 0.5, self._min_zoom)
            return self._crop_changed(before_crop) or self._crop_changed(
                before_detection_crop,
                self.detection_crop(),
            )

        target_x, target_y, target_zoom = self._target_for_bounds(hand_bounds)
        if self._should_update_display(target_x, target_y, target_zoom):
            self._move_display_toward(target_x, target_y, target_zoom)

        display_crop = self.current_crop()
        detection_target_zoom = self._detection_target_zoom(hand_bounds, display_crop)
        self._move_detection_toward(target_x, target_y, detection_target_zoom)
        return self._crop_changed(before_crop) or self._crop_changed(
            before_detection_crop,
            self.detection_crop(),
        )

    def update_if_current_crop_needs_landmarks(
        self,
        landmarks_by_hand: list[list[Any]],
        crop: CropRect,
    ) -> bool:
        if not self._config.camera.auto_zoom_enabled:
            return False

        hand_bounds = [
            landmarks_to_original_bounds(landmarks, crop)
            for landmarks in landmarks_by_hand
            if landmarks
        ]
        if not (
            _bounds_near_crop_edge(
                hand_bounds,
                self.current_crop(),
                self._config.camera.auto_zoom_position_deadband,
            )
            or _bounds_near_crop_edge(
                hand_bounds,
                self.detection_crop(),
                self._config.camera.auto_zoom_position_deadband,
            )
        ):
            return False

        return self.update(landmarks_by_hand, crop)

    def _target_for_bounds(
        self, hand_bounds: list[CropRect]
    ) -> tuple[float, float, float]:
        min_x = min(bounds.x for bounds in hand_bounds)
        min_y = min(bounds.y for bounds in hand_bounds)
        max_x = max(bounds.x + bounds.width for bounds in hand_bounds)
        max_y = max(bounds.y + bounds.height for bounds in hand_bounds)
        return (
            (min_x + max_x) / 2,
            (min_y + max_y) / 2,
            self._target_zoom(max_x - min_x, max_y - min_y),
        )

    def _target_zoom(self, bounds_width: float, bounds_height: float) -> float:
        padding = max(0.0, self._config.camera.auto_zoom_padding)
        required_width = max(0.01, bounds_width * (1 + padding * 2))
        required_height = max(0.01, bounds_height * (1 + padding * 2))
        zoom = 1 / max(required_width, required_height)
        return clamp(zoom, self._min_zoom, self._max_zoom)

    def _detection_target_zoom(
        self,
        hand_bounds: list[CropRect],
        display_crop: CropRect,
    ) -> float:
        detection_crop = self.detection_crop()
        deadband = self._config.camera.auto_zoom_position_deadband
        if _bounds_near_crop_edge(hand_bounds, detection_crop, deadband):
            return self._min_zoom

        display_zoom = self._display.zoom
        if _bounds_near_crop_edge(hand_bounds, display_crop, deadband):
            return max(self._min_zoom, display_zoom * DETECTION_ZOOM_RATIO)

        return display_zoom

    def _move_display_toward(
        self,
        target_x: float,
        target_y: float,
        target_zoom: float,
    ) -> None:
        self._move_state_toward(
            self._display,
            target_x,
            target_y,
            target_zoom,
            clamp(self._config.camera.auto_zoom_smoothing, 0.0, 1.0),
        )

    def _move_detection_toward(
        self,
        target_x: float,
        target_y: float,
        target_zoom: float,
    ) -> None:
        display_smoothing = clamp(self._config.camera.auto_zoom_smoothing, 0.0, 1.0)
        self._move_state_toward(
            self._detection,
            target_x,
            target_y,
            target_zoom,
            clamp(display_smoothing * DETECTION_SMOOTHING_RATIO, 0.0, 1.0),
        )

    def _move_state_toward(
        self,
        state: _ZoomState,
        target_x: float,
        target_y: float,
        target_zoom: float,
        smoothing: float,
    ) -> None:
        state.zoom += smoothing * (target_zoom - state.zoom)
        state.zoom = clamp(state.zoom, self._min_zoom, self._max_zoom)
        crop_width = 1 / state.zoom
        crop_height = 1 / state.zoom
        min_x = crop_width / 2
        max_x = 1 - crop_width / 2
        min_y = crop_height / 2
        max_y = 1 - crop_height / 2
        state.center_x += smoothing * (clamp(target_x, min_x, max_x) - state.center_x)
        state.center_y += smoothing * (clamp(target_y, min_y, max_y) - state.center_y)
        state.center_x = clamp(state.center_x, min_x, max_x)
        state.center_y = clamp(state.center_y, min_y, max_y)

    def _should_update_display(
        self,
        target_x: float,
        target_y: float,
        target_zoom: float,
    ) -> bool:
        position_deadband = max(0.0, self._config.camera.auto_zoom_position_deadband)
        scale_deadband = max(0.0, self._config.camera.auto_zoom_scale_deadband)
        center_delta = math.hypot(
            target_x - self._display.center_x,
            target_y - self._display.center_y,
        )
        scale_delta = abs(target_zoom - self._display.zoom) / max(
            self._display.zoom,
            0.01,
        )
        return center_delta >= position_deadband or scale_delta >= scale_deadband

    def _crop_changed(
        self,
        before_crop: CropRect,
        after_crop: CropRect | None = None,
    ) -> bool:
        after_crop = after_crop or self.current_crop()
        threshold = max(0.0, self._config.camera.auto_zoom_crop_reset_threshold)
        return (
            abs(after_crop.x - before_crop.x) >= threshold
            or abs(after_crop.y - before_crop.y) >= threshold
            or abs(after_crop.width - before_crop.width) >= threshold
            or abs(after_crop.height - before_crop.height) >= threshold
        )


def _bounds_near_crop_edge(
    hand_bounds: list[CropRect],
    crop: CropRect,
    margin: float,
) -> bool:
    if not hand_bounds or crop.width <= 0 or crop.height <= 0:
        return False

    margin = clamp(margin, 0.0, 0.45)
    min_x = min(bounds.x for bounds in hand_bounds)
    min_y = min(bounds.y for bounds in hand_bounds)
    max_x = max(bounds.x + bounds.width for bounds in hand_bounds)
    max_y = max(bounds.y + bounds.height for bounds in hand_bounds)
    left = (min_x - crop.x) / crop.width
    right = (max_x - crop.x) / crop.width
    top = (min_y - crop.y) / crop.height
    bottom = (max_y - crop.y) / crop.height
    return (
        left <= margin or right >= 1 - margin or top <= margin or bottom >= 1 - margin
    )
