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


class VoiceStream(Protocol):
    def send_chunk(self, chunk: bytes) -> None:
        ...

    def end(self) -> None:
        ...


class TvRemoteClient(Protocol):
    async def connect(self) -> bool:
        ...

    async def send_key_command(self, command: str) -> None:
        ...

    async def start_voice(self) -> VoiceStream | None:
        ...

    def disconnect(self) -> None:
        ...


class TvRemoteCommandError(ValueError):
    pass
