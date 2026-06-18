import asyncio
import contextlib
import time
from typing import Any

import cv2

from src.domain.commands import GESTURE_TO_COMMAND
from src.domain.constants import (
    DISPLAY_COMMAND_SELECT,
    GESTURE_MIC,
    TV_COMMAND_DPAD_CENTER,
)
from src.domain.session import GestureSession, HandState
from src.infrastructure.android_tv_remote import AndroidTvRemoteClient
from src.infrastructure.camera_zoom import CameraZoomController
from src.infrastructure.hand_model import download_model_if_missing
from src.infrastructure.hand_tracking import DetectedHand, MediaPipeHandTracker
from src.infrastructure.landmark_projection import hand_states_to_original_space
from src.infrastructure.video_preprocessing import CroppedFrame, apply_crop
from src.infrastructure.video_overlay import draw_simple_landmarks
from src.services.voice_capture import VoiceCaptureService
from src.shared.config import AppConfig
from src.shared.logging import AppLogger


class GestureRemoteService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._remote = AndroidTvRemoteClient(config)
        self._voice_capture = VoiceCaptureService(self._remote, config)
        self._gesture_session = GestureSession(config)
        self._logger = AppLogger()

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

        try:
            download_model_if_missing(self._config)
            hand_tracker = MediaPipeHandTracker(self._config)

            while True:
                ok, frame = cap.read()
                if not ok:
                    self._logger.error("Could not read frame from webcam.")
                    break

                frame = self._flip_frame(frame)
                cropped_frame = self._crop_frame(frame, zoom_controller)
                hand_states, detected_hands = self._detect_hands(
                    hand_tracker,
                    cropped_frame.frame,
                )
                self._draw_detected_hands(cropped_frame.frame, detected_hands)

                now = time.monotonic()
                decision = self._gesture_session.evaluate(
                    hand_states_to_original_space(hand_states, cropped_frame.crop),
                    now,
                )

                crop_changed = self._update_zoom(
                    zoom_controller,
                    detected_hands,
                    cropped_frame,
                    decision.activated,
                    decision.primary_temporarily_lost,
                )
                voice_task = self._handle_decision(
                    decision.command_gesture,
                    decision.activated,
                    now,
                    voice_task,
                )

                if crop_changed:
                    self._gesture_session.reset_motion_tracking()

                if (
                    decision.debug_message != last_debug_message
                    or now - last_debug_time >= self._config.debug_log_seconds
                ):
                    self._logger.debug(decision.debug_message)
                    last_debug_message = decision.debug_message
                    last_debug_time = now

                cv2.imshow(self._config.app_name, cropped_frame.frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

                await asyncio.sleep(0)
        finally:
            await self._cleanup(voice_task, hand_tracker, cap)

    @staticmethod
    def _flip_frame(frame: Any) -> Any:
        return cv2.flip(frame, 1)

    @staticmethod
    def _crop_frame(frame: Any, zoom_controller: CameraZoomController) -> CroppedFrame:
        return apply_crop(frame, zoom_controller.current_crop())

    @staticmethod
    def _detect_hands(
        hand_tracker: MediaPipeHandTracker,
        frame: Any,
    ) -> tuple[list[HandState], list[DetectedHand]]:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return hand_tracker.detect(rgb_frame, int(time.monotonic() * 1000))

    @staticmethod
    def _draw_detected_hands(frame: Any, detected_hands: list[DetectedHand]) -> None:
        for detected_hand in detected_hands:
            draw_simple_landmarks(frame, detected_hand.landmarks)

    def _update_zoom(
        self,
        zoom_controller: CameraZoomController,
        detected_hands: list[DetectedHand],
        cropped_frame: CroppedFrame,
        activated: bool,
        primary_temporarily_lost: bool,
    ) -> bool:
        if primary_temporarily_lost:
            return False

        if not activated:
            return zoom_controller.update([], cropped_frame.crop)

        return zoom_controller.update(
            [detected_hand.landmarks for detected_hand in detected_hands],
            cropped_frame.crop,
        )

    def _handle_decision(
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
            self._print_and_send_gesture(command_gesture, command)

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
        self._remote.disconnect()

    def _print_and_send_gesture(self, gesture: str, command: str) -> None:
        display_command = (
            DISPLAY_COMMAND_SELECT if command == TV_COMMAND_DPAD_CENTER else command
        )
        self._logger.info(f"Gesture: {gesture} -> {display_command}")
        self._remote.send_key_command(command)
