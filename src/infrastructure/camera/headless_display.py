from typing import Any

from src.application.ports.hand_tracker import DetectedHand
from src.domain.geometry.camera_geometry import CropRect
from src.domain.session.session_types import PointerDebug, VolumeDebug


class HeadlessDisplay:
    def debug_message(
        self,
        decision_debug_message: str,
        detection_crop: CropRect,
        display_crop: CropRect,
        zoom_frozen: bool = False,
    ) -> str:
        return (
            f"{decision_debug_message} "
            f"detection_crop=({detection_crop.x:.2f},{detection_crop.y:.2f},"
            f"{detection_crop.width:.2f},{detection_crop.height:.2f}) "
            f"display_crop=({display_crop.x:.2f},{display_crop.y:.2f},"
            f"{display_crop.width:.2f},{display_crop.height:.2f}) "
            f"zoom_frozen={zoom_frozen}"
        )

    def draw_detected_hands(
        self,
        frame: Any,
        detected_hands: list[DetectedHand],
        source_crop: CropRect,
        display_crop: CropRect,
    ) -> None:
        del frame, detected_hands, source_crop, display_crop

    def draw_pointer_zones(
        self,
        frame: Any,
        pointer_debug: PointerDebug | None,
        display_crop: CropRect,
    ) -> None:
        del frame, pointer_debug, display_crop

    def draw_volume_zones(
        self,
        frame: Any,
        volume_debug: VolumeDebug | None,
        display_crop: CropRect,
    ) -> None:
        del frame, volume_debug, display_crop

    def render(self, app_name: str, frame: Any) -> bool:
        del app_name, frame
        return False

    def close(self) -> None:
        pass
