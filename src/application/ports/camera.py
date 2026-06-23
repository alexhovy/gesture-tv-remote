from typing import Any, Protocol

from src.domain.camera_geometry import CroppedFrame, CropRect
from src.shared.config import AppConfig


class CameraPort(Protocol):
    def update_config(self, config: AppConfig) -> None: ...

    def current_crop(self) -> CropRect: ...

    def detection_crop(self) -> CropRect: ...

    def update(self, landmarks_by_hand: list[list[Any]], crop: CropRect) -> bool: ...

    def update_if_current_crop_needs_landmarks(
        self,
        landmarks_by_hand: list[list[Any]],
        crop: CropRect,
    ) -> bool: ...


class FrameProcessorPort(Protocol):
    def flip_frame(self, frame: Any) -> Any: ...

    def detection_frame(self, frame: Any, camera: CameraPort) -> CroppedFrame: ...

    def display_frame(self, frame: Any, camera: CameraPort) -> CroppedFrame: ...

    def close(self) -> None: ...
