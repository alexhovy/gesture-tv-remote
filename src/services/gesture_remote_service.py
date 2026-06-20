import asyncio
import contextlib
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import cv2

from src.domain.commands import GESTURE_TO_COMMAND, REPEATABLE_COMMANDS
from src.domain.constants import (
    DISPLAY_COMMAND_SELECT,
    GESTURE_MIC,
    TV_COMMAND_DPAD_CENTER,
)
from src.domain.session import GestureSession, HandState
from src.infrastructure.camera.camera_zoom import CameraZoomController
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
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class GestureRemoteService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._remote = create_tv_remote_client(config)
        self._voice_capture = VoiceCaptureService(self._remote, config)
        self._gesture_session = GestureSession(config)
        self._logger = AppLogger()
        self._command_dispatcher = RemoteCommandDispatcher(self._remote, self._logger)

    async def run(self) -> None:
        if not await self._remote.connect():
            self._logger.info("TV connection failed. Exiting.")
            return

        cap = cv2.VideoCapture(self._config.webcam_index)
        if not cap.isOpened():
            self._logger.error("Could not open webcam.")
            cap.release()
            self._remote.disconnect()
            return

        hand_tracker = None
        voice_task = None
        last_debug_time = 0.0
        last_debug_message = ""
        zoom_controller = CameraZoomController(self._config)
        self._command_dispatcher.start()

        try:
            download_model_if_missing(self._config)
            hand_tracker = MediaPipeHandTracker(self._config)

            while True:
                ok, frame = cap.read()
                if not ok:
                    self._logger.error("Could not read frame from webcam.")
                    break

                frame = self._flip_frame(frame)
                detection_frame = self._detection_frame(frame, self._config.camera_zoom)
                hand_states, detected_hands = self._detect_hands(
                    hand_tracker,
                    detection_frame.frame,
                )

                now = time.monotonic()
                decision = self._gesture_session.evaluate(
                    hand_states_to_original_space(hand_states, detection_frame.crop),
                    now,
                )

                crop_changed = self._update_zoom(
                    zoom_controller,
                    decision.zoom_landmarks,
                    decision.activated,
                    decision.primary_temporarily_lost,
                )
                voice_task = await self._handle_decision(
                    decision.command_gesture,
                    decision.activated,
                    now,
                    voice_task,
                )

                if crop_changed:
                    self._gesture_session.reset_motion_tracking()

                display_frame = self._display_frame(frame, zoom_controller)
                debug_message = self._debug_message(
                    decision.debug_message,
                    detection_frame.crop,
                    display_frame.crop,
                )
                if (
                    debug_message != last_debug_message
                    or now - last_debug_time >= self._config.debug_log_seconds
                ):
                    self._logger.debug(debug_message)
                    last_debug_message = debug_message
                    last_debug_time = now

                self._draw_detected_hands(
                    display_frame.frame,
                    detected_hands,
                    detection_frame.crop,
                    display_frame.crop,
                )
                cv2.imshow(self._config.app_name, display_frame.frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

                await asyncio.sleep(0)
        finally:
            await self._cleanup(voice_task, hand_tracker, cap)

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
    ) -> bool:
        if primary_temporarily_lost:
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
    ) -> str:
        return (
            f"{decision_debug_message} "
            f"detection_crop={_debug_crop(detection_crop)} "
            f"display_crop={_debug_crop(display_crop)}"
        )

    async def _handle_decision(
        self,
        command_gesture: str | None,
        activated: bool,
        now: float,
        voice_task: asyncio.Task | None,
    ) -> asyncio.Task | None:
        if not activated or command_gesture is None:
            self._gesture_session.record_idle()
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

    async def _cleanup(
        self,
        voice_task: asyncio.Task | None,
        hand_tracker: MediaPipeHandTracker | None,
        cap: Any,
    ) -> None:
        if voice_task is not None and not voice_task.done():
            voice_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await voice_task
        if hand_tracker is not None:
            hand_tracker.close()
        cap.release()
        cv2.destroyAllWindows()
        await self._command_dispatcher.close()
        self._remote.disconnect()


def _debug_crop(crop: CropRect) -> str:
    return (
        f"({crop.x:.2f},{crop.y:.2f},"
        f"{crop.width:.2f},{crop.height:.2f})"
    )


@dataclass(frozen=True)
class RemoteCommandRequest:
    gesture: str
    command: str


class RemoteCommandDispatcher:
    def __init__(self, remote: Any, logger: AppLogger) -> None:
        self._remote = remote
        self._logger = logger
        self._commands: deque[RemoteCommandRequest] = deque()
        self._latest_repeatable: RemoteCommandRequest | None = None
        self._has_work: asyncio.Event | None = None
        self._worker_task: asyncio.Task | None = None
        self._sending = False
        self._closed = False

    def start(self) -> None:
        if self._worker_task is not None and not self._worker_task.done():
            return
        self._has_work = asyncio.Event()
        self._worker_task = asyncio.create_task(self._run())

    def enqueue(self, gesture: str, command: str) -> None:
        if self._closed:
            return
        if self._has_work is None:
            self.start()

        request = RemoteCommandRequest(gesture=gesture, command=command)
        if command in REPEATABLE_COMMANDS and self._is_busy():
            self._latest_repeatable = request
            self._has_work.set()
            return

        if command not in REPEATABLE_COMMANDS:
            self._latest_repeatable = None
        self._commands.append(request)
        self._has_work.set()

    async def close(self) -> None:
        self._closed = True
        self._commands.clear()
        self._latest_repeatable = None
        if self._worker_task is None:
            return

        self._worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._worker_task
        self._worker_task = None

    async def _run(self) -> None:
        if self._has_work is None:
            return

        while True:
            await self._has_work.wait()
            while True:
                request = self._next_request()
                if request is None:
                    self._has_work.clear()
                    break

                self._sending = True
                try:
                    await self._send(request)
                finally:
                    self._sending = False

    async def _send(self, request: RemoteCommandRequest) -> None:
        display_command = (
            DISPLAY_COMMAND_SELECT
            if request.command == TV_COMMAND_DPAD_CENTER
            else request.command
        )
        self._logger.info(f"Gesture: {request.gesture} -> {display_command}")
        await self._remote.send_key_command(request.command)

    def _next_request(self) -> RemoteCommandRequest | None:
        if self._commands:
            return self._commands.popleft()

        request = self._latest_repeatable
        self._latest_repeatable = None
        return request

    def _is_busy(self) -> bool:
        return self._sending or bool(self._commands)
