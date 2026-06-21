from dataclasses import dataclass
from enum import Enum
from typing import Protocol


TV_ADAPTER_ANDROIDTV = "androidtv"
TV_ADAPTER_SAMSUNG = "samsung"
TV_ADAPTER_WEBOS = "webos"
TV_ADAPTER_ROKU = "roku"

SUPPORTED_TV_ADAPTERS = {
    TV_ADAPTER_ANDROIDTV,
    TV_ADAPTER_SAMSUNG,
    TV_ADAPTER_WEBOS,
    TV_ADAPTER_ROKU,
}


class CapabilityStatus(str, Enum):
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


class VoiceStream(Protocol):
    def send_chunk(self, chunk: bytes) -> None:
        ...

    def end(self) -> None:
        ...


class TvRemoteClient(Protocol):
    def capabilities(self) -> TvAdapterCapabilities:
        ...

    async def connect(self) -> bool:
        ...

    async def send_key_command(self, command: str) -> None:
        ...

    async def start_voice(self) -> VoiceStream | None:
        ...

    async def disconnect(self) -> None:
        ...


class TvRemoteCommandError(ValueError):
    pass
