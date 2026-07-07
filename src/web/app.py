from collections.abc import Callable
from http import HTTPStatus
from typing import Protocol

from aiohttp import web

from src.application.ports.config_provider import ConfigStorePort
from src.application.ports.logger import LoggerPort
from src.shared.config import AppConfig
from src.web.assets import static_dir
from src.web.gesture.app import (
    BrowserAudioSink,
    BrowserDebugSource,
    BrowserDisplayMetricsSink,
    BrowserVideoSink,
    register_gesture_routes,
)
from src.web.home.templates import render_home_page
from src.web.remote.app import DirectRemote, TextInputRemote, register_remote_routes
from src.web.settings.handlers import (
    active_tab,
    form_tab,
    render_settings_page,
    save_settings_form,
    settings_redirect,
)


class RuntimeControl(Protocol):
    def request_restart(self) -> None: ...


def create_web_app(
    *,
    repository: ConfigStorePort,
    config_provider: Callable[[], AppConfig],
    browser_video_sink: BrowserVideoSink,
    browser_audio_sink: BrowserAudioSink,
    debug_source: BrowserDebugSource,
    direct_remote: DirectRemote,
    text_input: TextInputRemote,
    logger: LoggerPort,
    display_metrics_sink: BrowserDisplayMetricsSink | None = None,
    runtime_control: RuntimeControl | None = None,
) -> web.Application:
    app = web.Application()

    async def home_page(request: web.Request) -> web.Response:
        logger.info(f"Web home page viewed from {_remote(request)}")
        return web.Response(
            text=render_home_page(config_provider()),
            content_type="text/html",
        )

    async def config_page(request: web.Request) -> web.Response:
        logger.info(f"Web config page viewed from {_remote(request)}")
        return web.Response(
            text=render_settings_page(
                config_provider(),
                query=request.query,
                restart_available=runtime_control is not None,
            ),
            content_type="text/html",
        )

    async def health(request: web.Request) -> web.Response:
        del request
        return web.json_response({"status": "ok"})

    async def save_settings(request: web.Request) -> web.Response:
        form_data = await request.post()
        form = {
            key: [str(value) for value in form_data.getall(key)] for key in form_data
        }
        selected_tab = form_tab(form)
        try:
            selected_tab, restart_fields = save_settings_form(
                form,
                config_provider(),
                repository,
            )
        except ValueError as error:
            logger.info(
                f"Web config validation failed from {_remote(request)}: {error}"
            )
            return web.Response(
                text=render_settings_page(
                    config_provider(),
                    query={"tab": selected_tab},
                    error_message=str(error),
                    restart_available=runtime_control is not None,
                ),
                content_type="text/html",
                status=HTTPStatus.BAD_REQUEST,
            )

        logger.info(f"Web config settings saved from {_remote(request)}")
        raise web.HTTPSeeOther(settings_redirect(selected_tab, restart_fields))

    async def reset_settings(request: web.Request) -> web.Response:
        repository.reset_config()
        logger.info(f"Web config settings reset from {_remote(request)}")
        raise web.HTTPSeeOther("/settings?reset=1")

    async def restart_runtime(request: web.Request) -> web.Response:
        if runtime_control is None:
            logger.info(f"Web restart rejected from {_remote(request)}")
            return web.Response(
                text=render_settings_page(
                    config_provider(),
                    query=request.query,
                    error_message="Runtime restart is unavailable in this mode.",
                ),
                content_type="text/html",
                status=HTTPStatus.CONFLICT,
            )
        logger.info(f"Web runtime restart requested from {_remote(request)}")
        runtime_control.request_restart()
        return web.Response(
            text=render_settings_page(
                config_provider(),
                query={"tab": active_tab(request.query)},
                status_message_override=(
                    "Restart requested. The runtime is stopping now."
                ),
            ),
            content_type="text/html",
        )

    app.router.add_get("/", home_page)
    app.router.add_get("/settings", config_page)
    app.router.add_get("/health", health)
    app.router.add_static("/static", static_dir(), name="static")
    app.router.add_post("/settings", save_settings)
    app.router.add_post("/reset", reset_settings)
    app.router.add_post("/restart", restart_runtime)
    register_gesture_routes(
        app,
        config_provider=config_provider,
        browser_video_sink=browser_video_sink,
        browser_audio_sink=browser_audio_sink,
        debug_source=debug_source,
        display_metrics_sink=display_metrics_sink,
        logger=logger,
    )
    register_remote_routes(
        app,
        config_provider=config_provider,
        direct_remote=direct_remote,
        text_input=text_input,
        logger=logger,
    )
    return app


def _remote(request: web.Request) -> str:
    return request.remote or "unknown"
