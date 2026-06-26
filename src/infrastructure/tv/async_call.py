import asyncio
import inspect
from collections.abc import Callable
from typing import Any


async def call_remote_method(
    method: Callable[..., Any],
    *args: Any,
    offload_sync: bool = True,
    **kwargs: Any,
) -> Any:
    if inspect.iscoroutinefunction(method):
        return await method(*args, **kwargs)

    if offload_sync:
        result = await asyncio.to_thread(method, *args, **kwargs)
    else:
        result = method(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result
