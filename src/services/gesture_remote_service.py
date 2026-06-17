import asyncio
import contextlib
import time

import cv2

from src.domain.commands import GESTURE_TO_COMMAND
from src.domain.constants import (
    DISPLAY_COMMAND_SELECT,
    GESTURE_MIC,
    TV_COMMAND_DPAD_CENTER,
)
from src.domain.session import GestureSession
from src.infrastructure.android_tv_remote import AndroidTvRemoteClient
from src.infrastructure.hand_model import download_model_if_missing
from src.infrastructure.hand_tracking import MediaPipeHandTracker
from src.infrastructure.video_preprocessing import CameraZoomController, apply_crop
from src.infrastructure.video_overlay import draw_simple_landmarks
from src.services.voice_capture import VoiceCaptureService
from src.shared.config import AppConfig


class GestureRemoteService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._remote = AndroidTvRemoteClient(config)
        self._voice_capture = VoiceCaptureService(self._remote, config)
        self._gesture_session = GestureSession(config)

    async def run(self) -> None:
        await self._remote.connect()

        cap = cv2.VideoCapture(self._config.webcam_index)
        if not cap.isOpened():
            print("Could not open webcam.")
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
                    print("Could not read frame from webcam.")
                    break

                now = time.monotonic()
                frame = cv2.flip(frame, 1)
                cropped_frame = apply_crop(frame, zoom_controller.current_crop())
                frame = cropped_frame.frame
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                hand_states, detected_hands = hand_tracker.detect(
                    rgb_frame,
                    int(time.monotonic() * 1000),
                )
                zoom_controller.update(
                    [landmarks for landmarks, _ in detected_hands],
                    cropped_frame.crop,
                )

                for landmarks, _ in detected_hands:
                    draw_simple_landmarks(frame, landmarks)

                decision = self._gesture_session.evaluate(hand_states, now)
                command_gesture = decision.command_gesture

                if command_gesture:
                    command = GESTURE_TO_COMMAND.get(command_gesture)
                    if self._gesture_session.should_emit(command_gesture, command, now):
                        if command_gesture == GESTURE_MIC:
                            if voice_task is None or voice_task.done():
                                self._log_debug("starting microphone capture")
                                voice_task = asyncio.create_task(self._voice_capture.capture())
                            else:
                                self._log_debug("microphone capture already running")
                        elif command:
                            self._log_debug(
                                f"sending command_gesture={command_gesture} command={command}"
                            )
                            self._print_and_send_gesture(command_gesture, command)
                        self._gesture_session.record_emit(command_gesture, now)
                else:
                    self._gesture_session.record_idle()

                if (
                    decision.debug_message != last_debug_message
                    or now - last_debug_time >= self._config.debug_log_seconds
                ):
                    self._log_debug(decision.debug_message)
                    last_debug_message = decision.debug_message
                    last_debug_time = now

                cv2.imshow(self._config.app_name, frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

                await asyncio.sleep(0)
        finally:
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
        print(f"Gesture: {gesture} -> {display_command}")
        self._remote.send_key_command(command)

    @staticmethod
    def _log_debug(message: str) -> None:
        print(f"[DEBUG] {message}")
