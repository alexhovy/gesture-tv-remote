import time
from typing import Any

import cv2

from src.domain.session_types import HandState
from src.infrastructure.hand_tracking.hand_tracking import DetectedHand, MediaPipeHandTracker
from src.services.pipeline_metrics import PipelineMetrics


class DetectionPipeline:
    def __init__(self, metrics: PipelineMetrics | None = None) -> None:
        self._metrics = metrics

    def detect_hands(
        self,
        hand_tracker: MediaPipeHandTracker,
        frame: Any,
    ) -> tuple[list[HandState], list[DetectedHand]]:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        started_at = time.monotonic()
        result = hand_tracker.detect(rgb_frame, int(time.monotonic() * 1000))
        if self._metrics is not None:
            self._metrics.record_detection(time.monotonic() - started_at)
        return result
