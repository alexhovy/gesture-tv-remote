from collections.abc import Callable
from http import HTTPStatus
from typing import Any, Protocol

from aiohttp import web

from src.application.ports.logger import LoggerPort
from src.shared.config import AppConfig
from src.web.remote.templates import render_remote_page


class DirectRemote(Protocol):
    def capabilities(self) -> Any: ...

    def supported_commands(self) -> tuple[str, ...]: ...

    def dispatch(self, command: str) -> Any: ...


def register_remote_routes(
    app: web.Application,
    *,
    config_provider: Callable[[], AppConfig],
    direct_remote: DirectRemote,
    logger: LoggerPort,
) -> None:
    async def remote_page(request: web.Request) -> web.Response:
        logger.info(f"Web remote page viewed from {_remote(request)}")
        return web.Response(
            text=render_remote_page(config_provider()),
            content_type="text/html",
        )

    async def remote_capabilities(request: web.Request) -> web.Response:
        del request
        capabilities = direct_remote.capabilities()
        return web.json_response(
            {
                "supportedCommands": list(capabilities.supported_commands),
                "commandGroups": {
                    group: list(commands)
                    for group, commands in capabilities.command_groups.items()
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
        return web.json_response(
            {
                "accepted": result.accepted,
                "command": result.command,
                "reason": result.reason,
            },
            status=status,
        )

    app.router.add_get("/remote", remote_page)
    app.router.add_get("/api/remote/capabilities", remote_capabilities)
    app.router.add_post("/api/remote/commands", remote_command)


def _remote(request: web.Request) -> str:
    return request.remote or "unknown"
