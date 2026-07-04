import asyncio
import contextlib
from collections.abc import Callable
from http import HTTPStatus
from typing import Any, Protocol

from aiohttp import web
from aiortc import RTCSessionDescription

from src.application.ports.config_provider import ConfigStorePort
from src.application.ports.logger import LoggerPort
from src.shared.config import AppConfig
from src.web.assets import (
    read_config_css,
    read_gesture_css,
    read_gesture_js,
    read_remote_css,
    read_remote_js,
)
from src.web.gesture.templates import render_gesture_page
from src.web.remote.templates import render_remote_page
from src.web.settings.forms import config_from_form
from src.web.settings.templates import (
    render_config_page,
    reset_status_message,
    saved_status_message,
)


class BrowserVideoSink(Protocol):
    def submit_frame(self, frame: Any) -> None: ...


class BrowserAudioSink(Protocol):
    async def push_chunk(self, chunk: bytes) -> None: ...


class BrowserDebugSource(Protocol):
    def subscribe(self) -> Any: ...


class BrowserDisplayMetricsSink(Protocol):
    def update_size(self, width: float, height: float) -> None: ...


class DirectRemote(Protocol):
    def supported_commands(self) -> tuple[str, ...]: ...

    def dispatch(self, command: str) -> Any: ...


def create_web_app(
    *,
    repository: ConfigStorePort,
    config_provider: Callable[[], AppConfig],
    browser_video_sink: BrowserVideoSink,
    browser_audio_sink: BrowserAudioSink,
    debug_source: BrowserDebugSource,
    direct_remote: DirectRemote,
    logger: LoggerPort,
    display_metrics_sink: BrowserDisplayMetricsSink | None = None,
) -> web.Application:
    app = web.Application()
    app["peers"] = set()
    app["track_tasks"] = set()

    async def config_page(request: web.Request) -> web.Response:
        logger.info(f"Web config page viewed from {_remote(request)}")
        return web.Response(
            text=render_config_page(
                config_provider(),
                status_message=_status_message(request.query),
            ),
            content_type="text/html",
        )

    async def gesture_page(request: web.Request) -> web.Response:
        logger.info(f"Web gesture page viewed from {_remote(request)}")
        return web.Response(
            text=render_gesture_page(config_provider()),
            content_type="text/html",
        )

    async def remote_page(request: web.Request) -> web.Response:
        logger.info(f"Web remote page viewed from {_remote(request)}")
        return web.Response(
            text=render_remote_page(config_provider()),
            content_type="text/html",
        )

    async def config_css(request: web.Request) -> web.Response:
        del request
        return web.Response(text=read_config_css(), content_type="text/css")

    async def gesture_css(request: web.Request) -> web.Response:
        del request
        return web.Response(text=read_gesture_css(), content_type="text/css")

    async def gesture_js(request: web.Request) -> web.Response:
        del request
        return web.Response(
            text=read_gesture_js(),
            content_type="application/javascript",
        )

    async def remote_css(request: web.Request) -> web.Response:
        del request
        return web.Response(text=read_remote_css(), content_type="text/css")

    async def remote_js(request: web.Request) -> web.Response:
        del request
        return web.Response(
            text=read_remote_js(),
            content_type="application/javascript",
        )

    async def health(request: web.Request) -> web.Response:
        del request
        return web.json_response({"status": "ok"})

    async def save_settings(request: web.Request) -> web.Response:
        form_data = await request.post()
        form = {
            key: [str(value) for value in form_data.getall(key)] for key in form_data
        }
        try:
            config = config_from_form(form, config_provider())
            repository.save_config(config)
        except ValueError as error:
            logger.info(
                f"Web config validation failed from {_remote(request)}: {error}"
            )
            return web.Response(
                text=render_config_page(
                    config_provider(),
                    error_message=str(error),
                ),
                content_type="text/html",
                status=HTTPStatus.BAD_REQUEST,
            )

        logger.info(f"Web config settings saved from {_remote(request)}")
        raise web.HTTPSeeOther("/?saved=1")

    async def reset_settings(request: web.Request) -> web.Response:
        repository.reset_config()
        logger.info(f"Web config settings reset from {_remote(request)}")
        raise web.HTTPSeeOther("/?reset=1")

    async def remote_capabilities(request: web.Request) -> web.Response:
        del request
        return web.json_response(
            {"supportedCommands": list(direct_remote.supported_commands())}
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

    async def client_log(request: web.Request) -> web.Response:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        level = str(payload.get("level", "info")).lower()
        message = str(payload.get("message", "browser event"))
        details = payload.get("details", {})
        log_message = (
            f"Browser client {message} from {_remote(request)} details={details}"
        )
        if level == "error":
            logger.error(log_message)
        elif level == "debug":
            logger.debug(log_message)
        else:
            logger.info(log_message)
        return web.json_response({"status": "ok"})

    async def layout_metrics(request: web.Request) -> web.Response:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        width = _float(payload.get("width"))
        height = _float(payload.get("height"))
        if display_metrics_sink is not None:
            display_metrics_sink.update_size(width, height)
        return web.json_response({"status": "ok"})

    async def debug_events(request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse(
            status=HTTPStatus.OK,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        await response.prepare(request)
        logger.info(f"Browser debug stream connected from {_remote(request)}")
        try:
            async for payload in debug_source.subscribe():
                await response.write(f"data: {payload}\n\n".encode())
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        finally:
            logger.info(f"Browser debug stream disconnected from {_remote(request)}")
        return response

    async def offer(request: web.Request) -> web.Response:
        from aiortc import RTCPeerConnection

        params = await request.json()
        peer = RTCPeerConnection()
        app["peers"].add(peer)
        logger.info(f"Browser gesture offer received from {_remote(request)}")

        @peer.on("track")
        def on_track(track) -> None:
            if track.kind == "video":
                task = asyncio.create_task(
                    _consume_video(track, browser_video_sink, logger)
                )
            elif track.kind == "audio":
                task = asyncio.create_task(
                    _consume_audio(track, browser_audio_sink, logger)
                )
            else:
                return
            app["track_tasks"].add(task)
            task.add_done_callback(app["track_tasks"].discard)

        @peer.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            if peer.connectionState in {"failed", "closed", "disconnected"}:
                await peer.close()
                app["peers"].discard(peer)
                logger.info(
                    "Browser gesture peer disconnected: "
                    f"state={peer.connectionState}"
                )

        await peer.setRemoteDescription(
            RTCSessionDescription(sdp=params["sdp"], type=params["type"])
        )
        answer = await peer.createAnswer()
        await peer.setLocalDescription(answer)
        logger.info(f"Browser gesture offer accepted from {_remote(request)}")
        return web.json_response(
            {
                "sdp": peer.localDescription.sdp,
                "type": peer.localDescription.type,
            }
        )

    async def cleanup(app: web.Application) -> None:
        track_tasks = set(app["track_tasks"])
        for task in track_tasks:
            task.cancel()
        for task in track_tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await asyncio.gather(
            *(peer.close() for peer in set(app["peers"])),
            return_exceptions=True,
        )
        app["peers"].clear()

    app.router.add_get("/", config_page)
    app.router.add_get("/settings", config_page)
    app.router.add_get("/gesture", gesture_page)
    app.router.add_get("/remote", remote_page)
    app.router.add_get("/health", health)
    app.router.add_get("/static/config.css", config_css)
    app.router.add_get("/static/gesture.css", gesture_css)
    app.router.add_get("/static/gesture.js", gesture_js)
    app.router.add_get("/static/remote.css", remote_css)
    app.router.add_get("/static/remote.js", remote_js)
    app.router.add_post("/settings", save_settings)
    app.router.add_post("/reset", reset_settings)
    app.router.add_post("/api/log/client", client_log)
    app.router.add_get("/api/remote/capabilities", remote_capabilities)
    app.router.add_post("/api/remote/commands", remote_command)
    app.router.add_post("/api/gesture/layout", layout_metrics)
    app.router.add_post("/api/gesture/offer", offer)
    app.router.add_get("/api/gesture/debug", debug_events)
    app.on_shutdown.append(cleanup)
    return app


async def _consume_video(
    track,
    video_sink: BrowserVideoSink,
    logger: LoggerPort,
) -> None:
    logger.info("Browser video track started.")
    try:
        while True:
            frame = await track.recv()
            video_sink.submit_frame(frame.to_ndarray(format="bgr24"))
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.info(f"Browser video track stopped: {error}")


async def _consume_audio(
    track,
    audio_sink: BrowserAudioSink,
    logger: LoggerPort,
) -> None:
    logger.info("Browser audio track started.")
    try:
        from av.audio.resampler import AudioResampler

        resampler = AudioResampler(format="s16", layout="mono", rate=8000)
        while True:
            frame = await track.recv()
            resampled_frames = resampler.resample(frame)
            for resampled_frame in resampled_frames:
                await audio_sink.push_chunk(bytes(resampled_frame.planes[0]))
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.info(f"Browser audio track stopped: {error}")


def _remote(request: web.Request) -> str:
    return request.remote or "unknown"


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _status_message(query: Any) -> str | None:
    if "saved" in query:
        return saved_status_message()
    if "reset" in query:
        return reset_status_message()
    return None
