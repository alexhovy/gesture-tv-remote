from typing import Any

from src.application.ports.camera import CameraPort, FrameProcessorPort
from src.application.ports.frame_source import FrameSourcePort
from src.application.services.pipeline_metrics import PipelineMetrics
from src.domain.geometry.camera_geometry import CroppedFrame


class FrameCapturePipeline:
    def __init__(
        self,
        frame_processor: FrameProcessorPort,
        frame_source: FrameSourcePort | None = None,
        metrics: PipelineMetrics | None = None,
    ) -> None:
        self._frame_processor = frame_processor
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
        if self._metrics is not None and not self._metrics.record_frame_version(
            version
        ):
            return None
        return frame

    def flip_frame(self, frame: Any) -> Any:
        return self._frame_processor.flip_frame(frame)

    def detection_frame(
        self,
        frame: Any,
        zoom_controller: CameraPort,
    ) -> CroppedFrame:
        return self._frame_processor.detection_frame(frame, zoom_controller)

    def display_frame(
        self,
        frame: Any,
        zoom_controller: CameraPort,
    ) -> CroppedFrame:
        return self._frame_processor.display_frame(frame, zoom_controller)
