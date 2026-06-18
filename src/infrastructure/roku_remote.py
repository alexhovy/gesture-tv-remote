from src.infrastructure.tv_command_translation import translate_tv_command
from src.infrastructure.tv_remote import TV_ADAPTER_ROKU
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class RokuRemoteClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._remote = None
        self._logger = AppLogger()

    async def connect(self) -> bool:
        try:
            from rokuecp import Roku

            self._remote = Roku(self._config.tv_host, port=self._config.roku_port)
        except Exception as error:
            self._logger.error(
                f"Could not connect to Roku at {self._config.tv_host}: {error}"
            )
            self._remote = None
            return False

        self._logger.info(f"Connected to Roku at {self._config.tv_host}")
        return True

    async def send_key_command(self, command: str) -> None:
        if self._remote is None:
            self._logger.info(f"TV not connected. Skipping command: {command}")
            return

        adapter_command = translate_tv_command(TV_ADAPTER_ROKU, command)
        try:
            keypress = getattr(self._remote, "keypress", None)
            if keypress is not None:
                result = keypress(adapter_command)
            else:
                result = self._remote.remote(adapter_command)
            if hasattr(result, "__await__"):
                await result
        except Exception as error:
            self._logger.error(f"Roku command {adapter_command} failed: {error}")

    async def start_voice(self):
        self._logger.info("Voice capture is not supported for Roku.")
        return None

    def disconnect(self) -> None:
        close = getattr(self._remote, "close", None)
        if close is not None:
            close()
