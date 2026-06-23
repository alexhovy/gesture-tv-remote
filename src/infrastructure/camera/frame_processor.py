from typing import Any

import cv2

from src.application.ports.camera import CameraPort
from src.domain.camera_geometry import CroppedFrame
from src.infrastructure.camera.video_preprocessing import apply_crop


class OpenCvFrameProcessor:
    def flip_frame(self, frame: Any) -> Any:
        return cv2.flip(frame, 1)

    def detection_frame(self, frame: Any, camera: CameraPort) -> CroppedFrame:
        return apply_crop(frame, camera.detection_crop())

    def display_frame(self, frame: Any, camera: CameraPort) -> CroppedFrame:
        return apply_crop(frame, camera.current_crop())

    def close(self) -> None:
        cv2.destroyAllWindows()
