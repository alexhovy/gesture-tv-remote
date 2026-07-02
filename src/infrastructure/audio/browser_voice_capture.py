import asyncio
import time
from collections import deque

from src.application.ports.logger import LoggerPort
from src.application.ports.tv_remote import (
    CapabilityStatus,
    TVRemotePort,
    VoiceInputMode,
    VoiceStreamPort,
)
from src.application.ports.voice_capture import VoiceCapturePort
from src.infrastructure.audio.voice_capture import VOICE_SAMPLE_RATE
from src.infrastructure.tv.async_call import call_remote_method
from src.shared.config import AppConfig, VoiceInputTarget

MAX_BROWSER_AUDIO_CHUNKS = 12


class BrowserAudioSource:
    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._chunks: deque[bytes] = deque(maxlen=MAX_BROWSER_AUDIO_CHUNKS)
        self._closed = False

    async def push_chunk(self, chunk: bytes) -> None:
        if not chunk:
            return
        async with self._condition:
            if self._closed:
                return
            self._chunks.append(chunk)
            self._condition.notify_all()

    async def next_chunk(self, timeout: float) -> bytes | None:
        async with self._condition:
            if not self._chunks and not self._closed:
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=timeout)
                except TimeoutError:
                    return None
            if not self._chunks:
                return None
            return self._chunks.popleft()

    async def close(self) -> None:
        async with self._condition:
            self._closed = True
            self._chunks.clear()
            self._condition.notify_all()


class BrowserVoiceCapture(VoiceCapturePort):
    def __init__(
        self,
        remote: TVRemotePort,
        audio_source: BrowserAudioSource,
        config: AppConfig,
        logger: LoggerPort,
    ) -> None:
        self._remote = remote
        self._audio_source = audio_source
        self._config = config
        self._logger = logger

    def update_config(self, config: AppConfig) -> None:
        self._config = config

    async def capture(self) -> None:
        voice_stream = None
        try:
            mode = _select_voice_input_mode(
                self._remote,
                self._config.tv.voice_input_target,
            )
            if mode is None:
                self._logger.info(
                    "TV adapter does not support configured voice input target: "
                    f"{self._config.tv.voice_input_target}"
                )
                return

            self._logger.info(
                "Browser voice input target: "
                f"{self._config.tv.voice_input_target} mode: {mode.value}"
            )
            voice_stream = await self._remote.start_voice(mode)
            if voice_stream is None:
                if mode == VoiceInputMode.NATIVE_VOICE_SEARCH:
                    self._logger.info("TV native voice input requested.")
                    return
                self._logger.info(
                    "TV did not provide a voice stream. "
                    "Skipping browser microphone capture."
                )
                return

            await self.capture_stream(voice_stream, mode.value)
            voice_stream = None
        except TimeoutError:
            self._logger.error("TV did not start a voice session.")
        except Exception as error:
            self._logger.error(f"Browser voice session failed: {error}")
        finally:
            if voice_stream is not None:
                await call_remote_method(voice_stream.end, offload_sync=False)

    async def capture_stream(
        self,
        voice_stream: VoiceStreamPort,
        context: str,
    ) -> None:
        deadline = time.monotonic() + self._config.tv.voice_capture_seconds
        sent_chunks = 0
        sent_bytes = 0
        self._logger.info(
            "Browser microphone: listening... "
            f"context={context} sample_rate={VOICE_SAMPLE_RATE}"
        )
        try:
            while time.monotonic() < deadline:
                timeout = max(0.0, deadline - time.monotonic())
                chunk = await self._audio_source.next_chunk(timeout)
                if chunk is None:
                    break
                sent = await call_remote_method(
                    voice_stream.send_chunk,
                    chunk,
                    offload_sync=False,
                )
                if sent is False:
                    self._logger.info("TV voice stream closed while sending audio.")
                    break
                sent_chunks += 1
                sent_bytes += len(chunk)
            self._logger.info(
                "Browser microphone: finished. "
                f"sent_chunks={sent_chunks} sent_bytes={sent_bytes} "
                f"context={context}"
            )
        finally:
            await call_remote_method(voice_stream.end, offload_sync=False)


def _select_voice_input_mode(
    remote: TVRemotePort,
    target: str,
) -> VoiceInputMode | None:
    voice = remote.capabilities().voice_input
    if target == VoiceInputTarget.AUTO.value:
        if voice.app_voice_input == CapabilityStatus.IMPLEMENTED:
            return VoiceInputMode.AUTO
        if voice.remote_mic_stream == CapabilityStatus.IMPLEMENTED:
            return VoiceInputMode.REMOTE_MIC_STREAM
        if voice.native_voice_search == CapabilityStatus.IMPLEMENTED:
            return VoiceInputMode.NATIVE_VOICE_SEARCH
        return None
    if (
        target == VoiceInputTarget.REMOTE_SEARCH.value
        and voice.remote_mic_stream == CapabilityStatus.IMPLEMENTED
    ):
        return VoiceInputMode.REMOTE_MIC_STREAM
    if (
        target == VoiceInputTarget.NATIVE_SEARCH.value
        and voice.native_voice_search == CapabilityStatus.IMPLEMENTED
    ):
        return VoiceInputMode.NATIVE_VOICE_SEARCH
    return None
