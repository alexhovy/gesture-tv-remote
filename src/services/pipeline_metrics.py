import time
from dataclasses import dataclass

from src.shared.logging import AppLogger


@dataclass
class PipelineMetricsSnapshot:
    camera_fps: float
    detection_ms: float
    decision_ms: float
    dispatch_queue_depth: int
    command_send_latency_ms: float
    dropped_stale_frames: int
    active_tv_adapter: str
    current_gesture_decision: str


class PipelineMetrics:
    def __init__(self, adapter: str) -> None:
        self._adapter = adapter
        self._camera_frames = 0
        self._camera_started_at = time.monotonic()
        self._last_frame_version = 0
        self._dropped_stale_frames = 0
        self._detection_ms = 0.0
        self._decision_ms = 0.0
        self._dispatch_queue_depth = 0
        self._command_send_latency_ms = 0.0
        self._current_gesture_decision = "none"
        self._last_log_time = 0.0

    def record_frame_version(self, version: int) -> bool:
        if version <= self._last_frame_version:
            return False
        if self._last_frame_version:
            self._dropped_stale_frames += max(0, version - self._last_frame_version - 1)
        self._last_frame_version = version
        self._camera_frames += 1
        return True

    def record_detection(self, elapsed_seconds: float) -> None:
        self._detection_ms = elapsed_seconds * 1000.0

    def record_decision(self, elapsed_seconds: float, gesture: str | None) -> None:
        self._decision_ms = elapsed_seconds * 1000.0
        self._current_gesture_decision = gesture or "none"

    def record_dispatch(self, queue_depth: int, send_latency_seconds: float | None) -> None:
        self._dispatch_queue_depth = queue_depth
        if send_latency_seconds is not None:
            self._command_send_latency_ms = send_latency_seconds * 1000.0

    def snapshot(self) -> PipelineMetricsSnapshot:
        elapsed = max(time.monotonic() - self._camera_started_at, 1e-9)
        return PipelineMetricsSnapshot(
            camera_fps=self._camera_frames / elapsed,
            detection_ms=self._detection_ms,
            decision_ms=self._decision_ms,
            dispatch_queue_depth=self._dispatch_queue_depth,
            command_send_latency_ms=self._command_send_latency_ms,
            dropped_stale_frames=self._dropped_stale_frames,
            active_tv_adapter=self._adapter,
            current_gesture_decision=self._current_gesture_decision,
        )

    def log_if_due(
        self,
        logger: AppLogger,
        now: float,
        enabled: bool,
        interval_seconds: float,
    ) -> None:
        if not enabled:
            return
        if now - self._last_log_time < interval_seconds:
            return
        self._last_log_time = now
        snapshot = self.snapshot()
        logger.debug(
            "pipeline_metrics "
            f"camera_fps={snapshot.camera_fps:.1f} "
            f"detection_ms={snapshot.detection_ms:.1f} "
            f"decision_ms={snapshot.decision_ms:.1f} "
            f"dispatch_queue_depth={snapshot.dispatch_queue_depth} "
            f"command_send_latency_ms={snapshot.command_send_latency_ms:.1f} "
            f"dropped_stale_frames={snapshot.dropped_stale_frames} "
            f"active_tv_adapter={snapshot.active_tv_adapter} "
            f"current_gesture_decision={snapshot.current_gesture_decision}"
        )
