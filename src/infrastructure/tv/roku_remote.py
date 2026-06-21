from src.infrastructure.tv.thread_bound_remote import ThreadBoundRemoteExecutor
from src.infrastructure.tv.tv_command_translation import translate_tv_command
from src.infrastructure.tv.tv_remote import (
    TV_ADAPTER_ROKU,
    CapabilityStatus,
    TvAdapterCapabilities,
)
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class RokuRemoteClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._remote = None
        self._logger = AppLogger()
        self._executor = ThreadBoundRemoteExecutor("roku-tv")

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            power=CapabilityStatus.NOT_IMPLEMENTED,
            volume=CapabilityStatus.IMPLEMENTED,
            directional_navigation=CapabilityStatus.IMPLEMENTED,
            media_controls=CapabilityStatus.NOT_IMPLEMENTED,
            text_input=CapabilityStatus.NOT_IMPLEMENTED,
            source_selection=CapabilityStatus.NOT_IMPLEMENTED,
            wake_on_lan=CapabilityStatus.UNSUPPORTED,
            pairing=CapabilityStatus.UNSUPPORTED,
            voice_capture=CapabilityStatus.UNSUPPORTED,
            connection_type="Roku ECP HTTP",
            known_limitations=(
                "Only ECP keypress commands are implemented.",
                "Voice capture, pairing, text input, source selection, and Wake-on-LAN are not implemented.",
            ),
        )

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

    async def send_key_command(self, command: str) -> None:
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

    async def start_voice(self):
        self._logger.info("Voice capture is not supported for Roku.")
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
