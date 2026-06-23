from typing import Any

from src.application.ports.hand_tracker import DetectedHand
from src.domain.session.session_types import HandState
from src.shared.config import AppConfig


class FakeHandTracker:
    def __init__(
        self,
        results: tuple[list[HandState], list[DetectedHand]] | None = None,
    ) -> None:
        self.results = results or ([], [])
        self.detected_frames: list[Any] = []
        self.config: AppConfig | None = None
        self.closed = False

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    def detect(
        self,
        frame: Any,
        timestamp_ms: int,
    ) -> tuple[list[HandState], list[DetectedHand]]:
        del timestamp_ms
        self.detected_frames.append(frame)
        return self.results

    def close(self) -> None:
        self.closed = True
