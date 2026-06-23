from typing import Protocol

from src.application.ports.logger import LoggerPort


class MetricsPort(Protocol):
    def record_frame_version(self, version: int) -> bool: ...

    def record_detection(self, elapsed_seconds: float) -> None: ...

    def record_decision(self, elapsed_seconds: float, gesture: str | None) -> None: ...

    def record_dispatch(
        self,
        queue_depth: int,
        send_latency_seconds: float | None,
        dropped_commands: int = 0,
    ) -> None: ...

    def log_if_due(
        self,
        logger: LoggerPort,
        now: float,
        enabled: bool,
        interval_seconds: float,
    ) -> None: ...
