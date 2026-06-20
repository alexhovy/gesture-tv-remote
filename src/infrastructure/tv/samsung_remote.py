from src.infrastructure.tv.async_call import call_remote_method
from src.infrastructure.tv.tv_command_translation import translate_tv_command
from src.infrastructure.tv.tv_remote import TV_ADAPTER_SAMSUNG
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class SamsungTvRemoteClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._remote = None
        self._logger = AppLogger()

    async def connect(self) -> bool:
        try:
            from samsungtvws import SamsungTVWS

            self._config.samsung_token_file.parent.mkdir(parents=True, exist_ok=True)
            self._remote = SamsungTVWS(
                host=self._config.tv_host,
                port=self._config.samsung_port,
                token_file=str(self._config.samsung_token_file),
                name=self._config.app_name,
            )
            self._remote.open()
        except Exception as error:
            self._logger.error(
                f"Could not connect to Samsung TV at {self._config.tv_host}: {error}"
            )
            self._remote = None
            return False

        self._logger.info(f"Connected to Samsung TV at {self._config.tv_host}")
        return True

    async def send_key_command(self, command: str) -> None:
        if self._remote is None:
            self._logger.info(f"TV not connected. Skipping command: {command}")
            return

        adapter_command = translate_tv_command(TV_ADAPTER_SAMSUNG, command)
        try:
            await call_remote_method(self._remote.send_key, adapter_command)
        except Exception as error:
            self._logger.error(f"Samsung TV command {adapter_command} failed: {error}")

    async def start_voice(self):
        self._logger.info("Voice capture is not supported for Samsung TV.")
        return None

    def disconnect(self) -> None:
        if self._remote is not None and hasattr(self._remote, "close"):
            self._remote.close()
