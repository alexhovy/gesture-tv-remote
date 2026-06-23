from src.application.ports.tv_remote import CapabilityStatus, TvAdapterCapabilities
from src.infrastructure.tv.thread_bound_remote import ThreadBoundRemoteExecutor
from src.infrastructure.tv.tv_command_translation import translate_tv_command
from src.infrastructure.tv.tv_remote import TV_ADAPTER_SAMSUNG
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class SamsungTvRemoteClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._remote = None
        self._logger = AppLogger()
        self._executor = ThreadBoundRemoteExecutor("samsung-tv")

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            power=CapabilityStatus.NOT_IMPLEMENTED,
            volume=CapabilityStatus.IMPLEMENTED,
            directional_navigation=CapabilityStatus.IMPLEMENTED,
            media_controls=CapabilityStatus.NOT_IMPLEMENTED,
            text_input=CapabilityStatus.NOT_IMPLEMENTED,
            source_selection=CapabilityStatus.NOT_IMPLEMENTED,
            wake_on_lan=CapabilityStatus.NOT_IMPLEMENTED,
            pairing=CapabilityStatus.IMPLEMENTED,
            voice_capture=CapabilityStatus.UNSUPPORTED,
            connection_type="samsungtvws websocket",
            known_limitations=(
                "Only key commands are implemented.",
                "Voice capture, text input, source selection, and Wake-on-LAN "
                "are not implemented.",
            ),
        )

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

    async def send_command(self, command: str) -> None:
        if self._remote is None:
            self._logger.info(f"TV not connected. Skipping command: {command}")
            return

        adapter_command = translate_tv_command(TV_ADAPTER_SAMSUNG, command)
        try:
            await self._executor.call(self._send_key_sync, adapter_command)
        except Exception as error:
            self._logger.debug(
                f"Samsung TV command {adapter_command} failed, reconnecting: {error}"
            )
            try:
                await self._executor.call(self._reconnect_sync)
                await self._executor.call(self._send_key_sync, adapter_command)
            except Exception as retry_error:
                self._logger.error(
                    f"Samsung TV command {adapter_command} failed: {retry_error}"
                )

    async def start_voice(self):
        self._logger.info("Voice capture is not supported for Samsung TV.")
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
        self._remote = remote

    def _send_key_sync(self, adapter_command: str) -> None:
        if self._remote is None:
            raise RuntimeError("Samsung TV is not connected")
        self._remote.send_key(adapter_command)

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
