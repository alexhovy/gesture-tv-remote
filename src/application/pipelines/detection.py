import time
from typing import Any

from src.domain.session_types import HandState
from src.application.services.pipeline_metrics import PipelineMetrics
from src.application.ports.hand_tracker import DetectedHand, HandTrackerPort


class DetectionPipeline:
    def __init__(self, metrics: PipelineMetrics | None = None) -> None:
        self._metrics = metrics

    def detect_hands(
        self,
        hand_tracker: HandTrackerPort,
        frame: Any,
    ) -> tuple[list[HandState], list[DetectedHand]]:
        started_at = time.monotonic()
        result = hand_tracker.detect(frame, int(time.monotonic() * 1000))
        if self._metrics is not None:
            self._metrics.record_detection(time.monotonic() - started_at)
        return result
