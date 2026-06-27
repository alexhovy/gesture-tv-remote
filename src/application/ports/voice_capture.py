from typing import Protocol

from src.application.ports.tv_remote import VoiceStreamPort
from src.shared.config import AppConfig


class VoiceCapturePort(Protocol):
    def update_config(self, config: AppConfig) -> None: ...

    async def capture(self) -> None: ...

    async def capture_stream(
        self, voice_stream: VoiceStreamPort, context: str
    ) -> None: ...
