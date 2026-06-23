import asyncio

from src.infrastructure.tv.async_call import call_remote_method
from src.infrastructure.tv.tv_command_translation import translate_tv_command
from src.infrastructure.tv.tv_remote import (
    TV_ADAPTER_ANDROIDTV,
    CapabilityStatus,
    TvAdapterCapabilities,
)
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class AndroidTvRemoteClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._remote = None
        self._logger = AppLogger()

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            power=CapabilityStatus.NOT_IMPLEMENTED,
            volume=CapabilityStatus.IMPLEMENTED,
            directional_navigation=CapabilityStatus.IMPLEMENTED,
            media_controls=CapabilityStatus.NOT_IMPLEMENTED,
            text_input=CapabilityStatus.NOT_IMPLEMENTED,
            source_selection=CapabilityStatus.UNSUPPORTED,
            wake_on_lan=CapabilityStatus.UNSUPPORTED,
            pairing=CapabilityStatus.IMPLEMENTED,
            voice_capture=CapabilityStatus.IMPLEMENTED,
            connection_type="androidtvremote2 TLS remote protocol",
            known_limitations=(
                "Only key commands and voice capture are implemented.",
                "Power, text input, source selection, and media controls are not mapped.",
            ),
        )

    async def connect(self) -> bool:
        from androidtvremote2 import (
            AndroidTVRemote,
            CannotConnect,
            ConnectionClosed,
            InvalidAuth,
        )

        self._config.tv.android_cert_file.parent.mkdir(parents=True, exist_ok=True)
        remote = AndroidTVRemote(
            self._config.app_name,
            str(self._config.tv.android_cert_file),
            str(self._config.tv.android_key_file),
            self._config.tv.host,
            enable_voice=True,
        )

        if await remote.async_generate_cert_if_missing():
            self._logger.info(
                "Generated "
                f"{self._config.tv.android_cert_file} and {self._config.tv.android_key_file}"
            )

        try:
            await remote.async_connect()
        except InvalidAuth:
            self._logger.info("Android TV needs pairing before commands can be sent.")
            self._logger.info("Starting pairing. Enter the code shown on your TV.")
            try:
                await remote.async_start_pairing()
                pairing_code = await asyncio.to_thread(input, "Pairing code: ")
                pairing_code = pairing_code.strip()
                await remote.async_finish_pairing(pairing_code)
                await remote.async_connect()
            except (CannotConnect, ConnectionClosed, InvalidAuth) as error:
                self._logger.error(f"Android TV pairing failed: {error}")
                return False
        except (CannotConnect, ConnectionClosed) as error:
            self._logger.error(
                f"Could not connect to Android TV at {self._config.tv.host}: {error}"
            )
            return False

        self._remote = remote
        self._logger.info(f"Connected to Android TV at {self._config.tv.host}")
        return True

    async def send_command(self, command: str) -> None:
        if self._remote is None:
            self._logger.info(f"TV not connected. Skipping command: {command}")
            return

        from androidtvremote2 import ConnectionClosed

        adapter_command = translate_tv_command(TV_ADAPTER_ANDROIDTV, command)
        try:
            await call_remote_method(self._remote.send_key_command, adapter_command)
        except ConnectionClosed:
            self._logger.error("Android TV connection closed. Command not sent.")
        except ValueError as error:
            self._logger.error(f"Invalid Android TV command {adapter_command}: {error}")

    async def start_voice(self):
        if self._remote is None:
            return None
        return await self._remote.start_voice()

    async def disconnect(self) -> None:
        if self._remote is not None:
            await call_remote_method(self._remote.disconnect)
