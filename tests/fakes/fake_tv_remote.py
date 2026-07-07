from src.application.ports.tv_remote import (
    AppVoiceInputHandler,
    CapabilityStatus,
    TextInputCapabilities,
    TextInputHandler,
    TextInputMode,
    TextInputStatus,
    TvAdapterCapabilities,
    VoiceInputCapabilities,
    VoiceInputMode,
)


class FakeTVRemote:
    def __init__(
        self,
        connected: bool = True,
        discovered_mac_address: str | None = None,
    ) -> None:
        self.connected = connected
        self.discovered_mac_address = discovered_mac_address
        self.commands: list[str] = []
        self.connect_calls = 0
        self.wake_calls = 0
        self.disconnect_calls = 0
        self.voice_started = False
        self.app_voice_input_handler: AppVoiceInputHandler | None = None
        self.text_input_handler: TextInputHandler | None = None
        self.text_values: list[str] = []

    def set_app_voice_input_handler(
        self,
        handler: AppVoiceInputHandler | None,
    ) -> None:
        self.app_voice_input_handler = handler

    def set_text_input_handler(self, handler: TextInputHandler | None) -> None:
        self.text_input_handler = handler

    def text_input_status(self) -> TextInputStatus:
        return TextInputStatus(active=False, mode=TextInputMode.MANUAL)

    async def connect(self) -> bool:
        self.connect_calls += 1
        return self.connected

    async def wake(self) -> bool:
        self.wake_calls += 1
        return True

    async def discover_mac_address(self) -> str | None:
        return self.discovered_mac_address

    async def send_command(self, command: str) -> None:
        self.commands.append(command)

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            supported_commands=frozenset(),
            power=CapabilityStatus.UNSUPPORTED,
            volume=CapabilityStatus.UNSUPPORTED,
            directional_navigation=CapabilityStatus.UNSUPPORTED,
            media_controls=CapabilityStatus.UNSUPPORTED,
            text_input=TextInputCapabilities(
                focus_detection=CapabilityStatus.UNSUPPORTED,
                send_text=CapabilityStatus.UNSUPPORTED,
                replace_text=CapabilityStatus.UNSUPPORTED,
                delete_text=CapabilityStatus.UNSUPPORTED,
                submit_text=CapabilityStatus.UNSUPPORTED,
            ),
            source_selection=CapabilityStatus.UNSUPPORTED,
            wake_on_lan=CapabilityStatus.UNSUPPORTED,
            pairing=CapabilityStatus.UNSUPPORTED,
            voice_input=VoiceInputCapabilities(
                remote_mic_stream=CapabilityStatus.UNSUPPORTED,
                native_voice_search=CapabilityStatus.UNSUPPORTED,
                app_voice_input=CapabilityStatus.UNSUPPORTED,
            ),
            connection_type="fake",
        )

    async def send_text(self, text: str) -> None:
        self.text_values.append(text)

    async def replace_text(self, text: str) -> None:
        self.text_values.append(text)

    async def delete_text(self, count: int = 1) -> None:
        self.text_values.append(f"delete:{count}")

    async def submit_text(self) -> None:
        self.text_values.append("submit")

    async def start_voice(self, mode: VoiceInputMode):
        self.voice_mode = mode
        self.voice_started = True
        return None

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
