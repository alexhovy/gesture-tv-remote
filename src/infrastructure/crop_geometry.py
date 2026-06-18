from src.infrastructure.video_preprocessing import CropRect


def crop_from_center_zoom(center_x: float, center_y: float, zoom: float) -> CropRect:
    zoom = max(1.0, zoom)
    crop_width = 1 / zoom
    crop_height = 1 / zoom
    x = clamp(center_x - crop_width / 2, 0.0, 1.0 - crop_width)
    y = clamp(center_y - crop_height / 2, 0.0, 1.0 - crop_height)
    return CropRect(x, y, crop_width, crop_height)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)
