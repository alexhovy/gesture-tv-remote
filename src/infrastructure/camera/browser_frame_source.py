import threading
from typing import Any


class BrowserFrameSource:
    """Latest-frame source fed by a browser media stream."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest_frame: Any = None
        self._latest_version = 0
        self._started = False
        self._closed = False

    def start(self) -> None:
        with self._lock:
            self._started = True

    def is_open(self) -> bool:
        with self._lock:
            return not self._closed

    def latest_versioned(self) -> tuple[int, Any | None]:
        with self._lock:
            return self._latest_version, self._latest_frame

    def failed(self) -> bool:
        return False

    def submit_frame(self, frame: Any) -> None:
        with self._lock:
            if self._closed:
                return
            self._latest_frame = frame
            self._latest_version += 1

    def stop(self) -> None:
        with self._lock:
            self._started = False

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._latest_frame = None
