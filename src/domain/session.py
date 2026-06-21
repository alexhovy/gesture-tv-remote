import math
from dataclasses import dataclass, field
from typing import Any

from src.domain.constants import (
    DEBUG_NONE,
    DEBUG_UNKNOWN,
    GESTURE_BACK,
    GESTURE_FIST,
    GESTURE_HOME,
    GESTURE_MIC,
    GESTURE_OPEN_PALM,
    GESTURE_OPEN_TO_FIST,
    GESTURE_PINCH,
    GESTURE_POINT,
    GESTURE_POINT_DOWN,
    GESTURE_POINT_LEFT,
    GESTURE_POINT_RIGHT,
    GESTURE_POINT_UP,
    GESTURE_TWO_FINGERS,
    GESTURE_VOLUME_DOWN,
    GESTURE_VOLUME_UP,
)
from src.domain.gestures import detect_direction, detect_volume
from src.domain.landmarks import (
    hand_upright_metrics,
    hand_upright_reason,
)
from src.shared.config import AppConfig


@dataclass(frozen=True)
class HandState:
    landmarks: list[Any]
    gesture: str | None
    center: tuple[float, float]
    size: float
    upright: bool = True


@dataclass(frozen=True)
class GestureDecision:
    command_gesture: str | None
    activated: bool
    debug_message: str
    primary_temporarily_lost: bool = False
    zoom_landmarks: list[list[Any]] = field(default_factory=list)


class GestureSession:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self.last_command_time = 0.0
        self.last_command_gesture: str | None = None
        self.primary_position: tuple[float, float] | None = None
        self.primary_last_seen_time: float | None = None
        self.primary_previous_gesture: str | None = None
        self.secondary_previous_gesture: str | None = None
        self.primary_close_time: float | None = None
        self.secondary_close_time: float | None = None
        self.primary_select_pending = False
        self.secondary_back_pending = False
        self.volume_start_y: float | None = None
        self.volume_active_gesture: str | None = None
        self.volume_peak_distance = 0.0
        self.volume_returning_to_neutral = False
        self.volume_settling_frames = 0
        self.volume_returned_gesture: str | None = None
        self.pointer_start_position: tuple[float, float] | None = None
        self.pointer_active_gesture: str | None = None
        self.pointer_peak_distance = 0.0
        self.pointer_returning_to_neutral = False
        self.pointer_settling_frames = 0
        self.pointer_returned_gesture: str | None = None

    def evaluate(self, hand_states: list[HandState], now: float) -> GestureDecision:
        primary_anchor = self.primary_position
        if self.primary_position is None:
            primary_index = next(
                (
                    index
                    for index, hand in enumerate(hand_states)
                    if hand.upright and hand.gesture == GESTURE_OPEN_PALM
                ),
                None,
            )
        else:
            primary_index = self._primary_hand_index(hand_states)

        primary_hand = hand_states[primary_index] if primary_index is not None else None
        secondary_index = next(
            (index for index, hand in enumerate(hand_states) if index != primary_index),
            None,
        )
        secondary_hand = hand_states[secondary_index] if secondary_index is not None else None
        debug_gestures = [hand.gesture or DEBUG_UNKNOWN for hand in hand_states]
        hand_debug = self._debug_hands(hand_states, primary_anchor)

        if primary_hand is None:
            if self._primary_missing_within_grace(now):
                self.reset_motion_tracking()
                return GestureDecision(
                    command_gesture=None,
                    activated=True,
                    debug_message=(
                        f"hands={len(hand_states)} activated=True "
                        f"gestures={debug_gestures} primary_temporarily_lost "
                        f"primary_index=none secondary_index=none "
                        f"zoom_hands=0 {hand_debug}"
                    ),
                    primary_temporarily_lost=True,
                )

            self._reset_activation()
            return GestureDecision(
                command_gesture=None,
                activated=False,
                debug_message=(
                    f"hands={len(hand_states)} activated=False "
                    f"gestures={debug_gestures} need_primary_open_palm_or_upright "
                    f"primary_index=none secondary_index=none "
                    f"zoom_hands=0 {hand_debug}"
                ),
            )

        if not primary_hand.upright:
            self._reset_activation()
            return GestureDecision(
                command_gesture=None,
                activated=False,
                debug_message=(
                    f"hands={len(hand_states)} activated=False "
                    f"gestures={debug_gestures} need_primary_open_palm_or_upright "
                    f"primary_index={primary_index} secondary_index=none "
                    f"zoom_hands=0 {hand_debug}"
                ),
            )

        if secondary_hand is not None and not secondary_hand.upright:
            secondary_hand = None
            secondary_index = None
            self.reset_motion_tracking()

        primary_gesture = primary_hand.gesture
        self.primary_position = primary_hand.center
        self.primary_last_seen_time = now
        secondary_gesture = secondary_hand.gesture if secondary_hand else None
        secondary_center = secondary_hand.center if secondary_hand else None
        secondary_size = secondary_hand.size if secondary_hand else 0.0
        zoom_landmarks = [primary_hand.landmarks]
        if secondary_hand is not None and secondary_gesture is not None:
            zoom_landmarks.append(secondary_hand.landmarks)

        primary_closed = (
            self.primary_previous_gesture == GESTURE_OPEN_PALM
            and primary_gesture == GESTURE_FIST
        )
        secondary_closed = (
            self.secondary_previous_gesture == GESTURE_OPEN_PALM
            and secondary_gesture == GESTURE_FIST
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
        pointer_position = None

        both_closed = (
            self.primary_close_time is not None
            and self.secondary_close_time is not None
            and abs(self.primary_close_time - self.secondary_close_time)
            <= self._config.home_chord_seconds
        )
        if both_closed:
            command_gesture = GESTURE_HOME
            self.primary_close_time = None
            self.secondary_close_time = None
            self.primary_select_pending = False
            self.secondary_back_pending = False
            self.reset_motion_tracking()
        elif self.primary_select_pending and self.primary_close_time is not None:
            if now - self.primary_close_time > self._config.home_chord_seconds:
                command_gesture = GESTURE_OPEN_TO_FIST
                self.primary_select_pending = False
                self.primary_close_time = None
        elif self.secondary_back_pending and self.secondary_close_time is not None:
            if now - self.secondary_close_time > self._config.home_chord_seconds:
                command_gesture = GESTURE_BACK
                self.secondary_back_pending = False
                self.secondary_close_time = None

        if secondary_hand is None:
            self.reset_motion_tracking()

        if command_gesture is None and secondary_hand is not None:
            if secondary_gesture == GESTURE_PINCH and secondary_center is not None:
                self._reset_pointer_tracking()
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
                volume_gesture = self._filtered_volume_gesture(
                    volume_gesture,
                    self.volume_start_y,
                    secondary_center[1],
                    volume_distance,
                )
                command_gesture = volume_gesture
            else:
                self._reset_volume_tracking()

            if (
                command_gesture is None
                and secondary_gesture == GESTURE_POINT
                and secondary_center is not None
            ):
                pointer_position = secondary_center
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
                    GESTURE_POINT,
                )
                pointer_gesture = self._filtered_pointer_gesture(
                    pointer_gesture,
                    self.pointer_start_position,
                    pointer_position,
                    pointer_distance,
                )
                command_gesture = pointer_gesture
            elif secondary_gesture != GESTURE_POINT:
                self._reset_pointer_tracking()

            if command_gesture is None and secondary_gesture == GESTURE_TWO_FINGERS:
                mic_gesture = GESTURE_MIC
                command_gesture = mic_gesture
            elif secondary_gesture != GESTURE_TWO_FINGERS:
                mic_gesture = None

        self.primary_previous_gesture = primary_gesture
        self.secondary_previous_gesture = secondary_gesture

        return GestureDecision(
            command_gesture=command_gesture,
            activated=True,
            debug_message=(
                f"hands={len(hand_states)} activated=True "
                f"gestures={debug_gestures} "
                f"primary={primary_gesture or DEBUG_UNKNOWN} "
                f"secondary={secondary_gesture or DEBUG_NONE} "
                f"volume={volume_gesture or DEBUG_NONE} "
                f"pointer={pointer_gesture or DEBUG_NONE} "
                f"mic={mic_gesture or DEBUG_NONE} "
                f"size={secondary_size:.2f} "
                f"pointer_distance={pointer_distance:.2f} "
                f"volume_distance={volume_distance:.2f} "
                f"command={command_gesture or DEBUG_NONE} "
                f"pointer_state={self._debug_pointer_state(pointer_position)} "
                f"volume_state={self._debug_volume_state()} "
                f"primary_index={primary_index} "
                f"secondary_index={secondary_index if secondary_index is not None else DEBUG_NONE} "
                f"zoom_hands={len(zoom_landmarks)} "
                f"{hand_debug}"
            ),
            zoom_landmarks=zoom_landmarks,
        )

    def should_emit(self, command_gesture: str, command: str | None, now: float) -> bool:
        gesture_changed = command_gesture != self.last_command_gesture
        return gesture_changed

    def record_emit(self, command_gesture: str, now: float) -> None:
        self.last_command_time = now
        self.last_command_gesture = command_gesture

    def record_idle(self) -> None:
        self.last_command_gesture = None

    def reset_motion_tracking(self) -> None:
        self._reset_volume_tracking()
        self._reset_pointer_tracking()

    def _reset_activation(self) -> None:
        self.primary_position = None
        self.primary_last_seen_time = None
        self.primary_previous_gesture = None
        self.secondary_previous_gesture = None
        self.last_command_gesture = None
        self.primary_close_time = None
        self.secondary_close_time = None
        self.primary_select_pending = False
        self.secondary_back_pending = False
        self._reset_volume_tracking()
        self._reset_pointer_tracking()

    def _filtered_volume_gesture(
        self,
        gesture: str | None,
        start_y: float | None,
        current_y: float,
        distance: float,
    ) -> str | None:
        if start_y is None:
            return None

        magnitude = abs(current_y - start_y)
        if self.volume_settling_frames > 0:
            if self._is_motion_neutral(magnitude, distance):
                self.volume_settling_frames += 1
                if self.volume_settling_frames >= self._settling_frame_count():
                    self.volume_settling_frames = 0
            else:
                self.volume_start_y = current_y
                self.volume_settling_frames = 1
            return None

        if gesture is None:
            if self.volume_active_gesture is not None:
                if self._is_motion_neutral(magnitude, distance):
                    self.volume_start_y = current_y
                    self._reset_volume_motion_state()
                else:
                    self.volume_returning_to_neutral = True
            return None

        if self.volume_returning_to_neutral:
            if gesture is not None or self._is_motion_neutral(magnitude, distance):
                returned_gesture = self.volume_active_gesture
                self.volume_start_y = current_y
                self._reset_volume_motion_state()
                self.volume_settling_frames = 1
                self.volume_returned_gesture = returned_gesture
            return None

        if self.volume_active_gesture is not None and gesture != self.volume_active_gesture:
            returned_gesture = self.volume_active_gesture
            self.volume_start_y = current_y
            self._reset_volume_motion_state()
            self.volume_settling_frames = 1
            self.volume_returned_gesture = returned_gesture
            return None

        if self._is_direct_opposite_motion(gesture, self.volume_returned_gesture):
            if magnitude < self._opposite_rearm_distance(distance):
                return None
            self.volume_returned_gesture = None
        elif gesture is not None:
            self.volume_returned_gesture = None

        return self._filtered_motion_gesture(
            gesture,
            magnitude,
            distance,
            active_gesture_attr="volume_active_gesture",
            peak_distance_attr="volume_peak_distance",
            returning_attr="volume_returning_to_neutral",
        )

    def _filtered_pointer_gesture(
        self,
        gesture: str | None,
        start_position: tuple[float, float] | None,
        current_position: tuple[float, float],
        distance: float,
    ) -> str | None:
        if start_position is None:
            return None

        magnitude = math.dist(start_position, current_position)
        if self.pointer_settling_frames > 0:
            if self._is_motion_neutral(magnitude, distance):
                self.pointer_settling_frames += 1
                if self.pointer_settling_frames >= self._settling_frame_count():
                    self.pointer_settling_frames = 0
            else:
                self.pointer_start_position = current_position
                self.pointer_settling_frames = 1
            return None

        if gesture is None:
            if self.pointer_active_gesture is not None:
                if self._is_motion_neutral(magnitude, distance):
                    self.pointer_start_position = current_position
                    self._reset_pointer_motion_state()
                else:
                    self.pointer_returning_to_neutral = True
            return None

        if self.pointer_returning_to_neutral:
            if gesture is not None or self._is_motion_neutral(magnitude, distance):
                returned_gesture = self.pointer_active_gesture
                self.pointer_start_position = current_position
                self._reset_pointer_motion_state()
                self.pointer_settling_frames = 1
                self.pointer_returned_gesture = returned_gesture
            return None

        if self.pointer_active_gesture is not None and gesture != self.pointer_active_gesture:
            returned_gesture = self.pointer_active_gesture
            self.pointer_start_position = current_position
            self._reset_pointer_motion_state()
            self.pointer_settling_frames = 1
            self.pointer_returned_gesture = returned_gesture
            return None

        magnitude = self._pointer_motion_magnitude(gesture, start_position, current_position)
        if self._is_direct_opposite_motion(gesture, self.pointer_returned_gesture):
            if magnitude < self._opposite_rearm_distance(distance):
                return None
            self.pointer_returned_gesture = None
        elif gesture is not None:
            self.pointer_returned_gesture = None

        return self._filtered_motion_gesture(
            gesture,
            magnitude,
            distance,
            active_gesture_attr="pointer_active_gesture",
            peak_distance_attr="pointer_peak_distance",
            returning_attr="pointer_returning_to_neutral",
        )

    def _filtered_motion_gesture(
        self,
        gesture: str,
        magnitude: float,
        activation_distance: float,
        active_gesture_attr: str,
        peak_distance_attr: str,
        returning_attr: str,
    ) -> str | None:
        if getattr(self, returning_attr):
            return None

        active_gesture = getattr(self, active_gesture_attr)
        if active_gesture is not None and gesture != active_gesture:
            setattr(self, returning_attr, True)
            return None

        if gesture != active_gesture:
            setattr(self, active_gesture_attr, gesture)
            setattr(self, peak_distance_attr, magnitude)
            setattr(self, returning_attr, False)
            return gesture

        peak_distance = getattr(self, peak_distance_attr)
        if magnitude >= peak_distance:
            setattr(self, peak_distance_attr, magnitude)
            setattr(self, returning_attr, False)
            return None

        release_delta = activation_distance * 0.75
        if magnitude <= peak_distance - release_delta:
            setattr(self, returning_attr, True)

        return None

    @staticmethod
    def _is_motion_neutral(magnitude: float, activation_distance: float) -> bool:
        return magnitude <= activation_distance * 0.45

    @staticmethod
    def _settling_frame_count() -> int:
        return 2

    @staticmethod
    def _opposite_rearm_distance(activation_distance: float) -> float:
        return activation_distance * 1.5

    @staticmethod
    def _is_direct_opposite_motion(gesture: str | None, previous_gesture: str | None) -> bool:
        opposites = {
            GESTURE_POINT_DOWN: GESTURE_POINT_UP,
            GESTURE_POINT_UP: GESTURE_POINT_DOWN,
            GESTURE_POINT_LEFT: GESTURE_POINT_RIGHT,
            GESTURE_POINT_RIGHT: GESTURE_POINT_LEFT,
            GESTURE_VOLUME_DOWN: GESTURE_VOLUME_UP,
            GESTURE_VOLUME_UP: GESTURE_VOLUME_DOWN,
        }
        return gesture is not None and previous_gesture is not None and opposites.get(previous_gesture) == gesture

    @staticmethod
    def _pointer_motion_magnitude(
        gesture: str,
        start_position: tuple[float, float],
        current_position: tuple[float, float],
    ) -> float:
        start_x, start_y = start_position
        current_x, current_y = current_position
        if gesture in {GESTURE_POINT_LEFT, GESTURE_POINT_RIGHT}:
            return abs(current_x - start_x)
        if gesture in {GESTURE_POINT_UP, GESTURE_POINT_DOWN}:
            return abs(current_y - start_y)
        return math.dist(start_position, current_position)

    def _reset_volume_tracking(self) -> None:
        self.volume_start_y = None
        self._reset_volume_motion_state()

    def _reset_volume_motion_state(self) -> None:
        self.volume_active_gesture = None
        self.volume_peak_distance = 0.0
        self.volume_returning_to_neutral = False
        self.volume_settling_frames = 0
        self.volume_returned_gesture = None

    def _reset_pointer_tracking(self) -> None:
        self.pointer_start_position = None
        self._reset_pointer_motion_state()

    def _reset_pointer_motion_state(self) -> None:
        self.pointer_active_gesture = None
        self.pointer_peak_distance = 0.0
        self.pointer_returning_to_neutral = False
        self.pointer_settling_frames = 0
        self.pointer_returned_gesture = None

    def _primary_missing_within_grace(self, now: float) -> bool:
        if self.primary_position is None or self.primary_last_seen_time is None:
            return False

        grace_seconds = max(0.0, self._config.primary_lost_grace_seconds)
        return now - self.primary_last_seen_time <= grace_seconds

    def _primary_hand_index(self, hands: list[HandState]) -> int | None:
        if not hands or self.primary_position is None:
            return None

        max_distance = max(0.0, self._config.primary_match_max_distance)
        candidates = [
            index
            for index, hand in enumerate(hands)
            if self._distance_from_primary(hand) <= max_distance
        ]
        if not candidates:
            return None

        upright_candidates = [
            index
            for index in candidates
            if hands[index].upright
        ]
        if not upright_candidates:
            return min(
                candidates,
                key=lambda index: self._distance_from_primary(hands[index]),
            )

        if self.primary_previous_gesture is None:
            return min(
                upright_candidates,
                key=lambda index: self._distance_from_primary(hands[index]),
            )

        same_gesture = [
            index
            for index in upright_candidates
            if hands[index].gesture == self.primary_previous_gesture
        ]
        if same_gesture:
            return min(
                same_gesture,
                key=lambda index: self._distance_from_primary(hands[index]),
            )

        primary_gestures = [GESTURE_OPEN_PALM, GESTURE_FIST]
        primary_like = [
            index
            for index in upright_candidates
            if hands[index].gesture in primary_gestures
        ]
        if primary_like:
            return min(
                primary_like,
                key=lambda index: self._distance_from_primary(hands[index]),
            )

        return None

    def _distance_from_primary(self, hand: HandState) -> float:
        if self.primary_position is None:
            return math.inf

        target_x, target_y = self.primary_position
        return math.hypot(hand.center[0] - target_x, hand.center[1] - target_y)

    def _debug_hands(
        self,
        hands: list[HandState],
        primary_anchor: tuple[float, float] | None,
    ) -> str:
        if not hands:
            return "hand_details=[]"

        details = [
            self._debug_hand(index, hand, primary_anchor)
            for index, hand in enumerate(hands)
        ]
        return f"hand_details=[{';'.join(details)}]"

    def _debug_hand(
        self,
        index: int,
        hand: HandState,
        primary_anchor: tuple[float, float] | None,
    ) -> str:
        center_x, center_y = hand.center
        distance = "none"
        if primary_anchor is not None:
            distance_value = math.hypot(
                center_x - primary_anchor[0],
                center_y - primary_anchor[1],
            )
            distance = f"{distance_value:.2f}"
        dx, dy, tilt_ratio = hand_upright_metrics(hand.landmarks)
        tilt = "inf" if math.isinf(tilt_ratio) else f"{tilt_ratio:.2f}"
        reason = hand_upright_reason(
            hand.landmarks,
            self._config.hand_upright_max_tilt_ratio,
        )

        return (
            f"{index}:gesture={hand.gesture or DEBUG_UNKNOWN}"
            f":upright={hand.upright}"
            f":upright_reason={reason}"
            f":upright_dx={dx:.2f}"
            f":upright_dy={dy:.2f}"
            f":upright_tilt={tilt}"
            f":center=({center_x:.2f},{center_y:.2f})"
            f":size={hand.size:.2f}"
            f":primary_dist={distance}"
        )

    def _debug_pointer_state(self, current_position: tuple[float, float] | None) -> str:
        start = self._debug_position(self.pointer_start_position)
        current = self._debug_position(current_position)
        dx, dy = self._debug_delta(self.pointer_start_position, current_position)
        return (
            f"start={start}:active={self.pointer_active_gesture or DEBUG_NONE}"
            f":current={current}:dx={dx}:dy={dy}"
            f":peak={self.pointer_peak_distance:.2f}"
            f":returning={self.pointer_returning_to_neutral}"
            f":settling={self.pointer_settling_frames}"
            f":returned={self.pointer_returned_gesture or DEBUG_NONE}"
        )

    def _debug_volume_state(self) -> str:
        start = DEBUG_NONE if self.volume_start_y is None else f"{self.volume_start_y:.2f}"
        return (
            f"start={start}:active={self.volume_active_gesture or DEBUG_NONE}"
            f":peak={self.volume_peak_distance:.2f}"
            f":returning={self.volume_returning_to_neutral}"
            f":settling={self.volume_settling_frames}"
            f":returned={self.volume_returned_gesture or DEBUG_NONE}"
        )

    @staticmethod
    def _debug_position(position: tuple[float, float] | None) -> str:
        if position is None:
            return DEBUG_NONE

        x, y = position
        return f"({x:.2f},{y:.2f})"

    @staticmethod
    def _debug_delta(
        start_position: tuple[float, float] | None,
        current_position: tuple[float, float] | None,
    ) -> tuple[str, str]:
        if start_position is None or current_position is None:
            return DEBUG_NONE, DEBUG_NONE

        start_x, start_y = start_position
        current_x, current_y = current_position
        return f"{current_x - start_x:.2f}", f"{current_y - start_y:.2f}"

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
