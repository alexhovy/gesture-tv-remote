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
from src.web.config_forms import config_from_form
from src.web.config_templates import (
    render_config_page,
    reset_status_message,
    saved_status_message,
)
from src.web.control_templates import render_control_page
from src.web.static_files import read_config_css, read_control_css, read_control_js


class BrowserVideoSink(Protocol):
    def submit_frame(self, frame: Any) -> None: ...


class BrowserAudioSink(Protocol):
    async def push_chunk(self, chunk: bytes) -> None: ...


class BrowserDebugSource(Protocol):
    def subscribe(self) -> Any: ...


def create_browser_control_app(
    *,
    repository: ConfigStorePort,
    config_provider: Callable[[], AppConfig],
    video_sink: BrowserVideoSink,
    audio_sink: BrowserAudioSink,
    debug_source: BrowserDebugSource,
    logger: LoggerPort,
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

    async def control_page(request: web.Request) -> web.Response:
        logger.info(f"Web control page viewed from {_remote(request)}")
        return web.Response(
            text=render_control_page(config_provider()),
            content_type="text/html",
        )

    async def config_css(request: web.Request) -> web.Response:
        del request
        return web.Response(text=read_config_css(), content_type="text/css")

    async def control_css(request: web.Request) -> web.Response:
        del request
        return web.Response(text=read_control_css(), content_type="text/css")

    async def control_js(request: web.Request) -> web.Response:
        del request
        return web.Response(
            text=read_control_js(),
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
        logger.info(f"Browser control offer received from {_remote(request)}")

        @peer.on("track")
        def on_track(track) -> None:
            if track.kind == "video":
                task = asyncio.create_task(_consume_video(track, video_sink, logger))
            elif track.kind == "audio":
                task = asyncio.create_task(_consume_audio(track, audio_sink, logger))
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
                    "Browser control peer disconnected: "
                    f"state={peer.connectionState}"
                )

        await peer.setRemoteDescription(
            RTCSessionDescription(sdp=params["sdp"], type=params["type"])
        )
        answer = await peer.createAnswer()
        await peer.setLocalDescription(answer)
        logger.info(f"Browser control offer accepted from {_remote(request)}")
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
    app.router.add_get("/control", control_page)
    app.router.add_get("/health", health)
    app.router.add_get("/static/config.css", config_css)
    app.router.add_get("/static/control.css", control_css)
    app.router.add_get("/static/control.js", control_js)
    app.router.add_post("/settings", save_settings)
    app.router.add_post("/reset", reset_settings)
    app.router.add_post("/api/log/client", client_log)
    app.router.add_post("/api/control/offer", offer)
    app.router.add_get("/api/control/debug", debug_events)
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


def _status_message(query: Any) -> str | None:
    if "saved" in query:
        return saved_status_message()
    if "reset" in query:
        return reset_status_message()
    return None
