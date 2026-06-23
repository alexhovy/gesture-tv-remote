from typing import Any


class FakeFrameSource:
    def __init__(self, frames: list[Any] | None = None, open: bool = True) -> None:
        self._frames = frames or []
        self._open = open
        self._started = False
        self._closed = False
        self._failed = False
        self._index = 0

    def is_open(self) -> bool:
        return self._open

    def start(self) -> None:
        self._started = True

    def latest_versioned(self) -> tuple[int, Any | None]:
        if not self._frames:
            return 0, None
        index = min(self._index, len(self._frames) - 1)
        self._index += 1
        return self._index, self._frames[index]

    def failed(self) -> bool:
        return self._failed

    def stop(self) -> None:
        self._closed = True

    def close(self) -> None:
        self.stop()

    @property
    def started(self) -> bool:
        return self._started

    @property
    def closed(self) -> bool:
        return self._closed
