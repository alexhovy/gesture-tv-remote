import asyncio
import unittest

from src.services.voice_capture import VoiceCaptureService
from tests.config_helpers import app_config


class UnsupportedVoiceRemote:
    def __init__(self) -> None:
        self.started_voice = False

    async def connect(self) -> bool:
        return True

    async def send_key_command(self, command: str) -> None:
        pass

    async def start_voice(self):
        self.started_voice = True
        return None

    async def disconnect(self) -> None:
        pass


class VoiceCaptureTests(unittest.TestCase):
    def test_unsupported_voice_returns_without_microphone_dependency(self) -> None:
        remote = UnsupportedVoiceRemote()
        service = VoiceCaptureService(remote, app_config())

        asyncio.run(service.capture())

        self.assertTrue(remote.started_voice)


if __name__ == "__main__":
    unittest.main()
