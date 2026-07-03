from dataclasses import dataclass

from src.domain.geometry.camera_geometry import CropRect


@dataclass(frozen=True)
class DisplayMotionScale:
    x: float = 1.0
    y: float = 1.0


def motion_scale_for_rendered_crop(
    display_crop: CropRect,
    rendered_width: float,
    rendered_height: float,
) -> DisplayMotionScale:
    if (
        display_crop.width <= 0
        or display_crop.height <= 0
        or rendered_width <= 0
        or rendered_height <= 0
    ):
        return DisplayMotionScale()

    shortest_rendered_side = min(rendered_width, rendered_height)
    shortest_crop_side = min(display_crop.width, display_crop.height)
    return DisplayMotionScale(
        x=(rendered_width / shortest_rendered_side)
        * (shortest_crop_side / display_crop.width),
        y=(rendered_height / shortest_rendered_side)
        * (shortest_crop_side / display_crop.height),
    )
