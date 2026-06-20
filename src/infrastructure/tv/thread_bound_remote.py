import asyncio
import inspect
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any


class ThreadBoundRemoteExecutor:
    def __init__(self, name: str) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=name)
        self._closed = False

    async def call(
        self,
        method: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if self._closed:
            raise RuntimeError("Remote executor is closed")

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            self._executor,
            lambda: method(*args, **kwargs),
        )
        if inspect.isawaitable(result):
            return await result
        return result

    def shutdown(self) -> None:
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
