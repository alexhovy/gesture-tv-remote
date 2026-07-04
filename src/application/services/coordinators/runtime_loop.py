import asyncio
import time

from src.application.pipelines import (
    CommandDispatchPipeline,
    DetectionPipeline,
    FrameCapturePipeline,
    GestureDecisionPipeline,
)
from src.application.ports.camera import CameraPort, FrameProcessorPort
from src.application.ports.command_dispatcher import CommandDispatcherPort
from src.application.ports.display_metrics import DisplayMetricsPort
from src.application.ports.frame_source import FrameSourcePort
from src.application.ports.hand_tracker import HandTrackerPort
from src.application.ports.logger import LoggerPort
from src.application.ports.voice_capture import VoiceCapturePort
from src.application.services.coordinators.config_reload import ConfigReloadCoordinator
from src.application.services.coordinators.display_debug import DisplayDebugCoordinator
from src.application.services.pipeline_metrics import PipelineMetrics
from src.domain.session import GestureSession


class RuntimeLoopCoordinator:
    def __init__(
        self,
        *,
        frame_source: FrameSourcePort,
        hand_tracker: HandTrackerPort,
        camera: CameraPort,
        frame_processor: FrameProcessorPort,
        voice_capture: VoiceCapturePort,
        command_dispatcher: CommandDispatcherPort,
        gesture_session: GestureSession,
        metrics: PipelineMetrics,
        logger: LoggerPort,
        config_reload: ConfigReloadCoordinator,
        display_debug: DisplayDebugCoordinator,
        display_metrics: DisplayMetricsPort | None = None,
    ) -> None:
        self._frame_source = frame_source
        self._hand_tracker = hand_tracker
        self._camera = camera
        self._frame_processor = frame_processor
        self._voice_capture = voice_capture
        self._command_dispatcher = command_dispatcher
        self._gesture_session = gesture_session
        self._metrics = metrics
        self._logger = logger
        self._config_reload = config_reload
        self._display_debug = display_debug
        self._display_metrics = display_metrics
        self._stop_requested = False

    async def run(self, voice_task: asyncio.Task | None = None) -> asyncio.Task | None:
        frame_pipeline = FrameCapturePipeline(
            self._frame_processor,
            self._frame_source,
            self._metrics,
        )
        detection_pipeline = DetectionPipeline(self._metrics)
        gesture_pipeline = GestureDecisionPipeline(
            self._gesture_session,
            self._camera,
            self._metrics,
            self._display_metrics,
        )
        command_pipeline = CommandDispatchPipeline(
            self._gesture_session,
            self._voice_capture,
            self._command_dispatcher,
            self._metrics,
            self._logger,
        )

        self._command_dispatcher.start()
        frame_pipeline.start()

        while not self._stop_requested:
            if self._frame_source.failed():
                self._logger.error("Could not read frame from webcam.")
                break

            frame = frame_pipeline.latest_frame()
            if frame is None:
                await asyncio.sleep(0.005)
                continue

            now = time.monotonic()
            config = await self._config_reload.reload_if_needed(now)
            frame = frame_pipeline.flip_frame(frame)
            detection_frame = frame_pipeline.detection_frame(frame, self._camera)
            hand_states, detected_hands = detection_pipeline.detect_hands(
                self._hand_tracker,
                detection_frame.frame,
            )

            display_frame = frame_pipeline.display_frame(frame, self._camera)
            decision = gesture_pipeline.evaluate(
                hand_states,
                detection_frame.crop,
                display_frame.crop,
                now,
            )

            voice_task = await command_pipeline.handle_decision(
                decision.command_gesture,
                decision.activated,
                now,
                voice_task,
            )

            if self._display_debug.render(
                config=config,
                frame=display_frame.frame,
                detected_hands=detected_hands,
                detection_crop=detection_frame.crop,
                display_crop=display_frame.crop,
                decision=decision,
                now=now,
            ):
                break

            command_pipeline.record_dispatch_metrics()
            self._metrics.log_if_due(
                self._logger,
                now,
                config.debug.verbose_pipeline_diagnostics,
                config.performance.metrics_log_seconds,
            )
            await asyncio.sleep(0)

        return voice_task

    def stop(self) -> None:
        self._stop_requested = True
