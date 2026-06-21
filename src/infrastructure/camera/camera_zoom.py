import math
from typing import Any

from src.infrastructure.camera.crop_geometry import clamp, crop_from_center_zoom
from src.infrastructure.camera.landmark_projection import landmarks_to_original_bounds
from src.infrastructure.camera.video_preprocessing import CropRect, center_crop_for_zoom
from src.shared.config import AppConfig


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
            self._center_x,
            self._center_y,
            self._zoom,
        )

    def reset(self) -> None:
        self._center_x = 0.5
        self._center_y = 0.5
        self._zoom = clamp(
            max(self._min_zoom, self._config.camera.zoom),
            self._min_zoom,
            self._max_zoom,
        )

    def update(self, landmarks_by_hand: list[list[Any]], crop: CropRect) -> bool:
        if not self._config.camera.auto_zoom_enabled:
            return False

        before_crop = self.current_crop()

        hand_bounds = [
            landmarks_to_original_bounds(landmarks, crop)
            for landmarks in landmarks_by_hand
            if landmarks
        ]
        if not hand_bounds:
            self._move_toward(0.5, 0.5, self._min_zoom)
            return self._crop_changed(before_crop)

        min_x = min(bounds.x for bounds in hand_bounds)
        min_y = min(bounds.y for bounds in hand_bounds)
        max_x = max(bounds.x + bounds.width for bounds in hand_bounds)
        max_y = max(bounds.y + bounds.height for bounds in hand_bounds)
        target_x = (min_x + max_x) / 2
        target_y = (min_y + max_y) / 2
        target_zoom = self._target_zoom(max_x - min_x, max_y - min_y)
        if _bounds_near_crop_edge(
            hand_bounds,
            crop,
            self._config.camera.auto_zoom_position_deadband,
        ) and (crop.width < 1.0 or crop.height < 1.0):
            target_zoom = self._min_zoom
        if not self._should_update(target_x, target_y, target_zoom, hand_bounds, crop):
            return False
        self._move_toward(target_x, target_y, target_zoom)
        return self._crop_changed(before_crop)

    def _target_zoom(self, bounds_width: float, bounds_height: float) -> float:
        padding = max(0.0, self._config.camera.auto_zoom_padding)
        required_width = max(0.01, bounds_width * (1 + padding * 2))
        required_height = max(0.01, bounds_height * (1 + padding * 2))
        zoom = 1 / max(required_width, required_height)
        return clamp(zoom, self._min_zoom, self._max_zoom)

    def _move_toward(self, target_x: float, target_y: float, target_zoom: float) -> None:
        smoothing = clamp(self._config.camera.auto_zoom_smoothing, 0.0, 1.0)
        self._zoom += smoothing * (target_zoom - self._zoom)
        self._zoom = clamp(
            self._zoom,
            self._min_zoom,
            self._max_zoom,
        )
        crop_width = 1 / self._zoom
        crop_height = 1 / self._zoom
        min_x = crop_width / 2
        max_x = 1 - crop_width / 2
        min_y = crop_height / 2
        max_y = 1 - crop_height / 2
        self._center_x += smoothing * (clamp(target_x, min_x, max_x) - self._center_x)
        self._center_y += smoothing * (clamp(target_y, min_y, max_y) - self._center_y)
        self._center_x = clamp(self._center_x, min_x, max_x)
        self._center_y = clamp(self._center_y, min_y, max_y)

    def _should_update(
        self,
        target_x: float,
        target_y: float,
        target_zoom: float,
        hand_bounds: list[CropRect],
        crop: CropRect,
    ) -> bool:
        position_deadband = max(0.0, self._config.camera.auto_zoom_position_deadband)
        scale_deadband = max(0.0, self._config.camera.auto_zoom_scale_deadband)
        center_delta = math.hypot(target_x - self._center_x, target_y - self._center_y)
        scale_delta = abs(target_zoom - self._zoom) / max(self._zoom, 0.01)
        return (
            center_delta >= position_deadband
            or scale_delta >= scale_deadband
            or _bounds_near_crop_edge(hand_bounds, crop, position_deadband)
        )

    def _crop_changed(self, before_crop: CropRect) -> bool:
        after_crop = self.current_crop()
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
    return left <= margin or right >= 1 - margin or top <= margin or bottom >= 1 - margin
