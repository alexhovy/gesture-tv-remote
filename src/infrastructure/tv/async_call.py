import asyncio
import inspect
from collections.abc import Callable
from typing import Any


async def call_remote_method(
    method: Callable[..., Any], *args: Any, **kwargs: Any
) -> Any:
    if inspect.iscoroutinefunction(method):
        return await method(*args, **kwargs)

    result = await asyncio.to_thread(method, *args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result
