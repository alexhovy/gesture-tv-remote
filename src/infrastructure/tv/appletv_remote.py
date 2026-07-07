import asyncio
from typing import Any

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
from src.domain.constants import (
    TV_COMMAND_BACK,
    TV_COMMAND_HOME,
    TV_COMMAND_POWER_OFF,
    TV_COMMAND_POWER_ON,
    TV_COMMAND_POWER_TOGGLE,
)
from src.infrastructure.tv.tv_command_translation import (
    APPLETV_COMMANDS,
    translate_tv_command,
)
from src.infrastructure.tv.tv_remote import TV_ADAPTER_APPLETV
from src.infrastructure.tv.wake_on_lan import WakeOnLanSender, normalize_mac_address
from src.shared.config import AppConfig
from src.shared.logging import AppLogger

_TEXT_DISMISS_COMMANDS = frozenset(
    {
        TV_COMMAND_BACK,
        TV_COMMAND_HOME,
        TV_COMMAND_POWER_OFF,
        TV_COMMAND_POWER_ON,
        TV_COMMAND_POWER_TOGGLE,
    }
)


class AppleTvRemoteClient:
    def __init__(
        self,
        config: AppConfig,
        wake_on_lan: WakeOnLanSender | None = None,
    ) -> None:
        self._config = config
        self._remote: Any | None = None
        self._device_config: Any | None = None
        self._storage: Any | None = None
        self._logger = AppLogger()
        self._wake_on_lan = wake_on_lan or WakeOnLanSender(config, self._logger)
        self._text_input_handler: TextInputHandler | None = None
        self._text_input_status = TextInputStatus(
            active=False,
            mode=TextInputMode.AUTO_DETECTED,
        )

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            supported_commands=frozenset(APPLETV_COMMANDS),
            power=CapabilityStatus.IMPLEMENTED,
            volume=CapabilityStatus.IMPLEMENTED,
            directional_navigation=CapabilityStatus.IMPLEMENTED,
            media_controls=CapabilityStatus.IMPLEMENTED,
            text_input=TextInputCapabilities(
                focus_detection=CapabilityStatus.IMPLEMENTED,
                send_text=CapabilityStatus.IMPLEMENTED,
                replace_text=CapabilityStatus.IMPLEMENTED,
                delete_text=CapabilityStatus.IMPLEMENTED,
                submit_text=CapabilityStatus.IMPLEMENTED,
                notes=(
                    "Apple TV text input uses pyatv's Companion keyboard "
                    "interface when the connected device advertises it.",
                ),
            ),
            source_selection=CapabilityStatus.UNSUPPORTED,
            wake_on_lan=CapabilityStatus.IMPLEMENTED,
            pairing=CapabilityStatus.IMPLEMENTED,
            voice_input=VoiceInputCapabilities(
                remote_mic_stream=CapabilityStatus.UNSUPPORTED,
                native_voice_search=CapabilityStatus.UNSUPPORTED,
                app_voice_input=CapabilityStatus.UNSUPPORTED,
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
                "Wake-on-LAN sends a generic magic packet when a MAC address is "
                "configured, then pyatv power management can turn on connected "
                "tvOS devices.",
                "App launching and touch gestures are not mapped.",
            ),
        )

    def set_app_voice_input_handler(
        self,
        handler: AppVoiceInputHandler | None,
    ) -> None:
        del handler

    def set_text_input_handler(self, handler: TextInputHandler | None) -> None:
        self._text_input_handler = handler

    def text_input_status(self) -> TextInputStatus:
        if self._remote is None:
            return self._text_input_status
        try:
            keyboard = getattr(self._remote, "keyboard", None)
            focus_state = getattr(keyboard, "text_focus_state", None)
        except Exception as error:
            self._logger.debug(f"Apple TV keyboard status failed: {error}")
            return self._text_input_status
        active = str(focus_state).endswith(".Focused") or str(focus_state) == "Focused"
        self._text_input_status = TextInputStatus(
            active=active,
            mode=TextInputMode.AUTO_DETECTED,
        )
        return self._text_input_status

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

            self._device_config = devices[0]
            self._remote = await pyatv.connect(
                self._device_config, loop, storage=storage
            )
            keyboard = getattr(self._remote, "keyboard", None)
            if keyboard is not None:
                keyboard.listener = _AppleTvKeyboardListener(self)
            self._storage = storage
            await storage.save()
        except Exception as error:
            self._logger.error(
                f"Could not connect to Apple TV at {self._config.tv.host}: {error}"
            )
            self._remote = None
            self._device_config = None
            self._storage = None
            return False

        self._logger.info(f"Connected to Apple TV at {self._config.tv.host}")
        return True

    async def wake(self) -> bool:
        try:
            result = await asyncio.to_thread(self._wake_on_lan.wake)
        except Exception as error:
            self._logger.error(f"Apple TV Wake-on-LAN failed: {error}")
            return False
        if result.attempted and result.sent_packets > 0:
            return True
        if self._remote is None:
            return False
        try:
            await self._remote.power.turn_on()
        except Exception as error:
            self._logger.error(f"Apple TV wake failed: {error}")
            return False
        return True

    async def discover_mac_address(self) -> str | None:
        if self._device_config is None:
            return None
        device_info = getattr(self._device_config, "device_info", None)
        mac_address = normalize_mac_address(str(getattr(device_info, "mac", "") or ""))
        if mac_address is not None:
            return mac_address
        identifiers: set[str] = getattr(self._device_config, "all_identifiers", set())
        for identifier in identifiers:
            mac_address = normalize_mac_address(str(identifier))
            if mac_address is not None:
                return mac_address
        return None

    async def send_command(self, command: str) -> None:
        if self._remote is None:
            self._logger.info(f"TV not connected. Skipping command: {command}")
            return

        adapter_command = translate_tv_command(TV_ADAPTER_APPLETV, command)
        try:
            if adapter_command in {"turn_on", "turn_off"}:
                await getattr(self._remote.power, adapter_command)()
                self._dismiss_text_input_for_command(command)
                return
            await getattr(self._remote.remote_control, adapter_command)()
            self._dismiss_text_input_for_command(command)
        except Exception as error:
            self._logger.error(f"Apple TV command {adapter_command} failed: {error}")

    async def send_text(self, text: str) -> None:
        keyboard = self._keyboard()
        if keyboard is None:
            return
        try:
            await keyboard.text_append(text)
        except Exception as error:
            self._logger.error(f"Apple TV text input failed: {error}")

    async def replace_text(self, text: str) -> None:
        keyboard = self._keyboard()
        if keyboard is None:
            return
        try:
            await keyboard.text_set(text)
        except Exception as error:
            self._logger.error(f"Apple TV text replacement failed: {error}")

    async def delete_text(self, count: int = 1) -> None:
        keyboard = self._keyboard()
        if keyboard is None:
            return
        try:
            current = await keyboard.text_get()
            await keyboard.text_set((current or "")[:-count])
        except Exception as error:
            self._logger.error(f"Apple TV text deletion failed: {error}")

    async def submit_text(self) -> None:
        await self.send_command("DPAD_CENTER")

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
        self._device_config = None

    def _keyboard(self) -> Any | None:
        if self._remote is None:
            self._logger.info("TV not connected. Skipping Apple TV text input.")
            return None
        return getattr(self._remote, "keyboard", None)

    def _record_keyboard_focus(self, active: bool) -> None:
        self._text_input_status = TextInputStatus(
            active=active,
            mode=TextInputMode.AUTO_DETECTED,
        )
        if self._text_input_handler is not None:
            self._text_input_handler(self._text_input_status)

    def _dismiss_text_input_for_command(self, command: str) -> None:
        if command in _TEXT_DISMISS_COMMANDS:
            self._record_keyboard_focus(False)


class _AppleTvKeyboardListener:
    def __init__(self, client: AppleTvRemoteClient) -> None:
        self._client = client

    def focusstate_update(self, old_state: Any, new_state: Any) -> None:
        del old_state
        active = str(new_state).endswith(".Focused") or str(new_state) == "Focused"
        self._client._record_keyboard_focus(active)
