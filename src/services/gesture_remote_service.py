import asyncio
import threading
import time
from collections.abc import Callable
from typing import Any

import cv2

from src.domain.commands import GESTURE_TO_COMMAND
from src.domain.constants import (
    GESTURE_MIC,
)
from src.domain.session import GestureSession
from src.domain.session_types import GestureDecision, HandState
from src.infrastructure.camera.camera_zoom import CameraZoomController
from src.infrastructure.camera.frame_source import LatestFrameSource
from src.infrastructure.hand_tracking.hand_model import download_model_if_missing
from src.infrastructure.hand_tracking.hand_tracking import DetectedHand, MediaPipeHandTracker
from src.infrastructure.camera.landmark_projection import (
    hand_states_to_original_space,
    landmarks_to_crop_space,
    landmarks_to_original_space,
)
from src.infrastructure.tv.tv_remote_factory import create_tv_remote_client
from src.infrastructure.camera.video_preprocessing import (
    CropRect,
    CroppedFrame,
    apply_crop,
    center_crop_for_zoom,
)
from src.infrastructure.camera.video_overlay import draw_simple_landmarks
from src.services.voice_capture import VoiceCaptureService
from src.services.remote_command_dispatcher import RemoteCommandDispatcher
from src.shared.config import AppConfig, apply_reloadable_config
from src.shared.logging import AppLogger


CLEANUP_TIMEOUT_SECONDS = 1.0
CONFIG_RELOAD_INTERVAL_SECONDS = 1.0


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
        last_debug_time = 0.0
        last_debug_message = ""
        zoom_controller = CameraZoomController(self._config)
        frame_pipeline = FramePipeline()
        gesture_pipeline = GesturePipeline(self._gesture_session, zoom_controller)
        display_pipeline = DisplayPipeline(self._logger)
        command_pipeline = CommandPipeline(
            self._gesture_session,
            self._voice_capture,
            self._command_dispatcher,
            self._logger,
        )
        self._command_dispatcher.start()
        frame_source.start()

        try:
            await asyncio.to_thread(download_model_if_missing, self._config)
            hand_tracker = MediaPipeHandTracker(self._config)

            while True:
                if frame_source.failed():
                    self._logger.error("Could not read frame from webcam.")
                    break

                frame = frame_source.latest()
                if frame is None:
                    await asyncio.sleep(0.005)
                    continue

                now = time.monotonic()
                await self._reload_config_if_needed_async(now, zoom_controller, hand_tracker)
                frame = frame_pipeline.flip_frame(frame)
                detection_frame = frame_pipeline.detection_frame(
                    frame,
                    self._config.camera.zoom,
                )
                hand_states, detected_hands = frame_pipeline.detect_hands(
                    hand_tracker,
                    detection_frame.frame,
                )

                decision = gesture_pipeline.evaluate(
                    hand_states,
                    detection_frame.crop,
                    now,
                )

                voice_task = await command_pipeline.handle_decision(
                    decision.command_gesture,
                    decision.activated,
                    now,
                    voice_task,
                )

                display_frame = frame_pipeline.display_frame(frame, zoom_controller)
                debug_message = display_pipeline.debug_message(
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

                display_pipeline.draw_detected_hands(
                    display_frame.frame,
                    detected_hands,
                    detection_frame.crop,
                    display_frame.crop,
                )
                if display_pipeline.render(self._config.app_name, display_frame.frame):
                    break

                await asyncio.sleep(0)
        finally:
            await self._cleanup(voice_task, hand_tracker, cap, frame_source)

    @staticmethod
    def _flip_frame(frame: Any) -> Any:
        return cv2.flip(frame, 1)

    @staticmethod
    def _detection_frame(frame: Any, camera_zoom: float) -> CroppedFrame:
        return apply_crop(frame, center_crop_for_zoom(camera_zoom))

    @staticmethod
    def _display_frame(frame: Any, zoom_controller: CameraZoomController) -> CroppedFrame:
        return apply_crop(frame, zoom_controller.current_crop())

    @staticmethod
    def _detect_hands(
        hand_tracker: MediaPipeHandTracker,
        frame: Any,
    ) -> tuple[list[HandState], list[DetectedHand]]:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return hand_tracker.detect(rgb_frame, int(time.monotonic() * 1000))

    @staticmethod
    def _draw_detected_hands(
        frame: Any,
        detected_hands: list[DetectedHand],
        source_crop: CropRect,
        display_crop: CropRect,
    ) -> None:
        for detected_hand in detected_hands:
            original_landmarks = landmarks_to_original_space(
                detected_hand.landmarks,
                source_crop,
            )
            draw_simple_landmarks(
                frame,
                landmarks_to_crop_space(original_landmarks, display_crop),
            )

    def _update_zoom(
        self,
        zoom_controller: CameraZoomController,
        zoom_landmarks: list[list[Any]],
        activated: bool,
        primary_temporarily_lost: bool,
        freeze_zoom: bool = False,
    ) -> bool:
        if primary_temporarily_lost or freeze_zoom:
            return False

        full_frame_crop = CropRect(0.0, 0.0, 1.0, 1.0)
        if not activated:
            return zoom_controller.update([], full_frame_crop)

        return zoom_controller.update(zoom_landmarks, full_frame_crop)

    @staticmethod
    def _debug_message(
        decision_debug_message: str,
        detection_crop: CropRect,
        display_crop: CropRect,
        zoom_frozen: bool = False,
    ) -> str:
        return (
            f"{decision_debug_message} "
            f"detection_crop={_debug_crop(detection_crop)} "
            f"display_crop={_debug_crop(display_crop)} "
            f"zoom_frozen={zoom_frozen}"
        )

    async def _handle_decision(
        self,
        command_gesture: str | None,
        activated: bool,
        now: float,
        voice_task: asyncio.Task | None,
    ) -> asyncio.Task | None:
        if not activated:
            self._gesture_session.record_idle()
            return voice_task
        if command_gesture is None:
            return voice_task

        command = GESTURE_TO_COMMAND.get(command_gesture)
        if not self._gesture_session.should_emit(command_gesture, command, now):
            return voice_task

        if command_gesture == GESTURE_MIC:
            voice_task = self._ensure_voice_task(voice_task)
        elif command:
            self._logger.debug(
                f"sending command_gesture={command_gesture} command={command}"
            )
            self._command_dispatcher.enqueue(command_gesture, command)

        self._gesture_session.record_emit(command_gesture, now)
        return voice_task

    def _ensure_voice_task(self, voice_task: asyncio.Task | None) -> asyncio.Task | None:
        if voice_task is None or voice_task.done():
            self._logger.debug("starting microphone capture")
            return asyncio.create_task(self._voice_capture.capture())

        self._logger.debug("microphone capture already running")
        return voice_task

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


class FramePipeline:
    def flip_frame(self, frame: Any) -> Any:
        return cv2.flip(frame, 1)

    def detection_frame(self, frame: Any, camera_zoom: float) -> CroppedFrame:
        return apply_crop(frame, center_crop_for_zoom(camera_zoom))

    def display_frame(
        self,
        frame: Any,
        zoom_controller: CameraZoomController,
    ) -> CroppedFrame:
        return apply_crop(frame, zoom_controller.current_crop())

    def detect_hands(
        self,
        hand_tracker: MediaPipeHandTracker,
        frame: Any,
    ) -> tuple[list[HandState], list[DetectedHand]]:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return hand_tracker.detect(rgb_frame, int(time.monotonic() * 1000))


class GesturePipeline:
    def __init__(
        self,
        gesture_session: GestureSession,
        zoom_controller: CameraZoomController,
    ) -> None:
        self._gesture_session = gesture_session
        self._zoom_controller = zoom_controller

    def evaluate(
        self,
        hand_states: list[HandState],
        detection_crop: CropRect,
        now: float,
    ) -> GestureDecision:
        decision = self._gesture_session.evaluate(
            hand_states_to_original_space(hand_states, detection_crop),
            now,
        )
        self.update_zoom(decision)
        return decision

    def update_zoom(self, decision: GestureDecision) -> bool:
        if decision.primary_temporarily_lost or decision.freeze_zoom:
            return False

        full_frame_crop = CropRect(0.0, 0.0, 1.0, 1.0)
        if not decision.activated:
            return self._zoom_controller.update([], full_frame_crop)

        return self._zoom_controller.update(decision.zoom_landmarks, full_frame_crop)


class DisplayPipeline:
    def __init__(self, logger: AppLogger) -> None:
        self._logger = logger

    def debug_message(
        self,
        decision_debug_message: str,
        detection_crop: CropRect,
        display_crop: CropRect,
        zoom_frozen: bool = False,
    ) -> str:
        return GestureRemoteService._debug_message(
            decision_debug_message,
            detection_crop,
            display_crop,
            zoom_frozen,
        )

    def draw_detected_hands(
        self,
        frame: Any,
        detected_hands: list[DetectedHand],
        source_crop: CropRect,
        display_crop: CropRect,
    ) -> None:
        GestureRemoteService._draw_detected_hands(
            frame,
            detected_hands,
            source_crop,
            display_crop,
        )

    def render(self, app_name: str, frame: Any) -> bool:
        cv2.imshow(app_name, frame)
        return bool(cv2.pollKey() & 0xFF == ord("q"))


class CommandPipeline:
    def __init__(
        self,
        gesture_session: GestureSession,
        voice_capture: VoiceCaptureService,
        command_dispatcher: RemoteCommandDispatcher,
        logger: AppLogger,
    ) -> None:
        self._gesture_session = gesture_session
        self._voice_capture = voice_capture
        self._command_dispatcher = command_dispatcher
        self._logger = logger

    async def handle_decision(
        self,
        command_gesture: str | None,
        activated: bool,
        now: float,
        voice_task: asyncio.Task | None,
    ) -> asyncio.Task | None:
        if not activated:
            self._gesture_session.record_idle()
            return voice_task
        if command_gesture is None:
            return voice_task

        command = GESTURE_TO_COMMAND.get(command_gesture)
        if not self._gesture_session.should_emit(command_gesture, command, now):
            return voice_task

        if command_gesture == GESTURE_MIC:
            voice_task = self._ensure_voice_task(voice_task)
        elif command:
            self._logger.debug(
                f"sending command_gesture={command_gesture} command={command}"
            )
            self._command_dispatcher.enqueue(command_gesture, command)

        self._gesture_session.record_emit(command_gesture, now)
        return voice_task

    def _ensure_voice_task(self, voice_task: asyncio.Task | None) -> asyncio.Task | None:
        if voice_task is None or voice_task.done():
            self._logger.debug("starting microphone capture")
            return asyncio.create_task(self._voice_capture.capture())

        self._logger.debug("microphone capture already running")
        return voice_task


def _debug_crop(crop: CropRect) -> str:
    return (
        f"({crop.x:.2f},{crop.y:.2f},"
        f"{crop.width:.2f},{crop.height:.2f})"
    )
