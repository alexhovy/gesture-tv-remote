from typing import Any

import cv2

from src.infrastructure.camera.camera_zoom import CameraZoomController
from src.infrastructure.camera.frame_source import LatestFrameSource
from src.infrastructure.camera.video_preprocessing import (
    CroppedFrame,
    apply_crop,
)
from src.services.pipeline_metrics import PipelineMetrics


class FrameCapturePipeline:
    def __init__(
        self,
        frame_source: LatestFrameSource | None = None,
        metrics: PipelineMetrics | None = None,
    ) -> None:
        self._frame_source = frame_source
        self._metrics = metrics

    def start(self) -> None:
        if self._frame_source is None:
            return
        self._frame_source.start()

    def latest_frame(self) -> Any | None:
        if self._frame_source is None:
            return None
        version, frame = self._frame_source.latest_versioned()
        if self._metrics is not None and not self._metrics.record_frame_version(version):
            return None
        return frame

    def flip_frame(self, frame: Any) -> Any:
        return cv2.flip(frame, 1)

    def detection_frame(
        self,
        frame: Any,
        zoom_controller: CameraZoomController,
    ) -> CroppedFrame:
        return apply_crop(frame, zoom_controller.current_crop())

    def display_frame(
        self,
        frame: Any,
        zoom_controller: CameraZoomController,
    ) -> CroppedFrame:
        return apply_crop(frame, zoom_controller.current_crop())
