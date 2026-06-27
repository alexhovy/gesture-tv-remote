import asyncio
import threading
import time
from typing import Any

from src.application.pipelines import (
    CommandDispatchPipeline,
    DetectionPipeline,
    FrameCapturePipeline,
    GestureDecisionPipeline,
)
from src.application.ports.camera import CameraPort, FrameProcessorPort
from src.application.ports.command_dispatcher import CommandDispatcherPort
from src.application.ports.config_provider import ConfigProviderPort
from src.application.ports.display import DisplayPort
from src.application.ports.frame_source import FrameSourcePort
from src.application.ports.hand_tracker import HandTrackerPort
from src.application.ports.logger import LoggerPort
from src.application.ports.tv_remote import AppVoiceInputRequest, TVRemotePort
from src.application.ports.voice_capture import VoiceCapturePort
from src.application.services.pipeline_metrics import PipelineMetrics
from src.domain.session import GestureSession
from src.shared.config import AppConfig, apply_reloadable_config

CLEANUP_TIMEOUT_SECONDS = 1.0
CONFIG_RELOAD_INTERVAL_SECONDS = 1.0


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
        self._config = config
        self._config_provider = config_provider
        self._last_config_reload_time = 0.0
        self._remote = remote
        self._frame_source = frame_source
        self._hand_tracker = hand_tracker
        self._camera = camera
        self._frame_processor = frame_processor
        self._display = display
        self._voice_capture = voice_capture
        self._command_dispatcher = command_dispatcher
        self._logger = logger
        self._metrics = metrics
        self._gesture_session = gesture_session or GestureSession(config)
        self._voice_task: asyncio.Task | None = None

    async def run(self) -> None:
        if not await self._remote.connect():
            self._logger.info("TV connection failed. Exiting.")
            await self._cleanup(None)
            return

        if not await asyncio.to_thread(self._frame_source.is_open):
            self._logger.error("Could not open webcam.")
            await self._cleanup(None)
            return

        self._remote.set_app_voice_input_handler(self._handle_app_voice_input)
        last_debug_time = 0.0
        last_debug_message = ""
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

        try:
            while True:
                if self._frame_source.failed():
                    self._logger.error("Could not read frame from webcam.")
                    break

                frame = frame_pipeline.latest_frame()
                if frame is None:
                    await asyncio.sleep(0.005)
                    continue

                now = time.monotonic()
                await self._reload_config_if_needed_async(now)
                frame = frame_pipeline.flip_frame(frame)
                detection_frame = frame_pipeline.detection_frame(
                    frame,
                    self._camera,
                )
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

                self._voice_task = await command_pipeline.handle_decision(
                    decision.command_gesture,
                    decision.activated,
                    now,
                    self._voice_task,
                )

                debug_message = self._display.debug_message(
                    decision.debug_message,
                    detection_frame.crop,
                    display_frame.crop,
                    decision.freeze_zoom,
                )
                if (
                    debug_message != last_debug_message
                    or now - last_debug_time >= self._config.debug.log_seconds
                ):
                    self._logger.debug(debug_message)
                    last_debug_message = debug_message
                    last_debug_time = now

                self._display.draw_detected_hands(
                    display_frame.frame,
                    detected_hands,
                    detection_frame.crop,
                    display_frame.crop,
                )
                self._display.draw_pointer_zones(
                    display_frame.frame,
                    decision.pointer_debug,
                    display_frame.crop,
                )
                self._display.draw_volume_zones(
                    display_frame.frame,
                    decision.volume_debug,
                    display_frame.crop,
                )
                if self._display.render(self._config.app_name, display_frame.frame):
                    break

                command_pipeline.record_dispatch_metrics()
                self._metrics.log_if_due(
                    self._logger,
                    now,
                    self._config.debug.verbose_pipeline_diagnostics,
                    self._config.performance.metrics_log_seconds,
                )
                await asyncio.sleep(0)
        finally:
            await self._cleanup(self._voice_task)

    def _reload_config_if_needed(self, now: float) -> None:
        if self._config_provider is None:
            return
        if now - self._last_config_reload_time < CONFIG_RELOAD_INTERVAL_SECONDS:
            return
        self._last_config_reload_time = now

        try:
            latest_config = self._config_provider()
            config = apply_reloadable_config(self._config, latest_config)
        except ValueError as error:
            self._logger.error(f"Config reload skipped: {error}")
            return

        self._apply_reloaded_config(config)

    async def _reload_config_if_needed_async(self, now: float) -> None:
        if self._config_provider is None:
            return
        if now - self._last_config_reload_time < CONFIG_RELOAD_INTERVAL_SECONDS:
            return
        self._last_config_reload_time = now

        try:
            latest_config = await asyncio.to_thread(self._config_provider)
            config = apply_reloadable_config(self._config, latest_config)
        except ValueError as error:
            self._logger.error(f"Config reload skipped: {error}")
            return

        self._apply_reloaded_config(config)

    def _apply_reloaded_config(self, config: AppConfig) -> None:
        if config == self._config:
            return

        self._config = config
        self._gesture_session.update_config(config)
        self._voice_capture.update_config(config)
        self._camera.update_config(config)
        self._hand_tracker.update_config(config)
        self._logger.info("Reloaded live config settings.")

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

    async def _cleanup(self, voice_task: asyncio.Task | None) -> None:
        self._remote.set_app_voice_input_handler(None)
        if voice_task is not None and not voice_task.done():
            voice_task.cancel()
            await self._cleanup_step("voice capture", voice_task)
        await self._cleanup_sync_step("frame source", self._frame_source.close)
        await self._cleanup_sync_step("hand tracker", self._hand_tracker.close)
        self._cleanup_now("display", self._display.close)
        await self._cleanup_step("command dispatcher", self._command_dispatcher.close())
        await self._cleanup_step("TV remote", self._remote.disconnect())

    async def _cleanup_step(self, name: str, awaitable: Any) -> None:
        try:
            await asyncio.wait_for(awaitable, timeout=CLEANUP_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            pass
        except TimeoutError:
            self._logger.error(f"Timed out while cleaning up {name}.")
        except Exception as error:
            self._logger.error(f"Error while cleaning up {name}: {error}")

    async def _cleanup_sync_step(self, name: str, method: Any) -> None:
        done = threading.Event()
        error: list[BaseException] = []

        def run() -> None:
            try:
                method()
            except BaseException as cleanup_error:
                error.append(cleanup_error)
            finally:
                done.set()

        thread = threading.Thread(
            target=run,
            name=f"cleanup-{name.replace(' ', '-')}",
            daemon=True,
        )
        thread.start()
        deadline = time.monotonic() + CLEANUP_TIMEOUT_SECONDS
        while not done.is_set() and time.monotonic() < deadline:
            await asyncio.sleep(0.01)

        if not done.is_set():
            self._logger.error(f"Timed out while cleaning up {name}.")
            return

        if error:
            self._logger.error(f"Error while cleaning up {name}: {error[0]}")

    def _cleanup_now(self, name: str, method: Any) -> None:
        try:
            method()
        except Exception as error:
            self._logger.error(f"Error while cleaning up {name}: {error}")
