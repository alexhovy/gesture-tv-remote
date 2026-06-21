import asyncio
import contextlib
from collections import deque
from dataclasses import dataclass
from typing import Any

from src.domain.constants import DISPLAY_COMMAND_SELECT, TV_COMMAND_DPAD_CENTER
from src.shared.logging import AppLogger

MAX_PENDING_COMMANDS = 8


@dataclass(frozen=True)
class RemoteCommandRequest:
    gesture: str
    command: str


class RemoteCommandDispatcher:
    def __init__(self, remote: Any, logger: AppLogger) -> None:
        self._remote = remote
        self._logger = logger
        self._commands: deque[RemoteCommandRequest] = deque()
        self._has_work: asyncio.Event | None = None
        self._worker_task: asyncio.Task | None = None
        self._closed = False

    def start(self) -> None:
        if self._worker_task is not None and not self._worker_task.done():
            return
        self._has_work = asyncio.Event()
        self._worker_task = asyncio.create_task(self._run())

    def enqueue(self, gesture: str, command: str) -> None:
        if self._closed:
            return
        if self._has_work is None:
            self.start()

        request = RemoteCommandRequest(gesture=gesture, command=command)
        # TV adapters can be slow or reconnecting; keep gesture detection independent
        # by bounding pending remote work and dropping stale oldest commands first.
        if len(self._commands) >= MAX_PENDING_COMMANDS:
            if self._commands[-1].command == command:
                self._commands[-1] = request
            else:
                self._commands.popleft()
                self._commands.append(request)
            self._has_work.set()
            return
        self._commands.append(request)
        self._has_work.set()

    async def close(self) -> None:
        self._closed = True
        self._commands.clear()
        if self._worker_task is None:
            return

        self._worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._worker_task
        self._worker_task = None

    async def _run(self) -> None:
        if self._has_work is None:
            return

        while True:
            await self._has_work.wait()
            while True:
                request = self._next_request()
                if request is None:
                    self._has_work.clear()
                    break

                await self._send(request)

    async def _send(self, request: RemoteCommandRequest) -> None:
        display_command = (
            DISPLAY_COMMAND_SELECT
            if request.command == TV_COMMAND_DPAD_CENTER
            else request.command
        )
        self._logger.info(f"Gesture: {request.gesture} -> {display_command}")
        await self._remote.send_key_command(request.command)

    def _next_request(self) -> RemoteCommandRequest | None:
        if self._commands:
            return self._commands.popleft()

        return None
