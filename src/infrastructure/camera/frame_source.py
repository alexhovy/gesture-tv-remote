import threading
from typing import Any


class LatestFrameSource:
    def __init__(self, capture: Any) -> None:
        self._capture = capture
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._latest_frame: Any = None
        self._failed = False

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def latest(self) -> Any | None:
        with self._lock:
            return self._latest_frame

    def failed(self) -> bool:
        with self._lock:
            return self._failed

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _read_loop(self) -> None:
        while not self._stop_event.is_set():
            ok, frame = self._capture.read()
            with self._lock:
                if ok:
                    self._latest_frame = frame
                    self._failed = False
                else:
                    self._failed = True
                    return
