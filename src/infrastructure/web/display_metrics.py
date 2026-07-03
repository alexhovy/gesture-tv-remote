from __future__ import annotations

import threading

from src.application.ports.display_metrics import DisplaySize


class BrowserDisplayMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._size: DisplaySize | None = None

    def update_size(self, width: float, height: float) -> None:
        if width <= 0 or height <= 0:
            return
        with self._lock:
            self._size = DisplaySize(width=width, height=height)

    def latest_size(self) -> DisplaySize | None:
        with self._lock:
            return self._size
