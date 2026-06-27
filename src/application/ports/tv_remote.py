from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class CapabilityStatus(StrEnum):
    IMPLEMENTED = "implemented"
    NOT_IMPLEMENTED = "not_implemented"
    UNSUPPORTED = "unsupported"


class VoiceInputMode(StrEnum):
    AUTO = "auto"
    REMOTE_MIC_STREAM = "remote_mic_stream"
    NATIVE_VOICE_SEARCH = "native_voice_search"


@dataclass(frozen=True)
class VoiceInputCapabilities:
    remote_mic_stream: CapabilityStatus
    native_voice_search: CapabilityStatus
    app_voice_input: CapabilityStatus
    app_text_input: CapabilityStatus
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TvAdapterCapabilities:
    supported_commands: frozenset[str]
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


@dataclass(frozen=True)
class AppVoiceInputRequest:
    stream: VoiceStreamPort
    session_id: int
    package_name: str


AppVoiceInputHandler = Callable[[AppVoiceInputRequest], Awaitable[None]]


class TVRemotePort(Protocol):
    def capabilities(self) -> TvAdapterCapabilities: ...

    def set_app_voice_input_handler(
        self,
        handler: AppVoiceInputHandler | None,
    ) -> None: ...

    async def connect(self) -> bool: ...

    async def send_command(self, command: str) -> None: ...

    async def start_voice(self, mode: VoiceInputMode) -> VoiceStreamPort | None: ...

    async def disconnect(self) -> None: ...
