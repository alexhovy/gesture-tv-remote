import asyncio
import contextlib
from collections.abc import Callable
from typing import Any, Protocol

from aiohttp import web
from aiortc import RTCSessionDescription

from src.application.ports.logger import LoggerPort
from src.shared.config import AppConfig
from src.web.control_templates import render_control_page
from src.web.static_files import read_control_css, read_control_js


class BrowserVideoSink(Protocol):
    def submit_frame(self, frame: Any) -> None: ...


class BrowserAudioSink(Protocol):
    async def push_chunk(self, chunk: bytes) -> None: ...


def create_browser_control_app(
    *,
    config_provider: Callable[[], AppConfig],
    video_sink: BrowserVideoSink,
    audio_sink: BrowserAudioSink,
    logger: LoggerPort,
) -> web.Application:
    app = web.Application()
    app["peers"] = set()
    app["track_tasks"] = set()

    async def control_page(request: web.Request) -> web.Response:
        del request
        return web.Response(
            text=render_control_page(config_provider()),
            content_type="text/html",
        )

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

    async def offer(request: web.Request) -> web.Response:
        from aiortc import RTCPeerConnection

        params = await request.json()
        peer = RTCPeerConnection()
        app["peers"].add(peer)
        logger.info("Browser control peer connected.")

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

    app.router.add_get("/", control_page)
    app.router.add_get("/control", control_page)
    app.router.add_get("/health", health)
    app.router.add_get("/static/control.css", control_css)
    app.router.add_get("/static/control.js", control_js)
    app.router.add_post("/api/control/offer", offer)
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
