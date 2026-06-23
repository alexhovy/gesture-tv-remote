from dataclasses import dataclass
from typing import Any, Protocol

from src.domain.session_types import HandState
from src.shared.config import AppConfig


@dataclass(frozen=True)
class DetectedHand:
    landmarks: list[Any]
    handedness: str


class HandTrackerPort(Protocol):
    def update_config(self, config: AppConfig) -> None: ...

    def detect(
        self,
        frame: Any,
        timestamp_ms: int,
    ) -> tuple[list[HandState], list[DetectedHand]]: ...

    def close(self) -> None: ...
