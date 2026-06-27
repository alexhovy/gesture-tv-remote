import asyncio

from src.application.ports.camera import CameraPort, FrameProcessorPort
from src.application.ports.command_dispatcher import CommandDispatcherPort
from src.application.ports.config_provider import ConfigProviderPort
from src.application.ports.display import DisplayPort
from src.application.ports.frame_source import FrameSourcePort
from src.application.ports.hand_tracker import HandTrackerPort
from src.application.ports.logger import LoggerPort
from src.application.ports.tv_remote import AppVoiceInputRequest, TVRemotePort
from src.application.ports.voice_capture import VoiceCapturePort
from src.application.services.cleanup_coordinator import CleanupCoordinator
from src.application.services.config_reload_coordinator import ConfigReloadCoordinator
from src.application.services.display_debug_coordinator import DisplayDebugCoordinator
from src.application.services.pipeline_metrics import PipelineMetrics
from src.application.services.runtime_loop_coordinator import RuntimeLoopCoordinator
from src.domain.session import GestureSession
from src.shared.config import AppConfig


class GestureRemoteService:
    def __init__(
        self,
        config: AppConfig,
        *,
        remote: TVRemotePort,
        frame_source: FrameSourcePort,
        hand_tracker: HandTrackerPort,
        camera: CameraPort,
        frame_processor: FrameProcessorPort,
        display: DisplayPort,
        voice_capture: VoiceCapturePort,
        command_dispatcher: CommandDispatcherPort,
        logger: LoggerPort,
        metrics: PipelineMetrics,
        config_provider: ConfigProviderPort | None = None,
        gesture_session: GestureSession | None = None,
    ) -> None:
        self._remote = remote
        self._frame_source = frame_source
        self._voice_capture = voice_capture
        self._logger = logger
        self._gesture_session = gesture_session or GestureSession(config)
        self._voice_task: asyncio.Task | None = None
        config_reload = ConfigReloadCoordinator(
            config,
            gesture_session=self._gesture_session,
            voice_capture=voice_capture,
            camera=camera,
            hand_tracker=hand_tracker,
            logger=logger,
            config_provider=config_provider,
        )
        display_debug = DisplayDebugCoordinator(display, logger)
        self._runtime_loop = RuntimeLoopCoordinator(
            frame_source=frame_source,
            hand_tracker=hand_tracker,
            camera=camera,
            frame_processor=frame_processor,
            voice_capture=voice_capture,
            command_dispatcher=command_dispatcher,
            gesture_session=self._gesture_session,
            metrics=metrics,
            logger=logger,
            config_reload=config_reload,
            display_debug=display_debug,
        )
        self._cleanup = CleanupCoordinator(
            remote=remote,
            frame_source=frame_source,
            hand_tracker=hand_tracker,
            display=display,
            command_dispatcher=command_dispatcher,
            logger=logger,
        )

    async def run(self) -> None:
        if not await self._remote.connect():
            self._logger.info("TV connection failed. Exiting.")
            await self._cleanup.cleanup(None)
            return

        if not await asyncio.to_thread(self._frame_source.is_open):
            self._logger.error("Could not open webcam.")
            await self._cleanup.cleanup(None)
            return

        self._remote.set_app_voice_input_handler(self._handle_app_voice_input)
        try:
            self._voice_task = await self._runtime_loop.run(self._voice_task)
        finally:
            await self._cleanup.cleanup(self._voice_task)

    async def _handle_app_voice_input(self, request: AppVoiceInputRequest) -> None:
        context = (
            f"android_app_voice session_id={request.session_id} "
            f"package={request.package_name or 'unknown'}"
        )
        if self._voice_task is not None and not self._voice_task.done():
            self._logger.info(
                "Rejecting Android app voice input because microphone capture "
                f"is already running: {context}"
            )
            request.stream.end()
            return

        self._logger.info(f"Starting Android app voice input capture: {context}")
        self._voice_task = asyncio.create_task(
            self._voice_capture.capture_stream(request.stream, context)
        )
