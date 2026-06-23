import asyncio
import time

from src.application.ports.logger import LoggerPort
from src.application.ports.tv_remote import TVRemotePort
from src.infrastructure.tv.async_call import call_remote_method
from src.shared.config import AppConfig


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
            voice_stream = await self._remote.start_voice()
            if voice_stream is None:
                self._logger.info("TV not connected. Skipping microphone capture.")
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
            with sd.RawInputStream(
                samplerate=8000,
                channels=1,
                dtype="int16",
                blocksize=4096,
                callback=audio_callback,
            ):
                deadline = time.monotonic() + self._config.tv.voice_capture_seconds
                while time.monotonic() < deadline:
                    timeout = max(0.0, deadline - time.monotonic())
                    try:
                        chunk = await asyncio.wait_for(chunks.get(), timeout=timeout)
                    except TimeoutError:
                        break
                    await call_remote_method(voice_stream.send_chunk, chunk)
            self._logger.info("Microphone: finished.")
        except TimeoutError:
            self._logger.error("TV did not start a voice session.")
        except (OSError, RuntimeError) as error:
            self._logger.error(f"Microphone capture failed: {error}")
        except Exception as error:
            self._logger.error(f"TV voice session failed: {error}")
        finally:
            if voice_stream is not None:
                await call_remote_method(voice_stream.end)


def _put_latest_chunk(chunks: asyncio.Queue[bytes], chunk: bytes) -> None:
    if chunks.full():
        try:
            chunks.get_nowait()
        except asyncio.QueueEmpty:
            pass
    chunks.put_nowait(chunk)
