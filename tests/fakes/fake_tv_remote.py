from src.application.ports.tv_remote import (
    AppVoiceInputHandler,
    CapabilityStatus,
    TvAdapterCapabilities,
    VoiceInputCapabilities,
    VoiceInputMode,
)


class FakeTVRemote:
    def __init__(self, connected: bool = True) -> None:
        self.connected = connected
        self.commands: list[str] = []
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.voice_started = False
        self.app_voice_input_handler: AppVoiceInputHandler | None = None

    def set_app_voice_input_handler(
        self,
        handler: AppVoiceInputHandler | None,
    ) -> None:
        self.app_voice_input_handler = handler

    async def connect(self) -> bool:
        self.connect_calls += 1
        return self.connected

    async def send_command(self, command: str) -> None:
        self.commands.append(command)

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            power=CapabilityStatus.UNSUPPORTED,
            volume=CapabilityStatus.UNSUPPORTED,
            directional_navigation=CapabilityStatus.UNSUPPORTED,
            media_controls=CapabilityStatus.UNSUPPORTED,
            text_input=CapabilityStatus.UNSUPPORTED,
            source_selection=CapabilityStatus.UNSUPPORTED,
            wake_on_lan=CapabilityStatus.UNSUPPORTED,
            pairing=CapabilityStatus.UNSUPPORTED,
            voice_input=VoiceInputCapabilities(
                remote_mic_stream=CapabilityStatus.UNSUPPORTED,
                native_voice_search=CapabilityStatus.UNSUPPORTED,
                app_voice_input=CapabilityStatus.UNSUPPORTED,
                app_text_input=CapabilityStatus.UNSUPPORTED,
            ),
            connection_type="fake",
        )

    async def start_voice(self, mode: VoiceInputMode):
        self.voice_mode = mode
        self.voice_started = True
        return None

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
