import asyncio
import time
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
from src.infrastructure.tv.thread_bound_remote import ThreadBoundRemoteExecutor
from src.infrastructure.tv.tv_command_translation import (
    SAMSUNG_COMMANDS,
    translate_tv_command,
)
from src.infrastructure.tv.tv_remote import TV_ADAPTER_SAMSUNG
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


class SamsungTvRemoteClient:
    def __init__(
        self,
        config: AppConfig,
        wake_on_lan: WakeOnLanSender | None = None,
    ) -> None:
        self._config = config
        self._remote: Any | None = None
        self._logger = AppLogger()
        self._wake_on_lan = wake_on_lan or WakeOnLanSender(config, self._logger)
        self._executor = ThreadBoundRemoteExecutor("samsung-tv")
        self._text_input_handler: TextInputHandler | None = None
        self._text_input_status = TextInputStatus(
            active=False,
            mode=TextInputMode.AUTO_DETECTED,
        )

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            supported_commands=frozenset(SAMSUNG_COMMANDS),
            power=CapabilityStatus.IMPLEMENTED,
            volume=CapabilityStatus.IMPLEMENTED,
            directional_navigation=CapabilityStatus.IMPLEMENTED,
            media_controls=CapabilityStatus.IMPLEMENTED,
            text_input=TextInputCapabilities(
                focus_detection=CapabilityStatus.IMPLEMENTED,
                send_text=CapabilityStatus.IMPLEMENTED,
                replace_text=CapabilityStatus.UNSUPPORTED,
                delete_text=CapabilityStatus.IMPLEMENTED,
                submit_text=CapabilityStatus.IMPLEMENTED,
                notes=(
                    "Samsung websocket IME events are model and firmware "
                    "dependent; manual keyboard mode remains useful as a fallback.",
                ),
            ),
            source_selection=CapabilityStatus.NOT_IMPLEMENTED,
            wake_on_lan=CapabilityStatus.IMPLEMENTED,
            pairing=CapabilityStatus.IMPLEMENTED,
            voice_input=VoiceInputCapabilities(
                remote_mic_stream=CapabilityStatus.UNSUPPORTED,
                native_voice_search=CapabilityStatus.IMPLEMENTED,
                app_voice_input=CapabilityStatus.UNSUPPORTED,
                notes=(
                    "Samsung websocket control does not expose raw microphone "
                    "audio streaming.",
                    "Native voice UI is attempted with the KEY_VOICE remote key; "
                    "model support may vary.",
                ),
            ),
            connection_type="samsungtvws websocket",
            known_limitations=(
                "Power uses Samsung KEY_POWER toggle; wake-from-off support "
                "depends on the TV accepting websocket commands while asleep.",
                "Remote microphone streaming and source selection are not "
                "implemented.",
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
        return self._text_input_status

    async def connect(self) -> bool:
        try:
            await self._executor.call(self._connect_sync)
        except Exception as error:
            self._logger.error(
                f"Could not connect to Samsung TV at {self._config.tv.host}: {error}"
            )
            self._remote = None
            return False

        self._logger.info(f"Connected to Samsung TV at {self._config.tv.host}")
        return True

    async def wake(self) -> bool:
        try:
            result = await self._executor.call(self._wake_on_lan.wake)
        except Exception as error:
            self._logger.error(f"Samsung Wake-on-LAN failed: {error}")
            return False
        return result.attempted and result.sent_packets > 0

    async def discover_mac_address(self) -> str | None:
        if self._remote is None:
            return None
        try:
            return await self._executor.call(self._discover_mac_address_sync)
        except Exception as error:
            self._logger.debug(f"Samsung MAC discovery failed: {error}")
            return None

    async def send_command(self, command: str) -> None:
        if self._remote is None:
            if not await self._wake_and_connect():
                self._logger.info(f"TV not connected. Skipping command: {command}")
                return

        adapter_command = translate_tv_command(TV_ADAPTER_SAMSUNG, command)
        try:
            await self._executor.call(self._send_key_sync, adapter_command)
            self._dismiss_text_input_for_command(command)
        except Exception as error:
            self._logger.debug(
                f"Samsung TV command {adapter_command} failed, reconnecting: {error}"
            )
            try:
                await self._executor.call(self._close_sync, True)
                if not await self._wake_and_connect():
                    self._logger.info(f"TV not connected. Skipping command: {command}")
                    return
                await self._executor.call(self._send_key_sync, adapter_command)
                self._dismiss_text_input_for_command(command)
            except Exception as retry_error:
                self._logger.error(
                    f"Samsung TV command {adapter_command} failed: {retry_error}"
                )

    async def send_text(self, text: str) -> None:
        if self._remote is None and not await self._wake_and_connect():
            self._logger.info("TV not connected. Skipping Samsung text input.")
            return
        try:
            await self._executor.call(self._send_text_sync, text)
        except Exception as error:
            self._logger.error(f"Samsung text input failed: {error}")

    async def replace_text(self, text: str) -> None:
        del text
        self._logger.info("Samsung text replacement is not supported.")

    async def delete_text(self, count: int = 1) -> None:
        for _ in range(count):
            await self._executor.call(self._send_key_sync, "KEY_BACKSPACE")

    async def submit_text(self) -> None:
        if self._remote is None:
            return
        try:
            await self._executor.call(self._submit_text_sync)
        except Exception as error:
            self._logger.error(f"Samsung text submit failed: {error}")

    async def start_voice(self, mode: VoiceInputMode):
        if mode == VoiceInputMode.NATIVE_VOICE_SEARCH:
            if self._remote is None:
                self._logger.info("TV not connected. Skipping Samsung voice input.")
                return None
            try:
                await self._executor.call(self._send_key_sync, "KEY_VOICE")
            except Exception as error:
                self._logger.error(f"Samsung native voice input failed: {error}")
            return None
        self._logger.info(f"Samsung voice input mode is not supported: {mode.value}")
        return None

    async def disconnect(self) -> None:
        try:
            await self._executor.call(self._close_sync)
        finally:
            self._executor.shutdown()

    def _connect_sync(self) -> None:
        from samsungtvws import SamsungTVWS

        self._config.tv.samsung_token_file.parent.mkdir(parents=True, exist_ok=True)
        remote = SamsungTVWS(
            host=self._config.tv.host,
            port=self._config.tv.samsung_port,
            token_file=str(self._config.tv.samsung_token_file),
            name=self._config.app_name,
        )
        remote.open()
        self._attach_text_input_events(remote)
        self._remote = remote

    def _send_key_sync(self, adapter_command: str) -> None:
        if self._remote is None:
            raise RuntimeError("Samsung TV is not connected")
        self._remote.send_key(adapter_command)

    def _send_text_sync(self, text: str) -> None:
        if self._remote is None:
            raise RuntimeError("Samsung TV is not connected")
        self._remote.send_text(text)

    def _submit_text_sync(self) -> None:
        if self._remote is None:
            raise RuntimeError("Samsung TV is not connected")
        end_text = getattr(self._remote, "end_text", None)
        if end_text is not None:
            end_text()
            return
        self._remote.send_key("KEY_ENTER")

    def _attach_text_input_events(self, remote: Any) -> None:
        original = getattr(remote, "_websocket_event", None)
        if original is None:
            return

        def handle_event(event: str, response: dict[str, Any]) -> None:
            original(event, response)
            if event == "ms.remote.imeStart":
                self._record_text_input_status(True)
            elif event == "ms.remote.imeEnd":
                self._record_text_input_status(False)

        remote._websocket_event = handle_event

    def _record_text_input_status(self, active: bool) -> None:
        self._text_input_status = TextInputStatus(
            active=active,
            mode=TextInputMode.AUTO_DETECTED,
        )
        if self._text_input_handler is not None:
            self._text_input_handler(self._text_input_status)

    def _dismiss_text_input_for_command(self, command: str) -> None:
        if command in _TEXT_DISMISS_COMMANDS:
            self._record_text_input_status(False)

    def _discover_mac_address_sync(self) -> str | None:
        if self._remote is None:
            return None
        rest_device_info = getattr(self._remote, "rest_device_info", None)
        if rest_device_info is None:
            return None
        info = rest_device_info()
        device_info = info.get("device", {}) if isinstance(info, dict) else {}
        if not isinstance(device_info, dict):
            return None
        network_type = str(device_info.get("networkType", "")).strip().lower()
        wifi_mac = normalize_mac_address(str(device_info.get("wifiMac", "")))
        if wifi_mac is None:
            return None
        if network_type == "wired":
            self._logger.info(
                "Samsung reported only a Wi-Fi MAC address while the TV is using "
                "wired networking. Saving it as the Wake-on-LAN candidate; "
                "wake success depends on the TV model and network standby settings."
            )
        return wifi_mac

    async def _wake_and_connect(self) -> bool:
        await self.wake()
        deadline = time.monotonic() + self._config.tv.wake_connect_timeout_seconds
        while True:
            if await self.connect():
                return True

            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                return False

            retry_seconds = min(
                self._config.tv.wake_connect_retry_seconds,
                remaining_seconds,
            )
            if retry_seconds > 0:
                await asyncio.sleep(retry_seconds)

    def _reconnect_sync(self) -> None:
        self._close_sync(ignore_errors=True)
        self._connect_sync()

    def _close_sync(self, ignore_errors: bool = False) -> None:
        try:
            if self._remote is not None and hasattr(self._remote, "close"):
                self._remote.close()
        except Exception:
            if not ignore_errors:
                raise
        finally:
            self._remote = None
