from typing import Protocol


class CommandDispatcherPort(Protocol):
    def start(self) -> None: ...

    def enqueue(
        self,
        source: str,
        command: str,
        *,
        coalesce_repeats: bool = True,
        max_pending: int | None = None,
    ) -> None: ...

    @property
    def queue_depth(self) -> int: ...

    @property
    def dropped_commands(self) -> int: ...

    @property
    def last_send_latency_seconds(self) -> float | None: ...

    async def close(self) -> None: ...
