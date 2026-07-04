import asyncio
import contextlib
from collections.abc import Callable
from http import HTTPStatus
from typing import Any, Protocol

from aiohttp import web
from aiortc import RTCSessionDescription

from src.application.ports.logger import LoggerPort
from src.shared.config import AppConfig
from src.web.gesture.templates import render_gesture_page


class BrowserVideoSink(Protocol):
    def submit_frame(self, frame: Any) -> None: ...


class BrowserAudioSink(Protocol):
    async def push_chunk(self, chunk: bytes) -> None: ...


class BrowserDebugSource(Protocol):
    def subscribe(self) -> Any: ...


class BrowserDisplayMetricsSink(Protocol):
    def update_size(self, width: float, height: float) -> None: ...


PEERS_KEY = web.AppKey("peers", set[Any])
TRACK_TASKS_KEY = web.AppKey("track_tasks", set[asyncio.Task[Any]])


def register_gesture_routes(
    app: web.Application,
    *,
    config_provider: Callable[[], AppConfig],
    browser_video_sink: BrowserVideoSink,
    browser_audio_sink: BrowserAudioSink,
    debug_source: BrowserDebugSource,
    logger: LoggerPort,
    display_metrics_sink: BrowserDisplayMetricsSink | None = None,
) -> None:
    app[PEERS_KEY] = set()
    app[TRACK_TASKS_KEY] = set()

    async def gesture_page(request: web.Request) -> web.Response:
        logger.info(f"Web gesture page viewed from {_remote(request)}")
        return web.Response(
            text=render_gesture_page(config_provider()),
            content_type="text/html",
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
        app[PEERS_KEY].add(peer)
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
            app[TRACK_TASKS_KEY].add(task)
            task.add_done_callback(app[TRACK_TASKS_KEY].discard)

        @peer.on("connectionstatechange")
        async def on_connectionstatechange() -> None:
            if peer.connectionState in {"failed", "closed", "disconnected"}:
                await peer.close()
                app[PEERS_KEY].discard(peer)
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
        track_tasks = app[TRACK_TASKS_KEY].copy()
        for task in track_tasks:
            task.cancel()
        for task in track_tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await asyncio.gather(
            *(peer.close() for peer in app[PEERS_KEY].copy()),
            return_exceptions=True,
        )
        app[PEERS_KEY].clear()

    app.router.add_get("/gesture", gesture_page)
    app.router.add_post("/api/log/client", client_log)
    app.router.add_post("/api/gesture/layout", layout_metrics)
    app.router.add_post("/api/gesture/offer", offer)
    app.router.add_get("/api/gesture/debug", debug_events)
    app.on_shutdown.append(cleanup)


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
