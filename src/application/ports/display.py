from typing import Any, Protocol

from src.application.ports.hand_tracker import DetectedHand
from src.domain.geometry.camera_geometry import CropRect
from src.domain.session.session_types import PointerDebug, VolumeDebug


class DisplayPort(Protocol):
    def debug_message(
        self,
        decision_debug_message: str,
        detection_crop: CropRect,
        display_crop: CropRect,
        zoom_frozen: bool = False,
    ) -> str: ...

    def draw_detected_hands(
        self,
        frame: Any,
        detected_hands: list[DetectedHand],
        source_crop: CropRect,
        display_crop: CropRect,
    ) -> None: ...

    def draw_pointer_zones(
        self,
        frame: Any,
        pointer_debug: PointerDebug | None,
        display_crop: CropRect,
    ) -> None: ...

    def draw_volume_zones(
        self,
        frame: Any,
        volume_debug: VolumeDebug | None,
        display_crop: CropRect,
    ) -> None: ...

    def render(self, app_name: str, frame: Any) -> bool: ...

    def close(self) -> None: ...
