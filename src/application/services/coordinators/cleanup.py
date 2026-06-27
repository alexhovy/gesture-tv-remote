import asyncio
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any

from src.application.ports.command_dispatcher import CommandDispatcherPort
from src.application.ports.display import DisplayPort
from src.application.ports.frame_source import FrameSourcePort
from src.application.ports.hand_tracker import HandTrackerPort
from src.application.ports.logger import LoggerPort
from src.application.ports.tv_remote import TVRemotePort

CLEANUP_TIMEOUT_SECONDS = 1.0


class CleanupCoordinator:
    def __init__(
        self,
        *,
        remote: TVRemotePort,
        frame_source: FrameSourcePort,
        hand_tracker: HandTrackerPort,
        display: DisplayPort,
        command_dispatcher: CommandDispatcherPort,
        logger: LoggerPort,
    ) -> None:
        self._remote = remote
        self._frame_source = frame_source
        self._hand_tracker = hand_tracker
        self._display = display
        self._command_dispatcher = command_dispatcher
        self._logger = logger

    async def cleanup(self, voice_task: asyncio.Task | None) -> None:
        self._remote.set_app_voice_input_handler(None)
        if voice_task is not None and not voice_task.done():
            voice_task.cancel()
            await self._cleanup_step("voice capture", voice_task)
        await self._cleanup_sync_step("frame source", self._frame_source.close)
        await self._cleanup_sync_step("hand tracker", self._hand_tracker.close)
        self._cleanup_now("display", self._display.close)
        await self._cleanup_step("command dispatcher", self._command_dispatcher.close())
        await self._cleanup_step("TV remote", self._remote.disconnect())

    async def _cleanup_step(self, name: str, awaitable: Awaitable[Any]) -> None:
        try:
            await asyncio.wait_for(awaitable, timeout=CLEANUP_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            pass
        except TimeoutError:
            self._logger.error(f"Timed out while cleaning up {name}.")
        except Exception as error:
            self._logger.error(f"Error while cleaning up {name}: {error}")

    async def _cleanup_sync_step(self, name: str, method: Callable[[], None]) -> None:
        done = threading.Event()
        error: list[BaseException] = []

        def run() -> None:
            try:
                method()
            except BaseException as cleanup_error:
                error.append(cleanup_error)
            finally:
                done.set()

        thread = threading.Thread(
            target=run,
            name=f"cleanup-{name.replace(' ', '-')}",
            daemon=True,
        )
        thread.start()
        deadline = time.monotonic() + CLEANUP_TIMEOUT_SECONDS
        while not done.is_set() and time.monotonic() < deadline:
            await asyncio.sleep(0.01)

        if not done.is_set():
            self._logger.error(f"Timed out while cleaning up {name}.")
            return

        if error:
            self._logger.error(f"Error while cleaning up {name}: {error[0]}")

    def _cleanup_now(self, name: str, method: Callable[[], None]) -> None:
        try:
            method()
        except Exception as error:
            self._logger.error(f"Error while cleaning up {name}: {error}")
