import asyncio
import contextlib
import time
from collections import deque
from dataclasses import dataclass

from src.application.ports.logger import LoggerPort
from src.application.ports.tv_remote import TVRemotePort
from src.domain.constants import DISPLAY_COMMAND_SELECT, TV_COMMAND_DPAD_CENTER

MAX_PENDING_COMMANDS = 8


@dataclass(frozen=True)
class RemoteCommandRequest:
    gesture: str
    command: str
    enqueued_at: float


class RemoteCommandDispatcher:
    def __init__(self, remote: TVRemotePort, logger: LoggerPort) -> None:
        self._remote = remote
        self._logger = logger
        self._commands: deque[RemoteCommandRequest] = deque()
        self._has_work: asyncio.Event | None = None
        self._worker_task: asyncio.Task | None = None
        self._closed = False
        self._last_send_latency_seconds: float | None = None
        self._dropped_commands = 0

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

        request = RemoteCommandRequest(
            gesture=gesture,
            command=command,
            enqueued_at=time.monotonic(),
        )
        # TV adapters can be slow or reconnecting; keep gesture detection independent
        # by bounding pending remote work and dropping stale oldest commands first.
        if len(self._commands) >= MAX_PENDING_COMMANDS:
            if self._commands[-1].command == command:
                self._commands[-1] = request
            else:
                self._commands.popleft()
                self._dropped_commands += 1
                self._commands.append(request)
            self._has_work.set()
            return
        self._commands.append(request)
        self._has_work.set()

    @property
    def queue_depth(self) -> int:
        return len(self._commands)

    @property
    def dropped_commands(self) -> int:
        return self._dropped_commands

    @property
    def last_send_latency_seconds(self) -> float | None:
        return self._last_send_latency_seconds

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
        started_at = time.monotonic()
        await self._remote.send_command(request.command)
        self._last_send_latency_seconds = time.monotonic() - started_at

    def _next_request(self) -> RemoteCommandRequest | None:
        if self._commands:
            return self._commands.popleft()

        return None
