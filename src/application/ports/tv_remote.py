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
    notes: tuple[str, ...] = ()


class TextInputMode(StrEnum):
    AUTO_DETECTED = "auto_detected"
    MANUAL = "manual"


class TextInputBrowserCapture(StrEnum):
    AUTO_FOCUS = "auto_focus"
    HARDWARE_KEYS = "hardware_keys"


@dataclass(frozen=True)
class TextInputCapabilities:
    focus_detection: CapabilityStatus
    send_text: CapabilityStatus
    replace_text: CapabilityStatus
    delete_text: CapabilityStatus
    submit_text: CapabilityStatus
    browser_capture: TextInputBrowserCapture = TextInputBrowserCapture.AUTO_FOCUS
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TextInputStatus:
    active: bool
    mode: TextInputMode
    value: str = ""
    label: str = ""
    app_id: str = ""


@dataclass(frozen=True)
class TvAdapterCapabilities:
    supported_commands: frozenset[str]
    power: CapabilityStatus
    volume: CapabilityStatus
    directional_navigation: CapabilityStatus
    media_controls: CapabilityStatus
    text_input: TextInputCapabilities
    source_selection: CapabilityStatus
    wake_on_lan: CapabilityStatus
    pairing: CapabilityStatus
    voice_input: VoiceInputCapabilities
    connection_type: str
    known_limitations: tuple[str, ...] = ()


class VoiceStreamPort(Protocol):
    def send_chunk(self, chunk: bytes) -> bool | None: ...

    def end(self) -> None: ...


@dataclass(frozen=True)
class AppVoiceInputRequest:
    stream: VoiceStreamPort
    session_id: int
    package_name: str


AppVoiceInputHandler = Callable[[AppVoiceInputRequest], Awaitable[None]]
TextInputHandler = Callable[[TextInputStatus], None]


class TVRemotePort(Protocol):
    def capabilities(self) -> TvAdapterCapabilities: ...

    def set_app_voice_input_handler(
        self,
        handler: AppVoiceInputHandler | None,
    ) -> None: ...

    def set_text_input_handler(self, handler: TextInputHandler | None) -> None: ...

    def text_input_status(self) -> TextInputStatus: ...

    async def connect(self) -> bool: ...

    async def wake(self) -> bool: ...

    async def discover_mac_address(self) -> str | None: ...

    async def send_command(self, command: str) -> None: ...

    async def send_text(self, text: str) -> None: ...

    async def replace_text(self, text: str) -> None: ...

    async def delete_text(self, count: int = 1) -> None: ...

    async def submit_text(self) -> None: ...

    async def start_voice(self, mode: VoiceInputMode) -> VoiceStreamPort | None: ...

    async def disconnect(self) -> None: ...
