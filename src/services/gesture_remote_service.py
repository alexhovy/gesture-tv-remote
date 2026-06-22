import asyncio
import threading
import time
from collections.abc import Callable
from typing import Any

import cv2

from src.domain.landmarks import hand_center
from src.domain.session import GestureSession
from src.infrastructure.camera.camera_zoom import CameraZoomController
from src.infrastructure.camera.frame_source import LatestFrameSource
from src.infrastructure.camera.video_preprocessing import CropRect
from src.infrastructure.hand_tracking.hand_model import download_model_if_missing
from src.infrastructure.hand_tracking.hand_tracking import MediaPipeHandTracker
from src.infrastructure.tv.tv_remote_factory import create_tv_remote_client
from src.services.voice_capture import VoiceCaptureService
from src.services.remote_command_dispatcher import RemoteCommandDispatcher
from src.services.pipeline_metrics import PipelineMetrics
from src.services.pipelines import (
    CommandDispatchPipeline,
    DetectionPipeline,
    DisplayPipeline,
    FrameCapturePipeline,
    GestureDecisionPipeline,
)
from src.shared.config import AppConfig, apply_reloadable_config
from src.shared.logging import AppLogger


CLEANUP_TIMEOUT_SECONDS = 1.0
CONFIG_RELOAD_INTERVAL_SECONDS = 1.0
SECONDARY_STABILIZE_FRAMES = 4
PRECISION_MIN_HAND_SIZE = 0.10
PRECISION_CROP_MARGIN = 0.08


class DetectionCropModeTracker:
    def __init__(self, secondary_stabilize_frames: int = SECONDARY_STABILIZE_FRAMES) -> None:
        self._secondary_stabilize_frames = max(1, secondary_stabilize_frames)
        self.secondary_stable_frames = 0
        self.mode = "acquisition"
        self.precision_blocked_reason = "no_secondary"

    @property
    def precise(self) -> bool:
        return False

    def record_decision(self, decision: Any, current_crop: CropRect) -> None:
        if decision.activated and len(decision.zoom_landmarks) > 1:
            self.secondary_stable_frames += 1
        else:
            self.secondary_stable_frames = 0

        if self.secondary_stable_frames <= 0:
            self.mode = "acquisition"
            self.precision_blocked_reason = "no_secondary"
        elif self.secondary_stable_frames < self._secondary_stabilize_frames:
            self.mode = "stabilizing"
            self.precision_blocked_reason = "settling_secondary"
        else:
            self.precision_blocked_reason = _precision_blocked_reason(
                decision.zoom_landmarks,
                current_crop,
            )
            if self.precision_blocked_reason == "none":
                self.precision_blocked_reason = "wide_tracking"
            self.mode = "stabilizing"


class GestureRemoteService:
    def __init__(
        self,
        config: AppConfig,
        config_provider: Callable[[], AppConfig] | None = None,
    ) -> None:
        self._config = config
        self._config_provider = config_provider
        self._last_config_reload_time = 0.0
        self._remote = create_tv_remote_client(config)
        self._voice_capture = VoiceCaptureService(self._remote, config)
        self._gesture_session = GestureSession(config)
        self._logger = AppLogger()
        self._command_dispatcher = RemoteCommandDispatcher(self._remote, self._logger)

    async def run(self) -> None:
        if not await self._remote.connect():
            self._logger.info("TV connection failed. Exiting.")
            return

        cap = await asyncio.to_thread(cv2.VideoCapture, self._config.camera.webcam_index)
        if not await asyncio.to_thread(cap.isOpened):
            self._logger.error("Could not open webcam.")
            await asyncio.to_thread(cap.release)
            await self._remote.disconnect()
            return

        hand_tracker = None
        voice_task = None
        frame_source = LatestFrameSource(cap)
        metrics = PipelineMetrics(self._config.tv.adapter)
        last_debug_time = 0.0
        last_debug_message = ""
        detection_crop_mode = DetectionCropModeTracker()
        zoom_controller = CameraZoomController(self._config)
        frame_pipeline = FrameCapturePipeline(frame_source, metrics)
        detection_pipeline = DetectionPipeline(metrics)
        gesture_pipeline = GestureDecisionPipeline(
            self._gesture_session,
            zoom_controller,
            metrics,
        )
        display_pipeline = DisplayPipeline(self._logger)
        command_pipeline = CommandDispatchPipeline(
            self._gesture_session,
            self._voice_capture,
            self._command_dispatcher,
            metrics,
            self._logger,
        )
        # One bounded async worker sends TV commands so network stalls do not block
        # camera capture, MediaPipe submission, or display rendering.
        self._command_dispatcher.start()
        # One camera thread continuously reads frames and keeps only the newest
        # frame; the async loop drops stale versions instead of building backlog.
        frame_pipeline.start()

        try:
            await asyncio.to_thread(download_model_if_missing, self._config)
            hand_tracker = MediaPipeHandTracker(self._config)

            while True:
                if frame_source.failed():
                    self._logger.error("Could not read frame from webcam.")
                    break

                frame = frame_pipeline.latest_frame()
                if frame is None:
                    await asyncio.sleep(0.005)
                    continue

                now = time.monotonic()
                await self._reload_config_if_needed_async(now, zoom_controller, hand_tracker)
                frame = frame_pipeline.flip_frame(frame)
                detection_mode = detection_crop_mode.mode
                detection_frame = frame_pipeline.detection_frame(
                    frame,
                    zoom_controller,
                    detection_crop_mode.precise,
                )
                hand_states, detected_hands = detection_pipeline.detect_hands(
                    hand_tracker,
                    detection_frame.frame,
                )

                display_frame = frame_pipeline.display_frame(frame, zoom_controller)
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

                detection_crop_mode.record_decision(decision, display_frame.crop)
                debug_message = display_pipeline.debug_message(
                    decision.debug_message,
                    detection_frame.crop,
                    display_frame.crop,
                    detection_mode,
                    detection_crop_mode.secondary_stable_frames,
                    detection_crop_mode.precision_blocked_reason,
                    decision.freeze_zoom,
                )
                if (
                    debug_message != last_debug_message
                    or now - last_debug_time >= self._config.debug.log_seconds
                ):
                    self._logger.debug(debug_message)
                    last_debug_message = debug_message
                    last_debug_time = now

                display_pipeline.draw_detected_hands(
                    display_frame.frame,
                    detected_hands,
                    detection_frame.crop,
                    display_frame.crop,
                )
                display_pipeline.draw_pointer_zones(
                    display_frame.frame,
                    decision.pointer_debug,
                    display_frame.crop,
                )
                if display_pipeline.render(self._config.app_name, display_frame.frame):
                    break

                command_pipeline.record_dispatch_metrics()
                metrics.log_if_due(
                    self._logger,
                    now,
                    self._config.debug.verbose_pipeline_diagnostics,
                    self._config.performance.metrics_log_seconds,
                )
                await asyncio.sleep(0)
        finally:
            await self._cleanup(voice_task, hand_tracker, cap, frame_source)

    def _reload_config_if_needed(
        self,
        now: float,
        zoom_controller: CameraZoomController,
        hand_tracker: MediaPipeHandTracker | None,
    ) -> None:
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

        self._apply_reloaded_config(config, zoom_controller, hand_tracker)

    async def _reload_config_if_needed_async(
        self,
        now: float,
        zoom_controller: CameraZoomController,
        hand_tracker: MediaPipeHandTracker | None,
    ) -> None:
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

        self._apply_reloaded_config(config, zoom_controller, hand_tracker)

    def _apply_reloaded_config(
        self,
        config: AppConfig,
        zoom_controller: CameraZoomController,
        hand_tracker: MediaPipeHandTracker | None,
    ) -> None:
        if config == self._config:
            return

        self._config = config
        self._gesture_session.update_config(config)
        self._voice_capture.update_config(config)
        zoom_controller.update_config(config)
        if hand_tracker is not None:
            hand_tracker.update_config(config)
        self._logger.info("Reloaded live config settings.")

    async def _cleanup(
        self,
        voice_task: asyncio.Task | None,
        hand_tracker: MediaPipeHandTracker | None,
        cap: Any,
        frame_source: LatestFrameSource | None,
    ) -> None:
        if voice_task is not None and not voice_task.done():
            voice_task.cancel()
            await self._cleanup_step("voice capture", voice_task)
        if frame_source is not None:
            await self._cleanup_sync_step("frame source", frame_source.stop)
        if hand_tracker is not None:
            await self._cleanup_sync_step("hand tracker", hand_tracker.close)
        await self._cleanup_sync_step("camera", cap.release)
        self._cleanup_now("OpenCV windows", cv2.destroyAllWindows)
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


def _precision_blocked_reason(
    landmarks_by_hand: list[list[Any]],
    current_crop: CropRect,
) -> str:
    hand_landmarks = [landmarks for landmarks in landmarks_by_hand if landmarks]
    if len(hand_landmarks) < 2:
        return "no_secondary"

    hand_sizes = [hand_center(landmarks)[2] for landmarks in hand_landmarks]
    if any(size < PRECISION_MIN_HAND_SIZE for size in hand_sizes):
        return "hand_too_small"

    hand_bounds = [_landmark_bounds(landmarks) for landmarks in hand_landmarks]
    if not _bounds_fit_crop(hand_bounds, current_crop, PRECISION_CROP_MARGIN):
        return "crop_too_tight"

    return "none"


def _landmark_bounds(landmarks: list[Any]) -> CropRect:
    min_x = min(landmark.x for landmark in landmarks)
    min_y = min(landmark.y for landmark in landmarks)
    max_x = max(landmark.x for landmark in landmarks)
    max_y = max(landmark.y for landmark in landmarks)
    return CropRect(min_x, min_y, max_x - min_x, max_y - min_y)


def _bounds_fit_crop(
    hand_bounds: list[CropRect],
    crop: CropRect,
    margin: float,
) -> bool:
    if crop.width <= 0 or crop.height <= 0:
        return False

    min_x = min(bounds.x for bounds in hand_bounds)
    min_y = min(bounds.y for bounds in hand_bounds)
    max_x = max(bounds.x + bounds.width for bounds in hand_bounds)
    max_y = max(bounds.y + bounds.height for bounds in hand_bounds)
    left = (min_x - crop.x) / crop.width
    right = (max_x - crop.x) / crop.width
    top = (min_y - crop.y) / crop.height
    bottom = (max_y - crop.y) / crop.height
    return (
        left >= margin
        and right <= 1 - margin
        and top >= margin
        and bottom <= 1 - margin
    )
