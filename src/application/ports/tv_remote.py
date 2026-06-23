from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class CapabilityStatus(StrEnum):
    IMPLEMENTED = "implemented"
    NOT_IMPLEMENTED = "not_implemented"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class TvAdapterCapabilities:
    power: CapabilityStatus
    volume: CapabilityStatus
    directional_navigation: CapabilityStatus
    media_controls: CapabilityStatus
    text_input: CapabilityStatus
    source_selection: CapabilityStatus
    wake_on_lan: CapabilityStatus
    pairing: CapabilityStatus
    voice_capture: CapabilityStatus
    connection_type: str
    known_limitations: tuple[str, ...] = ()


class VoiceStreamPort(Protocol):
    def send_chunk(self, chunk: bytes) -> None: ...

    def end(self) -> None: ...


class TVRemotePort(Protocol):
    def capabilities(self) -> TvAdapterCapabilities: ...

    async def connect(self) -> bool: ...

    async def send_command(self, command: str) -> None: ...

    async def start_voice(self) -> VoiceStreamPort | None: ...

    async def disconnect(self) -> None: ...
