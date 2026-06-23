from src.application.pipelines.command_dispatch import CommandDispatchPipeline
from src.application.pipelines.detection import DetectionPipeline
from src.application.pipelines.frame_capture import FrameCapturePipeline
from src.application.pipelines.gesture_decision import GestureDecisionPipeline

__all__ = [
    "CommandDispatchPipeline",
    "DetectionPipeline",
    "FrameCapturePipeline",
    "GestureDecisionPipeline",
]
