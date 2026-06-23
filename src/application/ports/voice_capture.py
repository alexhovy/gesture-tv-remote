from typing import Protocol

from src.shared.config import AppConfig


class VoiceCapturePort(Protocol):
    def update_config(self, config: AppConfig) -> None: ...

    async def capture(self) -> None: ...
