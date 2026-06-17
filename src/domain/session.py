import math
from dataclasses import dataclass
from typing import Any

from src.domain.gestures import detect_direction, detect_volume
from src.domain.landmarks import landmark_position
from src.shared.config import AppConfig


@dataclass(frozen=True)
class HandState:
    landmarks: list[Any]
    gesture: str | None
    center: tuple[float, float]
    size: float


@dataclass(frozen=True)
class GestureDecision:
    command_gesture: str | None
    debug_message: str


class GestureSession:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self.last_command_time = 0.0
        self.last_command_gesture: str | None = None
        self.primary_position: tuple[float, float] | None = None
        self.primary_previous_gesture: str | None = None
        self.secondary_previous_gesture: str | None = None
        self.primary_close_time: float | None = None
        self.secondary_close_time: float | None = None
        self.primary_select_pending = False
        self.secondary_back_pending = False
        self.volume_start_y: float | None = None
        self.pointer_start_position: tuple[float, float] | None = None

    def evaluate(self, hand_states: list[HandState], now: float) -> GestureDecision:
        if self.primary_position is None:
            primary_index = next(
                (
                    index
                    for index, hand in enumerate(hand_states)
                    if hand.gesture == "OPEN_PALM"
                ),
                None,
            )
        else:
            primary_index = self._nearest_hand_index(hand_states, self.primary_position)

        primary_hand = hand_states[primary_index] if primary_index is not None else None
        secondary_hand = next(
            (hand for index, hand in enumerate(hand_states) if index != primary_index),
            None,
        )
        debug_gestures = [hand.gesture or "UNKNOWN" for hand in hand_states]

        if primary_hand is None:
            self._reset_activation()
            return GestureDecision(
                command_gesture=None,
                debug_message=(
                    f"hands={len(hand_states)} activated=False "
                    f"gestures={debug_gestures} need_primary_open_palm"
                ),
            )

        primary_gesture = primary_hand.gesture
        self.primary_position = primary_hand.center
        secondary_gesture = secondary_hand.gesture if secondary_hand else None
        secondary_center = secondary_hand.center if secondary_hand else None
        secondary_landmarks = secondary_hand.landmarks if secondary_hand else None
        secondary_size = secondary_hand.size if secondary_hand else 0.0

        primary_closed = (
            self.primary_previous_gesture == "OPEN_PALM" and primary_gesture == "FIST"
        )
        secondary_closed = (
            self.secondary_previous_gesture == "OPEN_PALM" and secondary_gesture == "FIST"
        )

        if primary_closed:
            self.primary_close_time = now
            self.primary_select_pending = True

        if secondary_closed:
            self.secondary_close_time = now
            self.secondary_back_pending = True

        command_gesture = None
        volume_gesture = None
        pointer_gesture = None
        mic_gesture = None
        volume_distance = 0.0
        pointer_distance = 0.0

        both_closed = (
            self.primary_close_time is not None
            and self.secondary_close_time is not None
            and abs(self.primary_close_time - self.secondary_close_time)
            <= self._config.home_chord_seconds
        )
        if both_closed:
            command_gesture = "HOME"
            self.primary_close_time = None
            self.secondary_close_time = None
            self.primary_select_pending = False
            self.secondary_back_pending = False
            self.volume_start_y = None
            self.pointer_start_position = None
        elif self.primary_select_pending and self.primary_close_time is not None:
            if now - self.primary_close_time > self._config.home_chord_seconds:
                command_gesture = "OPEN_TO_FIST"
                self.primary_select_pending = False
                self.primary_close_time = None
        elif self.secondary_back_pending and self.secondary_close_time is not None:
            if now - self.secondary_close_time > self._config.home_chord_seconds:
                command_gesture = "BACK"
                self.secondary_back_pending = False
                self.secondary_close_time = None

        if command_gesture is None and secondary_hand is not None:
            if secondary_gesture == "PINCH" and secondary_center is not None:
                self.pointer_start_position = None
                if self.volume_start_y is None:
                    self.volume_start_y = secondary_center[1]
                volume_distance = self._scaled_distance(
                    secondary_size,
                    self._config.volume_distance_ratio,
                    self._config.volume_min_distance,
                    self._config.volume_max_distance,
                )
                volume_gesture = detect_volume(
                    self.volume_start_y,
                    secondary_center[1],
                    volume_distance,
                )
                command_gesture = volume_gesture
            else:
                self.volume_start_y = None

            if (
                command_gesture is None
                and secondary_gesture == "POINT"
                and secondary_landmarks is not None
            ):
                pointer_position = landmark_position(secondary_landmarks, 8)
                if self.pointer_start_position is None:
                    self.pointer_start_position = pointer_position
                pointer_distance = self._scaled_distance(
                    secondary_size,
                    self._config.pointer_distance_ratio,
                    self._config.pointer_min_distance,
                    self._config.pointer_max_distance,
                )
                pointer_gesture = detect_direction(
                    self.pointer_start_position,
                    pointer_position,
                    pointer_distance,
                    self._config.pointer_dominance,
                    "POINT",
                )
                command_gesture = pointer_gesture
            elif secondary_gesture != "POINT":
                self.pointer_start_position = None

            if command_gesture is None and secondary_gesture == "TWO_FINGERS":
                mic_gesture = "MIC"
                command_gesture = mic_gesture
            elif secondary_gesture != "TWO_FINGERS":
                mic_gesture = None

        self.primary_previous_gesture = primary_gesture
        self.secondary_previous_gesture = secondary_gesture

        return GestureDecision(
            command_gesture=command_gesture,
            debug_message=(
                f"hands={len(hand_states)} activated=True "
                f"gestures={debug_gestures} "
                f"primary={primary_gesture or 'UNKNOWN'} "
                f"secondary={secondary_gesture or 'none'} "
                f"volume={volume_gesture or 'none'} "
                f"pointer={pointer_gesture or 'none'} "
                f"mic={mic_gesture or 'none'} "
                f"size={secondary_size:.2f} "
                f"pointer_distance={pointer_distance:.2f} "
                f"volume_distance={volume_distance:.2f} "
                f"command={command_gesture or 'none'}"
            ),
        )

    def should_emit(self, command_gesture: str, command: str | None, now: float) -> bool:
        from src.domain.commands import REPEATABLE_COMMANDS

        can_repeat = command in REPEATABLE_COMMANDS if command else False
        gesture_changed = command_gesture != self.last_command_gesture
        debounce_elapsed = now - self.last_command_time >= self._config.debounce_seconds
        return gesture_changed or (can_repeat and debounce_elapsed)

    def record_emit(self, command_gesture: str, now: float) -> None:
        self.last_command_time = now
        self.last_command_gesture = command_gesture

    def record_idle(self) -> None:
        self.last_command_gesture = None

    def _reset_activation(self) -> None:
        self.primary_position = None
        self.primary_previous_gesture = None
        self.secondary_previous_gesture = None
        self.last_command_gesture = None
        self.primary_close_time = None
        self.secondary_close_time = None
        self.primary_select_pending = False
        self.secondary_back_pending = False
        self.volume_start_y = None
        self.pointer_start_position = None

    @staticmethod
    def _nearest_hand_index(
        hands: list[HandState],
        target_position: tuple[float, float] | None,
    ) -> int | None:
        if not hands or target_position is None:
            return None

        target_x, target_y = target_position
        return min(
            range(len(hands)),
            key=lambda index: math.hypot(
                hands[index].center[0] - target_x,
                hands[index].center[1] - target_y,
            ),
        )

    @staticmethod
    def _scaled_distance(
        hand_size: float,
        ratio: float,
        min_distance: float,
        max_distance: float,
    ) -> float:
        if hand_size <= 0:
            return min_distance

        return min(max(hand_size * ratio, min_distance), max_distance)
