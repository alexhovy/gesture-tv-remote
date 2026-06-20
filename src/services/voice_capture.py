import asyncio
import time

from src.infrastructure.tv.async_call import call_remote_method
from src.infrastructure.tv.tv_remote import TvRemoteClient
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class VoiceCaptureService:
    def __init__(self, remote: TvRemoteClient, config: AppConfig) -> None:
        self._remote = remote
        self._config = config
        self._logger = AppLogger()

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
            chunks: asyncio.Queue[bytes] = asyncio.Queue()

            def audio_callback(indata, frames, time_info, status) -> None:
                if status:
                    loop.call_soon_threadsafe(
                        self._logger.debug,
                        f"microphone status={status}",
                    )
                loop.call_soon_threadsafe(chunks.put_nowait, bytes(indata))

            self._logger.info("Microphone: listening...")
            with sd.RawInputStream(
                samplerate=8000,
                channels=1,
                dtype="int16",
                blocksize=4096,
                callback=audio_callback,
            ):
                deadline = time.monotonic() + self._config.voice_capture_seconds
                while time.monotonic() < deadline:
                    timeout = max(0.0, deadline - time.monotonic())
                    try:
                        chunk = await asyncio.wait_for(chunks.get(), timeout=timeout)
                    except asyncio.TimeoutError:
                        break
                    await call_remote_method(voice_stream.send_chunk, chunk)
            self._logger.info("Microphone: finished.")
        except asyncio.TimeoutError:
            self._logger.error("TV did not start a voice session.")
        except (OSError, RuntimeError) as error:
            self._logger.error(f"Microphone capture failed: {error}")
        except Exception as error:
            self._logger.error(f"TV voice session failed: {error}")
        finally:
            if voice_stream is not None:
                await call_remote_method(voice_stream.end)
