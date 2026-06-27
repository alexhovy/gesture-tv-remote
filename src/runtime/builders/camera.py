from __future__ import annotations

from dataclasses import dataclass

from src.application.ports.camera import CameraPort, FrameProcessorPort
from src.application.ports.display import DisplayPort
from src.application.ports.frame_source import FrameSourcePort
from src.application.ports.hand_tracker import HandTrackerPort
from src.shared.config import AppConfig


@dataclass(frozen=True)
class CameraRuntimeDependencies:
    frame_source: FrameSourcePort
    hand_tracker: HandTrackerPort
    camera: CameraPort
    frame_processor: FrameProcessorPort
    display: DisplayPort


def build_camera_dependencies(config: AppConfig) -> CameraRuntimeDependencies:
    import cv2

    from src.infrastructure.camera.camera_zoom import CameraZoomController
    from src.infrastructure.camera.display import OpenCvDisplay
    from src.infrastructure.camera.frame_processor import OpenCvFrameProcessor
    from src.infrastructure.camera.frame_source import LatestFrameSource
    from src.infrastructure.hand_tracking.hand_tracking import MediaPipeHandTracker
    from src.infrastructure.hand_tracking.model_store import MediaPipeModelStore

    MediaPipeModelStore(config).ensure_model()
    return CameraRuntimeDependencies(
        frame_source=LatestFrameSource(cv2.VideoCapture(config.camera.webcam_index)),
        hand_tracker=MediaPipeHandTracker(config),
        camera=CameraZoomController(config),
        frame_processor=OpenCvFrameProcessor(),
        display=OpenCvDisplay(),
    )
