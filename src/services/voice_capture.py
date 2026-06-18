import asyncio
import time

from androidtvremote2 import ConnectionClosed

from src.infrastructure.android_tv_remote import AndroidTvRemoteClient
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class VoiceCaptureService:
    def __init__(self, remote: AndroidTvRemoteClient, config: AppConfig) -> None:
        self._remote = remote
        self._config = config
        self._logger = AppLogger()

    async def capture(self) -> None:
        try:
            import sounddevice as sd
        except (ImportError, OSError) as error:
            self._logger.error(f"Microphone capture unavailable: {error}")
            self._logger.info("Install sounddevice and PortAudio support for microphone capture.")
            return

        voice_stream = None
        try:
            voice_stream = await self._remote.start_voice()
            if voice_stream is None:
                self._logger.info("TV not connected. Skipping microphone capture.")
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
                    voice_stream.send_chunk(chunk)
            self._logger.info("Microphone: finished.")
        except asyncio.TimeoutError:
            self._logger.error("TV did not start a voice session.")
        except ConnectionClosed:
            self._logger.error("TV connection closed. Microphone capture stopped.")
        except (OSError, RuntimeError) as error:
            self._logger.error(f"Microphone capture failed: {error}")
        finally:
            if voice_stream is not None:
                voice_stream.end()
