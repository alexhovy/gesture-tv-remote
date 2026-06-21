from dataclasses import dataclass
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


@dataclass(frozen=True)
class TvAdapterCapabilities:
    supports_power: bool
    supports_volume: bool
    supports_directional_navigation: bool
    supports_media_controls: bool
    supports_text_input: bool
    supports_source_selection: bool
    supports_wake_on_lan: bool
    supports_pairing: bool
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
