import asyncio
import sys
from dataclasses import dataclass

from aiohttp import web

from src.application.ports.config_provider import ConfigProviderPort
from src.application.services.gesture_remote_service import GestureRemoteService
from src.infrastructure.audio.browser_voice_capture import (
    BrowserAudioSource,
    BrowserVoiceCapture,
)
from src.infrastructure.camera.browser_frame_source import BrowserFrameSource
from src.infrastructure.camera.camera_zoom import CameraZoomController
from src.infrastructure.camera.frame_processor import OpenCvFrameProcessor
from src.infrastructure.camera.headless_display import HeadlessDisplay
from src.infrastructure.hand_tracking.hand_tracking import MediaPipeHandTracker
from src.infrastructure.hand_tracking.model_store import MediaPipeModelStore
from src.runtime.builders.config import build_config_provider, build_config_repository
from src.runtime.builders.tv import build_tv_dependencies
from src.shared.config import load_config_from_env
from src.shared.logging import AppLogger, configure_app_logging
from src.web.control_app import create_browser_control_app


@dataclass(frozen=True)
class BrowserControlRuntime:
    service: GestureRemoteService
    server: "BrowserControlServer"
    audio_source: BrowserAudioSource


class BrowserControlServer:
    def __init__(
        self,
        app: web.Application,
        host: str,
        port: int,
        logger: AppLogger,
    ) -> None:
        self._app = app
        self._host = host
        self._port = port
        self._logger = logger
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
        self._logger.info(
            f"Browser control listening on http://{self._host}:{self._port}/control"
        )

    async def stop(self) -> None:
        if self._runner is None:
            return
        await self._runner.cleanup()
        self._runner = None
        self._site = None


async def main() -> None:
    runtime = build_browser_control_runtime(create_config_provider())
    await runtime.server.start()
    try:
        await runtime.service.run()
    finally:
        await runtime.audio_source.close()
        await runtime.server.stop()


def build_browser_control_runtime(
    config_provider: ConfigProviderPort | None = None,
) -> BrowserControlRuntime:
    provider = config_provider or create_config_provider()
    config = provider()
    logger = AppLogger()
    tv_deps = build_tv_dependencies(config, logger)
    frame_source = BrowserFrameSource()
    audio_source = BrowserAudioSource()

    MediaPipeModelStore(config).ensure_model()
    service = GestureRemoteService(
        config,
        remote=tv_deps.remote,
        frame_source=frame_source,
        hand_tracker=MediaPipeHandTracker(config),
        camera=CameraZoomController(config),
        frame_processor=OpenCvFrameProcessor(),
        display=HeadlessDisplay(),
        voice_capture=BrowserVoiceCapture(
            tv_deps.remote,
            audio_source,
            config,
            logger,
        ),
        command_dispatcher=tv_deps.command_dispatcher,
        logger=logger,
        metrics=tv_deps.metrics,
        config_provider=provider,
    )
    app = create_browser_control_app(
        config_provider=provider,
        video_sink=frame_source,
        audio_sink=audio_source,
        logger=logger,
    )
    return BrowserControlRuntime(
        service=service,
        server=BrowserControlServer(app, config.web.host, config.web.port, logger),
        audio_source=audio_source,
    )


def create_config_provider() -> ConfigProviderPort:
    bootstrap_config = load_config_from_env()
    repository = build_config_repository(bootstrap_config)
    return build_config_provider(repository)


def run(configure_logging: bool = True) -> None:
    if configure_logging:
        configure_app_logging()
    _configure_windows_event_loop_policy()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        AppLogger().info("Browser control stopped.")


def _configure_windows_event_loop_policy() -> None:
    if sys.platform != "win32":
        return

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
