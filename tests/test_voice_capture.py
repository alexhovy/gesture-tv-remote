import asyncio
import unittest

from src.infrastructure.audio.voice_capture import MicrophoneVoiceCapture
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
        service = MicrophoneVoiceCapture(remote, app_config(), FakeLogger())

        asyncio.run(service.capture())

        self.assertTrue(remote.started_voice)


class FakeLogger:
    def info(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass

    def debug(self, message: str) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
