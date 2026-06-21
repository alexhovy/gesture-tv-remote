import math

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
from src.domain.motion_filter import (
    JoystickDecision,
    classify_pointer_joystick,
    classify_volume_joystick,
)
from src.domain.session_debug import GestureSessionDebugMixin
from src.domain.session_types import GestureDecision, HandState
from src.shared.config import AppConfig


class GestureSession(GestureSessionDebugMixin):
    MOTION_NEUTRAL_SETTLE_FRAMES = 3

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
        self.volume_anchor_y: float | None = None
        self.volume_active_gesture: str | None = None
        self.volume_armed = True
        self.volume_neutral_frames = 0
        self.volume_phase = "idle"
        self.volume_last_blocked_reason: str | None = None
        self.volume_candidate_gesture: str | None = None
        self.volume_candidate_magnitude = 0.0
        self.volume_activation_distance = 0.0
        self.volume_neutral_distance = 0.0
        self.volume_threshold_ratio = 0.0
        self.volume_in_neutral = True
        self.pointer_anchor_position: tuple[float, float] | None = None
        self.pointer_active_gesture: str | None = None
        self.pointer_armed = True
        self.pointer_neutral_frames = 0
        self.pointer_phase = "idle"
        self.pointer_last_blocked_reason: str | None = None
        self.pointer_candidate_gesture: str | None = None
        self.pointer_candidate_magnitude = 0.0
        self.pointer_activation_distance = 0.0
        self.pointer_neutral_distance = 0.0
        self.pointer_threshold_ratio = 0.0
        self.pointer_in_neutral = True

    def update_config(self, config: AppConfig) -> None:
        self._config = config

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
        self.pointer_last_blocked_reason = None
        self.volume_last_blocked_reason = None
        self._reset_pointer_diagnostics()
        self._reset_volume_diagnostics()

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
                if self.volume_anchor_y is None:
                    self.volume_anchor_y = secondary_center[1]
                volume_distance = self._scaled_distance(
                    secondary_size,
                    self._config.volume_distance_ratio,
                    self._config.volume_min_distance,
                    self._config.volume_max_distance,
                )
                volume_candidate = classify_volume_joystick(
                    self.volume_anchor_y,
                    secondary_center[1],
                    volume_distance,
                )
                self._record_volume_decision(volume_candidate)
                volume_gesture = self._volume_joystick_command(
                    volume_candidate,
                    secondary_center[1],
                    now,
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
                if self.pointer_anchor_position is None:
                    self.pointer_anchor_position = pointer_position
                pointer_distance = self._scaled_distance(
                    secondary_size,
                    self._config.pointer_distance_ratio,
                    self._config.pointer_min_distance,
                    self._config.pointer_max_distance,
                )
                pointer_candidate = classify_pointer_joystick(
                    self.pointer_anchor_position,
                    pointer_position,
                    pointer_distance,
                    self._config.pointer_dominance,
                    GESTURE_POINT,
                )
                self._record_pointer_decision(pointer_candidate)
                pointer_gesture = self._pointer_joystick_command(
                    pointer_candidate,
                    pointer_position,
                    now,
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
        if gesture_changed:
            return True

        return now - self.last_command_time >= self._config.debounce_seconds

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

    def _volume_joystick_command(
        self,
        decision: JoystickDecision,
        current_y: float,
        now: float,
    ) -> str | None:
        if decision.in_neutral:
            self._settle_volume_neutral(current_y)
            return None

        return self._motion_command(
            decision,
            active_gesture_attr="volume_active_gesture",
            armed_attr="volume_armed",
            neutral_frames_attr="volume_neutral_frames",
            phase_attr="volume_phase",
            blocked_reason_attr="volume_last_blocked_reason",
        )

    def _pointer_joystick_command(
        self,
        decision: JoystickDecision,
        current_position: tuple[float, float],
        now: float,
    ) -> str | None:
        if decision.in_neutral:
            self._settle_pointer_neutral(current_position)
            return None

        return self._motion_command(
            decision,
            active_gesture_attr="pointer_active_gesture",
            armed_attr="pointer_armed",
            neutral_frames_attr="pointer_neutral_frames",
            phase_attr="pointer_phase",
            blocked_reason_attr="pointer_last_blocked_reason",
        )

    def _motion_command(
        self,
        decision: JoystickDecision,
        active_gesture_attr: str,
        armed_attr: str,
        neutral_frames_attr: str,
        phase_attr: str,
        blocked_reason_attr: str,
    ) -> str | None:
        setattr(self, neutral_frames_attr, 0)
        if decision.gesture is None:
            if getattr(self, armed_attr):
                setattr(self, phase_attr, "armed")
            else:
                setattr(self, phase_attr, "triggered")
                setattr(self, blocked_reason_attr, "awaiting_neutral")
            return None

        if getattr(self, armed_attr):
            setattr(self, active_gesture_attr, decision.gesture)
            setattr(self, armed_attr, False)
            setattr(self, phase_attr, "triggered")
            return decision.gesture

        setattr(self, phase_attr, "triggered")
        setattr(self, blocked_reason_attr, "awaiting_neutral")
        return None

    def _settle_volume_neutral(self, current_y: float) -> None:
        self.volume_neutral_frames += 1
        self.volume_phase = "settling"
        self.volume_last_blocked_reason = "settling_neutral"
        if self.volume_neutral_frames < self.MOTION_NEUTRAL_SETTLE_FRAMES:
            return

        self.volume_anchor_y = current_y
        self._reset_volume_motion_state()

    def _settle_pointer_neutral(self, current_position: tuple[float, float]) -> None:
        self.pointer_neutral_frames += 1
        self.pointer_phase = "settling"
        self.pointer_last_blocked_reason = "settling_neutral"
        if self.pointer_neutral_frames < self.MOTION_NEUTRAL_SETTLE_FRAMES:
            return

        self.pointer_anchor_position = current_position
        self._reset_pointer_motion_state()

    def _record_volume_decision(self, decision: JoystickDecision) -> None:
        self.volume_candidate_gesture = decision.gesture
        self.volume_candidate_magnitude = decision.magnitude
        self.volume_activation_distance = decision.activation_distance
        self.volume_neutral_distance = decision.neutral_distance
        self.volume_threshold_ratio = decision.threshold_ratio
        self.volume_in_neutral = decision.in_neutral
        self.volume_last_blocked_reason = decision.blocked_reason

    def _record_pointer_decision(self, decision: JoystickDecision) -> None:
        self.pointer_candidate_gesture = decision.gesture
        self.pointer_candidate_magnitude = decision.magnitude
        self.pointer_activation_distance = decision.activation_distance
        self.pointer_neutral_distance = decision.neutral_distance
        self.pointer_threshold_ratio = decision.threshold_ratio
        self.pointer_in_neutral = decision.in_neutral
        self.pointer_last_blocked_reason = decision.blocked_reason

    def _reset_volume_tracking(self) -> None:
        self.volume_anchor_y = None
        self._reset_volume_motion_state()

    def _reset_volume_motion_state(self) -> None:
        self.volume_active_gesture = None
        self.volume_armed = True
        self.volume_neutral_frames = 0
        self.volume_phase = "armed"

    def _reset_volume_diagnostics(self) -> None:
        self.volume_candidate_gesture = None
        self.volume_candidate_magnitude = 0.0
        self.volume_activation_distance = 0.0
        self.volume_neutral_distance = 0.0
        self.volume_threshold_ratio = 0.0
        self.volume_in_neutral = True

    def _reset_pointer_tracking(self) -> None:
        self.pointer_anchor_position = None
        self._reset_pointer_motion_state()

    def _reset_pointer_motion_state(self) -> None:
        self.pointer_active_gesture = None
        self.pointer_armed = True
        self.pointer_neutral_frames = 0
        self.pointer_phase = "armed"

    def _reset_pointer_diagnostics(self) -> None:
        self.pointer_candidate_gesture = None
        self.pointer_candidate_magnitude = 0.0
        self.pointer_activation_distance = 0.0
        self.pointer_neutral_distance = 0.0
        self.pointer_threshold_ratio = 0.0
        self.pointer_in_neutral = True

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
