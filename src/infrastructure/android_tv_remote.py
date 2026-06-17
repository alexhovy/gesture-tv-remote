from androidtvremote2 import AndroidTVRemote, CannotConnect, ConnectionClosed, InvalidAuth

from src.shared.config import AppConfig


class AndroidTvRemoteClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._remote: AndroidTVRemote | None = None

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
            print(f"Generated {self._config.cert_file} and {self._config.key_file}")

        try:
            await remote.async_connect()
        except InvalidAuth:
            print("TV needs pairing before commands can be sent.")
            print("Starting pairing. Enter the code shown on your TV.")
            try:
                await remote.async_start_pairing()
                pairing_code = input("Pairing code: ").strip()
                await remote.async_finish_pairing(pairing_code)
                await remote.async_connect()
            except (CannotConnect, ConnectionClosed, InvalidAuth) as error:
                print(f"Pairing failed: {error}")
                return False
        except (CannotConnect, ConnectionClosed) as error:
            print(f"Could not connect to TV at {self._config.tv_ip}: {error}")
            return False

        self._remote = remote
        print(f"Connected to TV at {self._config.tv_ip}")
        return True

    def send_key_command(self, command: str) -> None:
        if self._remote is None:
            print(f"TV not connected. Skipping command: {command}")
            return

        try:
            self._remote.send_key_command(command)
        except ConnectionClosed:
            print("TV connection closed. Command not sent.")
        except ValueError as error:
            print(f"Invalid TV command {command}: {error}")

    async def start_voice(self):
        if self._remote is None:
            return None
        return await self._remote.start_voice()

    def disconnect(self) -> None:
        if self._remote is not None:
            self._remote.disconnect()

