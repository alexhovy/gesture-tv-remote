from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any


class BrowserDebugStream:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._latest = "{}"
        self._closed = False

    def publish(self, snapshot: dict[str, Any]) -> None:
        if self._closed:
            return
        payload = json.dumps(snapshot, separators=(",", ":"))
        self._latest = payload
        stale_subscribers = []
        for subscriber in self._subscribers:
            if subscriber.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    subscriber.get_nowait()
            try:
                subscriber.put_nowait(payload)
            except asyncio.QueueFull:
                stale_subscribers.append(subscriber)
        for subscriber in stale_subscribers:
            self._subscribers.discard(subscriber)

    async def subscribe(self) -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=2)
        if self._closed:
            return
        self._subscribers.add(queue)
        try:
            if self._latest != "{}":
                yield self._latest
            while not self._closed:
                payload = await queue.get()
                if payload == "":
                    break
                yield payload
        finally:
            self._subscribers.discard(queue)

    def close(self) -> None:
        self._closed = True
        for subscriber in tuple(self._subscribers):
            with contextlib.suppress(asyncio.QueueFull):
                subscriber.put_nowait("")
