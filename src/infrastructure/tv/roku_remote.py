from typing import Any

from src.application.ports.tv_remote import (
    AppVoiceInputHandler,
    CapabilityStatus,
    TvAdapterCapabilities,
    VoiceInputCapabilities,
    VoiceInputMode,
)
from src.infrastructure.tv.thread_bound_remote import ThreadBoundRemoteExecutor
from src.infrastructure.tv.tv_command_translation import (
    ROKU_COMMANDS,
    translate_tv_command,
)
from src.infrastructure.tv.tv_remote import TV_ADAPTER_ROKU
from src.infrastructure.tv.wake_on_lan import WakeOnLanSender, normalize_mac_address
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class RokuRemoteClient:
    def __init__(
        self,
        config: AppConfig,
        wake_on_lan: WakeOnLanSender | None = None,
    ) -> None:
        self._config = config
        self._remote: Any | None = None
        self._logger = AppLogger()
        self._wake_on_lan = wake_on_lan or WakeOnLanSender(config, self._logger)
        self._executor = ThreadBoundRemoteExecutor("roku-tv")

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            supported_commands=frozenset(ROKU_COMMANDS),
            power=CapabilityStatus.IMPLEMENTED,
            volume=CapabilityStatus.IMPLEMENTED,
            directional_navigation=CapabilityStatus.IMPLEMENTED,
            media_controls=CapabilityStatus.IMPLEMENTED,
            text_input=CapabilityStatus.NOT_IMPLEMENTED,
            source_selection=CapabilityStatus.NOT_IMPLEMENTED,
            wake_on_lan=CapabilityStatus.IMPLEMENTED,
            pairing=CapabilityStatus.UNSUPPORTED,
            voice_input=VoiceInputCapabilities(
                remote_mic_stream=CapabilityStatus.UNSUPPORTED,
                native_voice_search=CapabilityStatus.IMPLEMENTED,
                app_voice_input=CapabilityStatus.UNSUPPORTED,
                app_text_input=CapabilityStatus.NOT_IMPLEMENTED,
                notes=(
                    "Roku ECP exposes a Search key that opens the Roku voice "
                    "heads-up display.",
                    "ECP does not expose raw microphone audio upload.",
                ),
            ),
            connection_type="Roku ECP HTTP",
            known_limitations=(
                "PowerOff is available on Roku TV devices; standalone Roku "
                "streaming players may not support TV power control.",
                "Wake-on-LAN uses Roku device-info MAC data when available; "
                "model and Fast TV Start support vary.",
                "Remote microphone streaming, pairing, text input, and source "
                "selection are not implemented.",
            ),
        )

    def set_app_voice_input_handler(
        self,
        handler: AppVoiceInputHandler | None,
    ) -> None:
        del handler

    async def connect(self) -> bool:
        try:
            await self._executor.call(self._connect_sync)
        except Exception as error:
            self._logger.error(
                f"Could not connect to Roku at {self._config.tv.host}: {error}"
            )
            self._remote = None
            return False

        self._logger.info(f"Connected to Roku at {self._config.tv.host}")
        return True

    async def wake(self) -> bool:
        try:
            result = await self._executor.call(self._wake_on_lan.wake)
        except Exception as error:
            self._logger.error(f"Roku Wake-on-LAN failed: {error}")
            return False
        return result.attempted and result.sent_packets > 0

    async def discover_mac_address(self) -> str | None:
        if self._remote is None:
            return None
        try:
            update = getattr(self._remote, "update", None)
            if update is None:
                return None
            device = await self._executor.call(update)
            return _mac_address_from_roku_device(device)
        except Exception as error:
            self._logger.debug(f"Roku MAC discovery failed: {error}")
            return None

    async def send_command(self, command: str) -> None:
        if self._remote is None:
            self._logger.info(f"TV not connected. Skipping command: {command}")
            return

        adapter_command = translate_tv_command(TV_ADAPTER_ROKU, command)
        try:
            await self._executor.call(self._send_key_sync, adapter_command)
        except Exception as error:
            self._logger.debug(
                f"Roku command {adapter_command} failed, reconnecting: {error}"
            )
            try:
                await self._executor.call(self._reconnect_sync)
                await self._executor.call(self._send_key_sync, adapter_command)
            except Exception as retry_error:
                self._logger.error(
                    f"Roku command {adapter_command} failed: {retry_error}"
                )

    async def start_voice(self, mode: VoiceInputMode):
        if mode == VoiceInputMode.NATIVE_VOICE_SEARCH:
            if self._remote is None:
                self._logger.info("TV not connected. Skipping Roku voice input.")
                return None
            try:
                await self._executor.call(self._send_key_sync, "Search")
            except Exception as error:
                self._logger.error(f"Roku native voice input failed: {error}")
            return None
        self._logger.info(f"Roku voice input mode is not supported: {mode.value}")
        return None

    async def disconnect(self) -> None:
        try:
            await self._executor.call(self._close_sync)
        finally:
            self._executor.shutdown()

    def _connect_sync(self) -> None:
        from rokuecp import Roku

        self._remote = Roku(
            self._config.tv.host,
            port=self._config.tv.roku_port,
        )

    def _send_key_sync(self, adapter_command: str) -> None:
        if self._remote is None:
            raise RuntimeError("Roku is not connected")

        keypress = getattr(self._remote, "keypress", None)
        if keypress is not None:
            keypress(adapter_command)
        else:
            self._remote.remote(adapter_command)

    def _reconnect_sync(self) -> None:
        self._close_sync(ignore_errors=True)
        self._connect_sync()

    def _close_sync(self, ignore_errors: bool = False) -> None:
        try:
            close = getattr(self._remote, "close", None)
            if close is not None:
                close()
        except Exception:
            if not ignore_errors:
                raise
        finally:
            self._remote = None


def _mac_address_from_roku_device(device: Any) -> str | None:
    info = getattr(device, "info", None)
    network_type = str(getattr(info, "network_type", "") or "").lower()
    if network_type == "ethernet":
        return normalize_mac_address(str(getattr(info, "ethernet_mac", "") or ""))
    if network_type in {"wifi", "wireless"}:
        return normalize_mac_address(str(getattr(info, "wifi_mac", "") or ""))
    return normalize_mac_address(str(getattr(info, "ethernet_mac", "") or "")) or (
        normalize_mac_address(str(getattr(info, "wifi_mac", "") or ""))
    )
