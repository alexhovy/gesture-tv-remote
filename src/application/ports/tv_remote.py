from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class CapabilityStatus(StrEnum):
    IMPLEMENTED = "implemented"
    NOT_IMPLEMENTED = "not_implemented"
    UNSUPPORTED = "unsupported"


class VoiceInputMode(StrEnum):
    REMOTE_MIC_STREAM = "remote_mic_stream"
    NATIVE_VOICE_SEARCH = "native_voice_search"
    APP_VOICE_INPUT = "app_voice_input"


@dataclass(frozen=True)
class VoiceInputCapabilities:
    remote_mic_stream: CapabilityStatus
    native_voice_search: CapabilityStatus
    app_voice_input: CapabilityStatus
    app_text_input: CapabilityStatus
    notes: tuple[str, ...] = ()


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
    voice_input: VoiceInputCapabilities
    connection_type: str
    known_limitations: tuple[str, ...] = ()


class VoiceStreamPort(Protocol):
    def send_chunk(self, chunk: bytes) -> None: ...

    def end(self) -> None: ...


class TVRemotePort(Protocol):
    def capabilities(self) -> TvAdapterCapabilities: ...

    async def connect(self) -> bool: ...

    async def send_command(self, command: str) -> None: ...

    async def start_voice(self, mode: VoiceInputMode) -> VoiceStreamPort | None: ...

    async def disconnect(self) -> None: ...
