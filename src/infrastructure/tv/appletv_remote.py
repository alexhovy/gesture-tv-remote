import asyncio
from typing import Any

from src.application.ports.tv_remote import (
    AppVoiceInputHandler,
    CapabilityStatus,
    TvAdapterCapabilities,
    VoiceInputCapabilities,
    VoiceInputMode,
)
from src.infrastructure.tv.tv_command_translation import (
    APPLETV_COMMANDS,
    translate_tv_command,
)
from src.infrastructure.tv.tv_remote import TV_ADAPTER_APPLETV
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class AppleTvRemoteClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._remote: Any | None = None
        self._storage: Any | None = None
        self._logger = AppLogger()

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            supported_commands=frozenset(APPLETV_COMMANDS),
            power=CapabilityStatus.IMPLEMENTED,
            volume=CapabilityStatus.IMPLEMENTED,
            directional_navigation=CapabilityStatus.IMPLEMENTED,
            media_controls=CapabilityStatus.IMPLEMENTED,
            text_input=CapabilityStatus.NOT_IMPLEMENTED,
            source_selection=CapabilityStatus.UNSUPPORTED,
            wake_on_lan=CapabilityStatus.UNSUPPORTED,
            pairing=CapabilityStatus.IMPLEMENTED,
            voice_input=VoiceInputCapabilities(
                remote_mic_stream=CapabilityStatus.UNSUPPORTED,
                native_voice_search=CapabilityStatus.UNSUPPORTED,
                app_voice_input=CapabilityStatus.UNSUPPORTED,
                app_text_input=CapabilityStatus.NOT_IMPLEMENTED,
                notes=(
                    "Apple TV control uses pyatv and requires paired credentials "
                    "in the configured pyatv storage file.",
                    "Siri microphone streaming is not exposed through this adapter.",
                ),
            ),
            connection_type="pyatv Media Remote Protocol",
            known_limitations=(
                "Pair Apple TV separately with atvremote wizard and the same "
                "storage file before using this adapter.",
                "Text input, app launching, and touch gestures are not mapped.",
            ),
        )

    def set_app_voice_input_handler(
        self,
        handler: AppVoiceInputHandler | None,
    ) -> None:
        del handler

    async def connect(self) -> bool:
        try:
            import pyatv
            from pyatv.storage.file_storage import FileStorage

            loop = asyncio.get_running_loop()
            self._config.tv.appletv_storage_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            storage = FileStorage(str(self._config.tv.appletv_storage_file), loop)
            await storage.load()

            devices = await pyatv.scan(
                loop,
                hosts=[self._config.tv.host],
                storage=storage,
            )
            if not devices:
                self._logger.error(
                    f"No Apple TV found at {self._config.tv.host}. "
                    "Check the host and local network discovery."
                )
                return False

            self._remote = await pyatv.connect(devices[0], loop, storage=storage)
            self._storage = storage
            await storage.save()
        except Exception as error:
            self._logger.error(
                f"Could not connect to Apple TV at {self._config.tv.host}: {error}"
            )
            self._remote = None
            self._storage = None
            return False

        self._logger.info(f"Connected to Apple TV at {self._config.tv.host}")
        return True

    async def send_command(self, command: str) -> None:
        if self._remote is None:
            self._logger.info(f"TV not connected. Skipping command: {command}")
            return

        adapter_command = translate_tv_command(TV_ADAPTER_APPLETV, command)
        try:
            if adapter_command in {"turn_on", "turn_off"}:
                await getattr(self._remote.power, adapter_command)()
                return
            await getattr(self._remote.remote_control, adapter_command)()
        except Exception as error:
            self._logger.error(f"Apple TV command {adapter_command} failed: {error}")

    async def start_voice(self, mode: VoiceInputMode):
        self._logger.info(f"Apple TV voice input mode is not supported: {mode.value}")
        return None

    async def disconnect(self) -> None:
        if self._remote is None:
            return
        pending_tasks = self._remote.close()
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)
        self._remote = None
