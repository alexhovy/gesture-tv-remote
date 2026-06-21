from src.infrastructure.tv.async_call import call_remote_method
from src.infrastructure.tv.tv_command_translation import translate_tv_command
from src.infrastructure.tv.tv_remote import TV_ADAPTER_WEBOS, TvAdapterCapabilities
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class WebOsRemoteClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client = None
        self._input = None
        self._media = None
        self._logger = AppLogger()

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            supports_power=False,
            supports_volume=True,
            supports_directional_navigation=True,
            supports_media_controls=False,
            supports_text_input=False,
            supports_source_selection=False,
            supports_wake_on_lan=False,
            supports_pairing=True,
            connection_type="aiowebostv websocket",
            known_limitations=(
                "Only input-control navigation and volume commands are implemented.",
                "Voice capture, text input, source selection, and Wake-on-LAN are not implemented.",
            ),
        )

    async def connect(self) -> bool:
        try:
            from aiowebostv import WebOsClient
            from aiowebostv.controls import InputControl, MediaControl

            self._config.tv.webos_client_key_file.parent.mkdir(parents=True, exist_ok=True)
            client_key = self._read_client_key()
            client = WebOsClient(self._config.tv.host)
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

    async def send_key_command(self, command: str) -> None:
        if self._client is None:
            self._logger.info(f"TV not connected. Skipping command: {command}")
            return

        adapter_command = translate_tv_command(TV_ADAPTER_WEBOS, command)
        try:
            await self._send(adapter_command)
        except Exception as error:
            self._logger.error(f"webOS TV command {adapter_command} failed: {error}")

    async def start_voice(self):
        self._logger.info("Voice capture is not supported for webOS TV.")
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
            await call_remote_method(self._media.volume_up)
            return
        if adapter_command == "volume_down":
            await call_remote_method(self._media.volume_down)
            return
        await call_remote_method(getattr(self._input, adapter_command))
