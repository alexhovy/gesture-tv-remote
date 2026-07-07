import asyncio
import contextlib
import json
from collections.abc import Callable
from http import HTTPStatus
from typing import Any, Protocol

from aiohttp import web
from aiohttp.client_exceptions import ClientConnectionResetError

from src.application.ports.logger import LoggerPort
from src.shared.config import AppConfig
from src.web.remote.templates import render_remote_page

TEXT_EVENT_QUEUES_KEY = web.AppKey("text_event_queues", set[asyncio.Queue[Any | None]])


class DirectRemote(Protocol):
    def capabilities(self) -> Any: ...

    def supported_commands(self) -> tuple[str, ...]: ...

    def dispatch(self, command: str) -> Any: ...


class TextInputRemote(Protocol):
    def capabilities(self) -> Any: ...

    def status(self) -> Any: ...

    def subscribe(self, subscriber: Callable[[Any], None]) -> Callable[[], None]: ...

    async def send(self, text: str) -> Any: ...

    async def replace(self, text: str) -> Any: ...

    async def delete(self, count: int = 1) -> Any: ...

    async def sync(self, text: str) -> Any: ...

    async def submit(self) -> Any: ...

    def dismiss_for_command(self, command: str) -> None: ...


def register_remote_routes(
    app: web.Application,
    *,
    config_provider: Callable[[], AppConfig],
    direct_remote: DirectRemote,
    text_input: TextInputRemote,
    logger: LoggerPort,
) -> None:
    app[TEXT_EVENT_QUEUES_KEY] = set()

    async def remote_page(request: web.Request) -> web.Response:
        logger.info(f"Web remote page viewed from {_remote(request)}")
        return web.Response(
            text=render_remote_page(config_provider()),
            content_type="text/html",
        )

    async def remote_capabilities(request: web.Request) -> web.Response:
        del request
        capabilities = direct_remote.capabilities()
        text_capabilities = text_input.capabilities()
        return web.json_response(
            {
                "supportedCommands": list(capabilities.supported_commands),
                "commandGroups": {
                    group: list(commands)
                    for group, commands in capabilities.command_groups.items()
                },
                "textInput": {
                    "focusDetection": text_capabilities.focus_detection.value,
                    "sendText": text_capabilities.send_text.value,
                    "replaceText": text_capabilities.replace_text.value,
                    "deleteText": text_capabilities.delete_text.value,
                    "submitText": text_capabilities.submit_text.value,
                    "browserCapture": text_capabilities.browser_capture.value,
                    "notes": list(text_capabilities.notes),
                },
            }
        )

    async def remote_command(request: web.Request) -> web.Response:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        result = direct_remote.dispatch(str(payload.get("command", "")))
        status = HTTPStatus.OK if result.accepted else HTTPStatus.BAD_REQUEST
        logger.info(
            "Web remote command from "
            f"{_remote(request)} command={result.command} accepted={result.accepted}"
        )
        if result.accepted:
            text_input.dismiss_for_command(result.command)
        return web.json_response(
            {
                "accepted": result.accepted,
                "command": result.command,
                "reason": result.reason,
            },
            status=status,
        )

    async def text_status(request: web.Request) -> web.Response:
        del request
        status = text_input.status()
        logger.debug(
            "Web remote text status " f"active={status.active} mode={status.mode.value}"
        )
        return web.json_response(_text_status_payload(status))

    async def text_events(request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse(
            status=HTTPStatus.OK,
            headers={
                "Cache-Control": "no-cache",
                "Content-Type": "text/event-stream",
            },
        )
        await response.prepare(request)
        logger.info(f"Web remote text event stream connected from {_remote(request)}")
        queue: asyncio.Queue[Any | None] = asyncio.Queue()
        app[TEXT_EVENT_QUEUES_KEY].add(queue)
        unsubscribe = text_input.subscribe(queue.put_nowait)
        try:
            while True:
                status = await queue.get()
                if status is None:
                    break
                payload = json.dumps(_text_status_payload(status))
                await response.write(f"data: {payload}\n\n".encode())
        except (
            asyncio.CancelledError,
            ConnectionResetError,
            ClientConnectionResetError,
        ):
            pass
        finally:
            app[TEXT_EVENT_QUEUES_KEY].discard(queue)
            unsubscribe()
            logger.info(
                f"Web remote text event stream disconnected from {_remote(request)}"
            )
            if request.transport is not None and not request.transport.is_closing():
                with contextlib.suppress(Exception):
                    await response.write_eof()
        return response

    async def send_text(request: web.Request) -> web.Response:
        payload = await _json_payload(request)
        text = str(payload.get("text", ""))
        logger.info(f"Web remote text send from {_remote(request)} length={len(text)}")
        result = await text_input.send(text)
        return _text_result(result)

    async def replace_text(request: web.Request) -> web.Response:
        payload = await _json_payload(request)
        text = str(payload.get("text", ""))
        logger.info(
            f"Web remote text replace from {_remote(request)} length={len(text)}"
        )
        result = await text_input.replace(text)
        return _text_result(result)

    async def sync_text(request: web.Request) -> web.Response:
        payload = await _json_payload(request)
        text = str(payload.get("text", ""))
        logger.info(f"Web remote text sync from {_remote(request)} length={len(text)}")
        result = await text_input.sync(text)
        return _text_result(result)

    async def delete_text(request: web.Request) -> web.Response:
        payload = await _json_payload(request)
        try:
            count = int(payload.get("count", 1))
        except (TypeError, ValueError):
            count = 1
        logger.info(f"Web remote text delete from {_remote(request)} count={count}")
        result = await text_input.delete(count)
        return _text_result(result)

    async def submit_text(request: web.Request) -> web.Response:
        logger.info(f"Web remote text submit from {_remote(request)}")
        result = await text_input.submit()
        return _text_result(result)

    app.router.add_get("/remote", remote_page)
    app.router.add_get("/api/remote/capabilities", remote_capabilities)
    app.router.add_post("/api/remote/commands", remote_command)
    app.router.add_get("/api/remote/text/status", text_status)
    app.router.add_get("/api/remote/text/events", text_events)
    app.router.add_post("/api/remote/text", send_text)
    app.router.add_post("/api/remote/text/replace", replace_text)
    app.router.add_post("/api/remote/text/sync", sync_text)
    app.router.add_post("/api/remote/text/delete", delete_text)
    app.router.add_post("/api/remote/text/submit", submit_text)
    app.on_shutdown.append(_cleanup_text_events)


async def _cleanup_text_events(app: web.Application) -> None:
    queues = app[TEXT_EVENT_QUEUES_KEY]
    for queue in tuple(queues):
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait(None)


async def _json_payload(request: web.Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _text_result(result: Any) -> web.Response:
    status = HTTPStatus.OK if result.accepted else HTTPStatus.BAD_REQUEST
    return web.json_response(
        {
            "accepted": result.accepted,
            "reason": result.reason,
        },
        status=status,
    )


def _text_status_payload(status: Any) -> dict[str, Any]:
    return {
        "active": status.active,
        "mode": status.mode.value,
        "value": status.value,
        "label": status.label,
        "appId": status.app_id,
    }


def _remote(request: web.Request) -> str:
    return request.remote or "unknown"
