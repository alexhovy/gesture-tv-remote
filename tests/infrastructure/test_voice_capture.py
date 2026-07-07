import asyncio
import sys
import types
import unittest

from src.application.ports.tv_remote import (
    CapabilityStatus,
    TextInputCapabilities,
    TextInputHandler,
    TextInputMode,
    TextInputStatus,
    TvAdapterCapabilities,
    VoiceInputCapabilities,
    VoiceInputMode,
)
from src.infrastructure.audio.local_voice_capture import LocalMicrophoneVoiceCapture
from tests.helpers.config_helpers import app_config


class TextInputRemoteMixin:
    def set_text_input_handler(self, handler: TextInputHandler | None) -> None:
        del handler

    def text_input_status(self) -> TextInputStatus:
        return TextInputStatus(active=False, mode=TextInputMode.MANUAL)

    async def send_text(self, text: str) -> None:
        del text

    async def replace_text(self, text: str) -> None:
        del text

    async def delete_text(self, count: int = 1) -> None:
        del count

    async def submit_text(self) -> None:
        pass


class UnsupportedVoiceRemote(TextInputRemoteMixin):
    def __init__(self) -> None:
        self.started_voice = False

    async def connect(self) -> bool:
        return True

    async def send_command(self, command: str) -> None:
        pass

    async def start_voice(self, mode: VoiceInputMode):
        self.voice_mode = mode
        self.started_voice = True
        return None

    async def disconnect(self) -> None:
        pass

    def capabilities(self) -> TvAdapterCapabilities:
        return _capabilities(
            remote_mic_stream=CapabilityStatus.UNSUPPORTED,
            native_voice_search=CapabilityStatus.UNSUPPORTED,
        )


class VoiceCaptureTests(unittest.TestCase):
    def test_unsupported_voice_returns_without_starting_microphone(self) -> None:
        remote = UnsupportedVoiceRemote()
        logger = FakeLogger()
        service = LocalMicrophoneVoiceCapture(
            remote,
            app_config(voice_input_target="auto"),
            logger,
        )

        asyncio.run(service.capture())

        self.assertFalse(remote.started_voice)
        self.assertIn(
            "TV adapter does not support configured voice input target: auto",
            logger.messages,
        )

    def test_voice_capture_logs_sent_audio_chunks(self) -> None:
        remote = SupportedVoiceRemote()
        logger = FakeLogger()
        service = LocalMicrophoneVoiceCapture(
            remote,
            app_config(
                voice_capture_seconds=0.01,
                voice_input_target="remote_search",
            ),
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
        self.assertEqual(remote.voice_mode, VoiceInputMode.REMOTE_MIC_STREAM)
        self.assertTrue(remote.voice_stream.ended)
        self.assertIn(
            "Microphone: finished. sent_chunks=1 sent_bytes=16384 "
            "max_abs_sample=12593 nonzero_samples=8192 "
            "context=remote_mic_stream",
            logger.messages,
        )

    def test_voice_capture_requests_native_voice_when_stream_is_unavailable(
        self,
    ) -> None:
        remote = NativeVoiceRemote()
        logger = FakeLogger()
        service = LocalMicrophoneVoiceCapture(
            remote,
            app_config(voice_input_target="native_search"),
            logger,
        )

        asyncio.run(service.capture())

        self.assertEqual(remote.voice_mode, VoiceInputMode.NATIVE_VOICE_SEARCH)
        self.assertIn("TV native voice input requested.", logger.messages)

    def test_voice_capture_auto_requests_auto_when_app_voice_is_supported(self) -> None:
        remote = AppVoiceRemote()
        logger = FakeLogger()
        service = LocalMicrophoneVoiceCapture(
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

        self.assertEqual(remote.voice_mode, VoiceInputMode.AUTO)

    def test_capture_stream_sends_audio_to_existing_voice_stream(self) -> None:
        remote = SupportedVoiceRemote()
        logger = FakeLogger()
        service = LocalMicrophoneVoiceCapture(
            remote,
            app_config(voice_capture_seconds=0.01),
            logger,
        )
        voice_stream = FakeVoiceStream()
        sounddevice = types.ModuleType("sounddevice")
        sounddevice.RawInputStream = FakeRawInputStream

        previous = sys.modules.get("sounddevice")
        sys.modules["sounddevice"] = sounddevice
        try:
            asyncio.run(service.capture_stream(voice_stream, "android_app_voice"))
        finally:
            if previous is None:
                sys.modules.pop("sounddevice", None)
            else:
                sys.modules["sounddevice"] = previous

        self.assertEqual(voice_stream.chunks, [b"1" * 16384])
        self.assertTrue(voice_stream.ended)
        self.assertIn(
            "Microphone: listening... context=android_app_voice",
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


class SupportedVoiceRemote(TextInputRemoteMixin):
    def __init__(self) -> None:
        self.voice_stream = FakeVoiceStream()

    async def start_voice(self, mode: VoiceInputMode):
        self.voice_mode = mode
        return self.voice_stream

    def capabilities(self) -> TvAdapterCapabilities:
        return _capabilities(
            remote_mic_stream=CapabilityStatus.IMPLEMENTED,
            native_voice_search=CapabilityStatus.IMPLEMENTED,
        )


class NativeVoiceRemote(TextInputRemoteMixin):
    def __init__(self) -> None:
        self.voice_mode = None

    async def start_voice(self, mode: VoiceInputMode):
        self.voice_mode = mode
        return None

    def capabilities(self) -> TvAdapterCapabilities:
        return _capabilities(
            remote_mic_stream=CapabilityStatus.UNSUPPORTED,
            native_voice_search=CapabilityStatus.IMPLEMENTED,
        )


class AppVoiceRemote(TextInputRemoteMixin):
    def __init__(self) -> None:
        self.voice_stream = FakeVoiceStream()
        self.voice_mode = None

    async def start_voice(self, mode: VoiceInputMode):
        self.voice_mode = mode
        return self.voice_stream

    def capabilities(self) -> TvAdapterCapabilities:
        return _capabilities(
            remote_mic_stream=CapabilityStatus.IMPLEMENTED,
            native_voice_search=CapabilityStatus.IMPLEMENTED,
            app_voice_input=CapabilityStatus.IMPLEMENTED,
        )


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


def _capabilities(
    *,
    remote_mic_stream: CapabilityStatus,
    native_voice_search: CapabilityStatus,
    app_voice_input: CapabilityStatus = CapabilityStatus.UNSUPPORTED,
) -> TvAdapterCapabilities:
    return TvAdapterCapabilities(
        supported_commands=frozenset(),
        power=CapabilityStatus.UNSUPPORTED,
        volume=CapabilityStatus.UNSUPPORTED,
        directional_navigation=CapabilityStatus.UNSUPPORTED,
        media_controls=CapabilityStatus.UNSUPPORTED,
        text_input=TextInputCapabilities(
            focus_detection=CapabilityStatus.UNSUPPORTED,
            send_text=CapabilityStatus.UNSUPPORTED,
            replace_text=CapabilityStatus.UNSUPPORTED,
            delete_text=CapabilityStatus.UNSUPPORTED,
            submit_text=CapabilityStatus.UNSUPPORTED,
        ),
        source_selection=CapabilityStatus.UNSUPPORTED,
        wake_on_lan=CapabilityStatus.UNSUPPORTED,
        pairing=CapabilityStatus.UNSUPPORTED,
        voice_input=VoiceInputCapabilities(
            remote_mic_stream=remote_mic_stream,
            native_voice_search=native_voice_search,
            app_voice_input=app_voice_input,
        ),
        connection_type="fake",
    )


if __name__ == "__main__":
    unittest.main()
