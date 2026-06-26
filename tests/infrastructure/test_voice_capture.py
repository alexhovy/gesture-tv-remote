import asyncio
import sys
import types
import unittest

from src.infrastructure.audio.voice_capture import MicrophoneVoiceCapture
from tests.helpers.config_helpers import app_config


class UnsupportedVoiceRemote:
    def __init__(self) -> None:
        self.started_voice = False

    async def connect(self) -> bool:
        return True

    async def send_command(self, command: str) -> None:
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

    def test_voice_capture_logs_sent_audio_chunks(self) -> None:
        remote = SupportedVoiceRemote()
        logger = FakeLogger()
        service = MicrophoneVoiceCapture(
            remote,
            app_config(voice_capture_seconds=0.01),
            logger,
        )
        sounddevice = types.ModuleType("sounddevice")
        sounddevice.RawInputStream = FakeRawInputStream

        previous = sys.modules.get("sounddevice")
        sys.modules["sounddevice"] = sounddevice
        try:
            asyncio.run(service.capture())
        finally:
            if previous is None:
                sys.modules.pop("sounddevice", None)
            else:
                sys.modules["sounddevice"] = previous

        self.assertEqual(remote.voice_stream.chunks, [b"1" * 16384])
        self.assertTrue(remote.voice_stream.ended)
        self.assertIn(
            "Microphone: finished. sent_chunks=1 sent_bytes=16384 "
            "max_abs_sample=12593 nonzero_samples=8192",
            logger.messages,
        )

class FakeLogger:
    def __init__(self) -> None:
        self.messages = []

    def info(self, message: str) -> None:
        self.messages.append(message)

    def error(self, message: str) -> None:
        self.messages.append(message)

    def debug(self, message: str) -> None:
        self.messages.append(message)


class SupportedVoiceRemote:
    def __init__(self) -> None:
        self.voice_stream = FakeVoiceStream()

    async def start_voice(self):
        return self.voice_stream


class FakeVoiceStream:
    def __init__(self) -> None:
        self.chunks = []
        self.ended = False

    def send_chunk(self, chunk: bytes) -> bool:
        self.chunks.append(chunk)
        return True

    def end(self) -> None:
        self.ended = True


class FakeRawInputStream:
    def __init__(self, **kwargs) -> None:
        self._callback = kwargs["callback"]

    def __enter__(self):
        self._callback(b"1" * 16384, 8192, None, None)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
