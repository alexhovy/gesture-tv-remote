class FakeTVRemote:
    def __init__(self, connected: bool = True) -> None:
        self.connected = connected
        self.commands: list[str] = []
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.voice_started = False

    async def connect(self) -> bool:
        self.connect_calls += 1
        return self.connected

    async def send_command(self, command: str) -> None:
        self.commands.append(command)

    async def start_voice(self):
        self.voice_started = True
        return None

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
