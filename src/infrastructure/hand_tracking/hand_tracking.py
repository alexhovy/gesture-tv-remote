import threading
from typing import Any

import cv2
import mediapipe as mp
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision.core.vision_task_running_mode import (
    VisionTaskRunningMode,
)
from mediapipe.tasks.python.vision.hand_landmarker import (
    HandLandmarker,
    HandLandmarkerOptions,
)

from src.application.ports.hand_tracker import DetectedHand
from src.domain.constants import HANDEDNESS_RIGHT
from src.domain.gesture_preprocessing import RawDetectedHandState, raw_hand_to_state
from src.domain.session_types import HandState
from src.shared.config import AppConfig


class MediaPipeHandTracker:
    def __init__(self, config: AppConfig) -> None:
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(config.model.file)),
            running_mode=VisionTaskRunningMode.LIVE_STREAM,
            num_hands=config.model.max_hands,
            min_hand_detection_confidence=config.model.min_hand_detection_confidence,
            min_hand_presence_confidence=config.model.min_hand_presence_confidence,
            min_tracking_confidence=config.model.min_tracking_confidence,
            result_callback=self._handle_result,
        )
        self._config = config
        self._lock = threading.Lock()
        self._latest: tuple[list[HandState], list[DetectedHand]] = ([], [])
        self._last_timestamp_ms = -1
        self._hands = HandLandmarker.create_from_options(options)

    def update_config(self, config: AppConfig) -> None:
        self._config = config

    def detect(
        self,
        frame: Any,
        timestamp_ms: int,
    ) -> tuple[list[HandState], list[DetectedHand]]:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        timestamp_ms = self._next_timestamp(timestamp_ms)
        self._hands.detect_async(mp_image, timestamp_ms)
        with self._lock:
            return self._latest

    def close(self) -> None:
        self._hands.close()

    def _handle_result(self, results, output_image, timestamp_ms: int) -> None:
        del output_image, timestamp_ms
        hand_states = []
        detected_hands = self._get_detected_hands(results)
        for detected_hand in detected_hands:
            hand_states.append(
                raw_hand_to_state(
                    RawDetectedHandState(
                        landmarks=detected_hand.landmarks,
                        handedness=detected_hand.handedness,
                    ),
                    self._config.gesture,
                )
            )

        with self._lock:
            self._latest = (hand_states, detected_hands)

    def _next_timestamp(self, timestamp_ms: int) -> int:
        with self._lock:
            timestamp_ms = max(timestamp_ms, self._last_timestamp_ms + 1)
            self._last_timestamp_ms = timestamp_ms
            return timestamp_ms

    @staticmethod
    def _get_detected_hands(results) -> list[DetectedHand]:
        detected_hands = []
        handedness_results = results.handedness or []

        for index, landmarks in enumerate(results.hand_landmarks or []):
            handedness = HANDEDNESS_RIGHT
            if index < len(handedness_results) and handedness_results[index]:
                handedness = handedness_results[index][0].category_name
            detected_hands.append(
                DetectedHand(landmarks=landmarks, handedness=handedness)
            )

        return detected_hands
