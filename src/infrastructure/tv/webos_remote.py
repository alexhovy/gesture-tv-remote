import re
from typing import Any

from src.application.ports.tv_remote import (
    AppVoiceInputHandler,
    CapabilityStatus,
    TvAdapterCapabilities,
    VoiceInputCapabilities,
    VoiceInputMode,
)
from src.infrastructure.tv.async_call import call_remote_method
from src.infrastructure.tv.tv_command_translation import (
    WEBOS_COMMANDS,
    translate_tv_command,
)
from src.infrastructure.tv.tv_remote import TV_ADAPTER_WEBOS
from src.infrastructure.tv.wake_on_lan import WakeOnLanSender, normalize_mac_address
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class WebOsRemoteClient:
    def __init__(
        self,
        config: AppConfig,
        wake_on_lan: WakeOnLanSender | None = None,
    ) -> None:
        self._config = config
        self._client: Any | None = None
        self._input: Any | None = None
        self._media: Any | None = None
        self._logger = AppLogger()
        self._wake_on_lan = wake_on_lan or WakeOnLanSender(config, self._logger)

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            supported_commands=frozenset(WEBOS_COMMANDS),
            power=CapabilityStatus.NOT_IMPLEMENTED,
            volume=CapabilityStatus.IMPLEMENTED,
            directional_navigation=CapabilityStatus.IMPLEMENTED,
            media_controls=CapabilityStatus.NOT_IMPLEMENTED,
            text_input=CapabilityStatus.NOT_IMPLEMENTED,
            source_selection=CapabilityStatus.NOT_IMPLEMENTED,
            wake_on_lan=CapabilityStatus.IMPLEMENTED,
            pairing=CapabilityStatus.IMPLEMENTED,
            voice_input=VoiceInputCapabilities(
                remote_mic_stream=CapabilityStatus.UNSUPPORTED,
                native_voice_search=CapabilityStatus.UNSUPPORTED,
                app_voice_input=CapabilityStatus.UNSUPPORTED,
                app_text_input=CapabilityStatus.NOT_IMPLEMENTED,
                notes=(
                    "webOS SSAP/input-control does not expose raw microphone "
                    "streaming.",
                    "Magic Remote and ThinQ voice paths are not exposed through "
                    "the current public adapter.",
                ),
            ),
            connection_type="aiowebostv websocket",
            known_limitations=(
                "Only input-control navigation and volume commands are implemented.",
                "Voice input, text input, and source selection are not implemented.",
            ),
        )

    def set_app_voice_input_handler(
        self,
        handler: AppVoiceInputHandler | None,
    ) -> None:
        del handler

    async def connect(self) -> bool:
        try:
            from aiowebostv import WebOsClient
            from aiowebostv.controls import InputControl, MediaControl

            self._config.tv.webos_client_key_file.parent.mkdir(
                parents=True, exist_ok=True
            )
            client_key = self._read_client_key()
            client: Any = WebOsClient(self._config.tv.host)
            await client.connect()

            registration_key = None
            async for status in client.register(client_key):
                registration_key = status.get("client-key", registration_key)

            if registration_key:
                self._write_client_key(registration_key)

            self._client = client
            self._input = await InputControl(client).connect_input()
            self._media = MediaControl(client)
        except Exception as error:
            self._logger.error(
                f"Could not connect to webOS TV at {self._config.tv.host}: {error}"
            )
            self._client = None
            self._input = None
            self._media = None
            return False

        self._logger.info(f"Connected to webOS TV at {self._config.tv.host}")
        return True

    async def wake(self) -> bool:
        try:
            result = await call_remote_method(self._wake_on_lan.wake)
        except Exception as error:
            self._logger.error(f"webOS Wake-on-LAN failed: {error}")
            return False
        return result.attempted and result.sent_packets > 0

    async def discover_mac_address(self) -> str | None:
        if self._client is None:
            return None
        for payload in await self._mac_discovery_payloads():
            mac_address = _mac_address_from_webos_payload(payload)
            if mac_address is not None:
                return mac_address
        return None

    async def send_command(self, command: str) -> None:
        if self._client is None:
            await self.wake()
            if not await self.connect():
                self._logger.info(f"TV not connected. Skipping command: {command}")
                return

        adapter_command = translate_tv_command(TV_ADAPTER_WEBOS, command)
        try:
            await self._send(adapter_command)
        except Exception as error:
            self._logger.debug(
                f"webOS TV command {adapter_command} failed, reconnecting: {error}"
            )
            self._client = None
            self._input = None
            self._media = None
            await self.wake()
            if await self.connect():
                try:
                    await self._send(adapter_command)
                    return
                except Exception as retry_error:
                    error = retry_error
            self._logger.error(f"webOS TV command {adapter_command} failed: {error}")

    async def start_voice(self, mode: VoiceInputMode):
        self._logger.info(f"webOS voice input mode is not supported: {mode.value}")
        return None

    async def disconnect(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            await call_remote_method(self._client.close)

    def _read_client_key(self) -> str | None:
        if not self._config.tv.webos_client_key_file.exists():
            return None
        return self._config.tv.webos_client_key_file.read_text(encoding="utf-8").strip()

    def _write_client_key(self, client_key: str) -> None:
        self._config.tv.webos_client_key_file.write_text(client_key, encoding="utf-8")

    async def _send(self, adapter_command: str) -> None:
        if adapter_command == "volume_up":
            if self._media is None:
                raise RuntimeError("webOS media control is not connected")
            await call_remote_method(self._media.volume_up)
            return
        if adapter_command == "volume_down":
            if self._media is None:
                raise RuntimeError("webOS media control is not connected")
            await call_remote_method(self._media.volume_down)
            return
        if self._input is None:
            raise RuntimeError("webOS input control is not connected")
        await call_remote_method(getattr(self._input, adapter_command))

    async def _mac_discovery_payloads(self) -> list[dict[str, Any]]:
        if self._client is None:
            return []
        payloads: list[dict[str, Any]] = []
        for endpoint in (
            "com.webos.service.connectionmanager/getinfo",
            "com.webos.service.connectionmanager/getStatus",
            "com.palm.connectionmanager/getStatus",
        ):
            try:
                payloads.append(
                    await call_remote_method(self._client.request, endpoint)
                )
            except Exception as error:
                self._logger.debug(f"webOS MAC discovery endpoint failed: {error}")

        for method in ("get_system_info", "get_software_info", "get_services"):
            try:
                payload = await call_remote_method(getattr(self._client, method))
            except Exception as error:
                self._logger.debug(f"webOS MAC discovery method failed: {error}")
                continue
            if isinstance(payload, dict):
                payloads.append(payload)
        return payloads


_MAC_KEY_PATTERN = re.compile(r"(?i)(^|[_-])mac([_-]?address)?$")


def _mac_address_from_webos_payload(payload: dict[str, Any]) -> str | None:
    for section_name in ("wired", "wifi", "wifiDirect"):
        section = payload.get(section_name)
        if not isinstance(section, dict):
            continue
        state = str(section.get("state") or section.get("status") or "").lower()
        if state and state not in {"connected", "online", "ready"}:
            continue
        mac_address = _find_mac_address(section)
        if mac_address is not None:
            return mac_address
    return _find_mac_address(payload)


def _find_mac_address(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _MAC_KEY_PATTERN.search(str(key)):
                mac_address = normalize_mac_address(str(item))
                if mac_address is not None:
                    return mac_address
        for item in value.values():
            mac_address = _find_mac_address(item)
            if mac_address is not None:
                return mac_address
    if isinstance(value, list | tuple):
        for item in value:
            mac_address = _find_mac_address(item)
            if mac_address is not None:
                return mac_address
    return None
