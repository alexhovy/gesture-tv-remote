import asyncio
import time

from src.application.ports.logger import LoggerPort
from src.application.ports.tv_remote import (
    CapabilityStatus,
    TVRemotePort,
    VoiceInputMode,
)
from src.infrastructure.tv.async_call import call_remote_method
from src.shared.config import AppConfig, VoiceInputTarget

VOICE_SAMPLE_RATE = 8000
VOICE_FRAMES_PER_BUFFER = 8192

class MicrophoneVoiceCapture:
    def __init__(
        self,
        remote: TVRemotePort,
        config: AppConfig,
        logger: LoggerPort,
    ) -> None:
        self._remote = remote
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

            self._logger.info(f"TV voice input mode: {mode.value}")
            voice_stream = await self._remote.start_voice(mode)
            if voice_stream is None:
                if mode == VoiceInputMode.NATIVE_VOICE_SEARCH:
                    self._logger.info("TV native voice input requested.")
                    return
                self._logger.info(
                    "TV did not provide a voice stream. Skipping microphone capture."
                )
                return

            try:
                import sounddevice as sd
            except (ImportError, OSError) as error:
                self._logger.error(f"Microphone capture unavailable: {error}")
                self._logger.info(
                    "Install sounddevice and PortAudio support for microphone capture."
                )
                return

            loop = asyncio.get_running_loop()
            chunks: asyncio.Queue[bytes] = asyncio.Queue(maxsize=4)

            def audio_callback(indata, frames, time_info, status) -> None:
                del frames, time_info
                if status:
                    loop.call_soon_threadsafe(
                        self._logger.debug,
                        f"microphone status={status}",
                    )
                loop.call_soon_threadsafe(_put_latest_chunk, chunks, bytes(indata))

            self._logger.info("Microphone: listening...")
            sent_chunks = 0
            sent_bytes = 0
            max_abs_sample = 0
            nonzero_samples = 0
            with sd.RawInputStream(
                samplerate=VOICE_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=VOICE_FRAMES_PER_BUFFER,
                callback=audio_callback,
            ):
                deadline = time.monotonic() + self._config.tv.voice_capture_seconds
                while time.monotonic() < deadline:
                    timeout = max(0.0, deadline - time.monotonic())
                    try:
                        chunk = await asyncio.wait_for(chunks.get(), timeout=timeout)
                    except TimeoutError:
                        break
                    chunk_max_abs, chunk_nonzero_samples = _pcm16_chunk_stats(chunk)
                    max_abs_sample = max(max_abs_sample, chunk_max_abs)
                    nonzero_samples += chunk_nonzero_samples
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
                "Microphone: finished. "
                f"sent_chunks={sent_chunks} sent_bytes={sent_bytes} "
                f"max_abs_sample={max_abs_sample} "
                f"nonzero_samples={nonzero_samples}"
            )
        except TimeoutError:
            self._logger.error("TV did not start a voice session.")
        except (OSError, RuntimeError) as error:
            self._logger.error(f"Microphone capture failed: {error}")
        except Exception as error:
            self._logger.error(f"TV voice session failed: {error}")
        finally:
            if voice_stream is not None:
                await call_remote_method(voice_stream.end, offload_sync=False)


def _put_latest_chunk(chunks: asyncio.Queue[bytes], chunk: bytes) -> None:
    if chunks.full():
        try:
            chunks.get_nowait()
        except asyncio.QueueEmpty:
            pass
    chunks.put_nowait(chunk)


def _select_voice_input_mode(
    remote: TVRemotePort,
    target: str,
) -> VoiceInputMode | None:
    voice = remote.capabilities().voice_input
    if (
        target == VoiceInputTarget.APP.value
        and voice.app_voice_input == CapabilityStatus.IMPLEMENTED
    ):
        return VoiceInputMode.APP_VOICE_INPUT
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


def _pcm16_chunk_stats(chunk: bytes) -> tuple[int, int]:
    max_abs_sample = 0
    nonzero_samples = 0
    for index in range(0, len(chunk) - 1, 2):
        sample = int.from_bytes(chunk[index : index + 2], "little", signed=True)
        if sample != 0:
            nonzero_samples += 1
            max_abs_sample = max(max_abs_sample, abs(sample))
    return max_abs_sample, nonzero_samples
