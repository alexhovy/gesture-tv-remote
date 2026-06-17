from dataclasses import dataclass
import math
from types import SimpleNamespace
from typing import Any, Callable

from src.domain.landmarks import hand_center
from src.domain.session import HandState
from src.shared.config import AppConfig


@dataclass(frozen=True)
class CropRect:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class CroppedFrame:
    frame: Any
    crop: CropRect


class CameraZoomController:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._min_zoom = max(1.0, min(config.auto_zoom_min, config.auto_zoom_max))
        self._max_zoom = max(self._min_zoom, config.auto_zoom_max)
        self._center_x = 0.5
        self._center_y = 0.5
        self._zoom = _clamp(max(self._min_zoom, config.camera_zoom), self._min_zoom, self._max_zoom)

    def current_crop(self) -> CropRect:
        if not self._config.auto_zoom_enabled:
            return center_crop_for_zoom(self._config.camera_zoom)

        return _crop_from_center_zoom(
            self._center_x,
            self._center_y,
            self._zoom,
        )

    def update(self, landmarks_by_hand: list[list[Any]], crop: CropRect) -> bool:
        if not self._config.auto_zoom_enabled:
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
        if not self._should_update(target_x, target_y, target_zoom, hand_bounds, crop):
            return False
        self._move_toward(target_x, target_y, target_zoom)
        return self._crop_changed(before_crop)

    def _target_zoom(self, bounds_width: float, bounds_height: float) -> float:
        padding = max(0.0, self._config.auto_zoom_padding)
        required_width = max(0.01, bounds_width * (1 + padding * 2))
        required_height = max(0.01, bounds_height * (1 + padding * 2))
        zoom = 1 / max(required_width, required_height)
        return _clamp(zoom, self._min_zoom, self._max_zoom)

    def _move_toward(self, target_x: float, target_y: float, target_zoom: float) -> None:
        smoothing = _clamp(self._config.auto_zoom_smoothing, 0.0, 1.0)
        self._zoom += smoothing * (target_zoom - self._zoom)
        self._zoom = _clamp(
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
        self._center_x += smoothing * (_clamp(target_x, min_x, max_x) - self._center_x)
        self._center_y += smoothing * (_clamp(target_y, min_y, max_y) - self._center_y)
        self._center_x = _clamp(self._center_x, min_x, max_x)
        self._center_y = _clamp(self._center_y, min_y, max_y)

    def _should_update(
        self,
        target_x: float,
        target_y: float,
        target_zoom: float,
        hand_bounds: list[CropRect],
        crop: CropRect,
    ) -> bool:
        position_deadband = max(0.0, self._config.auto_zoom_position_deadband)
        scale_deadband = max(0.0, self._config.auto_zoom_scale_deadband)
        center_delta = math.hypot(target_x - self._center_x, target_y - self._center_y)
        scale_delta = abs(target_zoom - self._zoom) / max(self._zoom, 0.01)
        return (
            center_delta >= position_deadband
            or scale_delta >= scale_deadband
            or _bounds_near_crop_edge(hand_bounds, crop, position_deadband)
        )

    def _crop_changed(self, before_crop: CropRect) -> bool:
        after_crop = self.current_crop()
        threshold = max(0.0, self._config.auto_zoom_crop_reset_threshold)
        return (
            abs(after_crop.x - before_crop.x) >= threshold
            or abs(after_crop.y - before_crop.y) >= threshold
            or abs(after_crop.width - before_crop.width) >= threshold
            or abs(after_crop.height - before_crop.height) >= threshold
        )


def apply_center_crop_zoom(
    frame: Any,
    zoom: float,
    resize: Callable[[Any, tuple[int, int]], Any] | None = None,
) -> Any:
    if zoom <= 1.0:
        return frame

    return apply_crop(frame, center_crop_for_zoom(zoom), resize).frame


def apply_crop(
    frame: Any,
    crop: CropRect,
    resize: Callable[[Any, tuple[int, int]], Any] | None = None,
) -> CroppedFrame:
    if crop == CropRect(0.0, 0.0, 1.0, 1.0):
        return CroppedFrame(frame=frame, crop=crop)

    resize_frame = resize or _resize_frame
    height, width = frame.shape[:2]
    x1 = int(crop.x * width)
    y1 = int(crop.y * height)
    crop_width = max(1, int(crop.width * width))
    crop_height = max(1, int(crop.height * height))
    x1 = min(max(0, x1), width - crop_width)
    y1 = min(max(0, y1), height - crop_height)
    cropped = frame[y1 : y1 + crop_height, x1 : x1 + crop_width]
    return CroppedFrame(
        frame=resize_frame(cropped, (width, height)),
        crop=CropRect(
            x=x1 / width,
            y=y1 / height,
            width=crop_width / width,
            height=crop_height / height,
        ),
    )


def center_crop_for_zoom(zoom: float) -> CropRect:
    return _crop_from_center_zoom(0.5, 0.5, max(1.0, zoom))


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
    )


def hand_states_to_original_space(
    hand_states: list[HandState],
    crop: CropRect,
) -> list[HandState]:
    return [hand_state_to_original_space(hand_state, crop) for hand_state in hand_states]


def landmarks_to_original_space(landmarks: list[Any], crop: CropRect) -> list[Any]:
    return [_landmark_to_original_space(landmark, crop) for landmark in landmarks]


def _crop_from_center_zoom(center_x: float, center_y: float, zoom: float) -> CropRect:
    zoom = max(1.0, zoom)
    crop_width = 1 / zoom
    crop_height = 1 / zoom
    x = _clamp(center_x - crop_width / 2, 0.0, 1.0 - crop_width)
    y = _clamp(center_y - crop_height / 2, 0.0, 1.0 - crop_height)
    return CropRect(x, y, crop_width, crop_height)


def _bounds_near_crop_edge(
    hand_bounds: list[CropRect],
    crop: CropRect,
    margin: float,
) -> bool:
    if not hand_bounds or crop.width <= 0 or crop.height <= 0:
        return False

    margin = _clamp(margin, 0.0, 0.45)
    min_x = min(bounds.x for bounds in hand_bounds)
    min_y = min(bounds.y for bounds in hand_bounds)
    max_x = max(bounds.x + bounds.width for bounds in hand_bounds)
    max_y = max(bounds.y + bounds.height for bounds in hand_bounds)
    left = (min_x - crop.x) / crop.width
    right = (max_x - crop.x) / crop.width
    top = (min_y - crop.y) / crop.height
    bottom = (max_y - crop.y) / crop.height
    return left <= margin or right >= 1 - margin or top <= margin or bottom >= 1 - margin


def _landmark_to_original_space(landmark: Any, crop: CropRect) -> Any:
    mapped = SimpleNamespace(
        x=crop.x + landmark.x * crop.width,
        y=crop.y + landmark.y * crop.height,
    )
    for attribute in ("z", "visibility", "presence"):
        if hasattr(landmark, attribute):
            setattr(mapped, attribute, getattr(landmark, attribute))
    return mapped


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _resize_frame(frame: Any, size: tuple[int, int]) -> Any:
    import cv2

    return cv2.resize(frame, size, interpolation=cv2.INTER_LINEAR)
