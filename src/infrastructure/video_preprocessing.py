from dataclasses import dataclass
from typing import Any, Callable


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


def _crop_from_center_zoom(center_x: float, center_y: float, zoom: float) -> CropRect:
    zoom = max(1.0, zoom)
    crop_width = 1 / zoom
    crop_height = 1 / zoom
    x = _clamp(center_x - crop_width / 2, 0.0, 1.0 - crop_width)
    y = _clamp(center_y - crop_height / 2, 0.0, 1.0 - crop_height)
    return CropRect(x, y, crop_width, crop_height)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _resize_frame(frame: Any, size: tuple[int, int]) -> Any:
    import cv2

    return cv2.resize(frame, size, interpolation=cv2.INTER_LINEAR)
