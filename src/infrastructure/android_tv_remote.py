from androidtvremote2 import AndroidTVRemote, CannotConnect, ConnectionClosed, InvalidAuth

from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class AndroidTvRemoteClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._remote: AndroidTVRemote | None = None
        self._logger = AppLogger()

    async def connect(self) -> bool:
        self._config.cert_file.parent.mkdir(parents=True, exist_ok=True)
        remote = AndroidTVRemote(
            self._config.app_name,
            str(self._config.cert_file),
            str(self._config.key_file),
            self._config.tv_ip,
            enable_voice=True,
        )

        if await remote.async_generate_cert_if_missing():
            self._logger.info(
                f"Generated {self._config.cert_file} and {self._config.key_file}"
            )

        try:
            await remote.async_connect()
        except InvalidAuth:
            self._logger.info("TV needs pairing before commands can be sent.")
            self._logger.info("Starting pairing. Enter the code shown on your TV.")
            try:
                await remote.async_start_pairing()
                pairing_code = input("Pairing code: ").strip()
                await remote.async_finish_pairing(pairing_code)
                await remote.async_connect()
            except (CannotConnect, ConnectionClosed, InvalidAuth) as error:
                self._logger.error(f"Pairing failed: {error}")
                return False
        except (CannotConnect, ConnectionClosed) as error:
            self._logger.error(f"Could not connect to TV at {self._config.tv_ip}: {error}")
            return False

        self._remote = remote
        self._logger.info(f"Connected to TV at {self._config.tv_ip}")
        return True

    def send_key_command(self, command: str) -> None:
        if self._remote is None:
            self._logger.info(f"TV not connected. Skipping command: {command}")
            return

        try:
            self._remote.send_key_command(command)
        except ConnectionClosed:
            self._logger.error("TV connection closed. Command not sent.")
        except ValueError as error:
            self._logger.error(f"Invalid TV command {command}: {error}")

    async def start_voice(self):
        if self._remote is None:
            return None
        return await self._remote.start_voice()

    def disconnect(self) -> None:
        if self._remote is not None:
            self._remote.disconnect()
