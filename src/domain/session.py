from src.domain.constants import (
    DEBUG_NONE,
    DEBUG_UNKNOWN,
    GESTURE_FIST,
    GESTURE_HOME,
    GESTURE_MIC,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_POINT,
    GESTURE_TWO_FINGERS,
)
from src.domain.landmarks import LANDMARK_INDEX_TIP, landmark_position
from src.domain.motion_filter import (
    JoystickDecision,
    classify_pointer_joystick,
    classify_volume_joystick,
)
from src.domain.activation_tracker import ActivationTracker
from src.domain.command_decision import CommandDecision, EmitDebounce
from src.domain.motion_gesture import MotionJoystickState, SecondaryGestureInterpreter
from src.domain.session_debug import GestureSessionDebugMixin
from src.domain.session_types import GestureDecision, HandState
from src.shared.config import AppConfig


SECONDARY_COMMAND_MIN_HAND_SIZE = 0.10
SECONDARY_DISCRETE_COMMAND_STABLE_FRAMES = 3
SECONDARY_SIZE_GATED_GESTURES = {
    GESTURE_FIST,
    GESTURE_PINCH,
    GESTURE_POINT,
    GESTURE_TWO_FINGERS,
}
SECONDARY_DISCRETE_COMMAND_GESTURES = {
    GESTURE_FIST,
    GESTURE_TWO_FINGERS,
}


class GestureSession(GestureSessionDebugMixin):
    SECONDARY_MOTION_GRACE_SECONDS = 0.6

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._activation = ActivationTracker()
        self._secondary = SecondaryGestureInterpreter(
            motion_grace_seconds=self.SECONDARY_MOTION_GRACE_SECONDS
        )
        self._command_decision = CommandDecision()
        self._emit = EmitDebounce()
        self._volume = MotionJoystickState()
        self._pointer = MotionJoystickState()
        self.secondary_previous_gesture: str | None = None
        self._secondary_pose_candidate: str | None = None
        self._secondary_pose_candidate_frames = 0
        self._secondary_pose_blocked_reason: str | None = None

    def update_config(self, config: AppConfig) -> None:
        self._config = config

    def evaluate(
        self,
        hand_states: list[HandState],
        now: float,
        pointer_reference_size: float = 1.0,
    ) -> GestureDecision:
        primary_anchor = self._activation.position
        if self._activation.position is None:
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
                anchor_locked = self._motion_anchor_locked()
                if anchor_locked:
                    self._mark_motion_grace("primary_grace")
                else:
                    self.reset_motion_tracking()
                return GestureDecision(
                    command_gesture=None,
                    activated=True,
                    debug_message=(
                        f"hands={len(hand_states)} activated=True "
                        f"gestures={debug_gestures} primary_temporarily_lost "
                        f"primary_index=none secondary_index=none "
                        f"zoom_hands=0 "
                        f"pointer_state={self._debug_pointer_state(None)} "
                        f"volume_state={self._debug_volume_state()} "
                        f"zoom_freeze_reason={'motion_anchor' if anchor_locked else 'primary_grace'} "
                        f"anchor_locked={anchor_locked} "
                        f"{hand_debug}"
                    ),
                    primary_temporarily_lost=True,
                    freeze_zoom=anchor_locked,
                    anchor_locked=anchor_locked,
                    pointer_debug=self._pointer_debug(None),
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
            if not self._motion_anchor_locked():
                self.reset_motion_tracking()

        primary_gesture = primary_hand.gesture
        self._activation.update_seen(primary_hand, now)
        secondary_gesture = secondary_hand.gesture if secondary_hand else None
        secondary_center = secondary_hand.center if secondary_hand else None
        secondary_size = secondary_hand.size if secondary_hand else 0.0
        zoom_landmarks = [primary_hand.landmarks]
        if secondary_hand is not None:
            zoom_landmarks.append(secondary_hand.landmarks)
            self._secondary.record_seen(now)
        freeze_zoom = secondary_hand is not None or self._secondary_missing_within_grace(now)
        zoom_freeze_reason = self._zoom_freeze_reason(secondary_hand, now)
        secondary_command_gesture = self._secondary_command_gesture(
            secondary_gesture,
            secondary_size,
        )
        secondary_motion_gesture = self._secondary_motion_gesture(
            secondary_gesture,
            secondary_command_gesture,
        )
        effective_secondary_gesture = self._effective_secondary_motion_gesture(
            secondary_motion_gesture,
            now,
        )

        command_gesture = None
        volume_gesture = None
        pointer_gesture = None
        mic_gesture = None
        volume_distance = 0.0
        pointer_distance = 0.0
        pointer_position = None
        self._pointer.last_blocked_reason = None
        self._volume.last_blocked_reason = None
        self._reset_pointer_diagnostics()
        self._reset_volume_diagnostics()

        command_gesture = self._command_decision.evaluate(
            self._activation.previous_gesture,
            primary_gesture,
            self.secondary_previous_gesture,
            secondary_command_gesture,
            now,
            self._config.gesture.home_chord_seconds,
        )
        if command_gesture == GESTURE_HOME:
            self.reset_motion_tracking()

        if secondary_hand is None:
            if self._secondary_missing_within_grace(now):
                self._mark_motion_grace("secondary_grace")
            elif self._motion_anchor_locked():
                self._mark_motion_grace("secondary_lost")
            else:
                self.reset_motion_tracking()

        if command_gesture is None and secondary_hand is not None:
            pinch_commandable = (
                secondary_command_gesture == GESTURE_PINCH
                or secondary_gesture == DEBUG_UNKNOWN
            )
            point_commandable = (
                secondary_command_gesture == GESTURE_POINT
                or secondary_gesture == DEBUG_UNKNOWN
            )
            if (
                effective_secondary_gesture == GESTURE_PINCH
                and pinch_commandable
                and secondary_center is not None
            ):
                self._reset_pointer_tracking()
                if not isinstance(self._volume.anchor, float):
                    self._volume.anchor = secondary_center[1]
                volume_distance = self._scaled_distance(
                    secondary_size,
                    self._config.gesture.volume_distance_ratio,
                    self._config.gesture.volume_min_distance,
                    self._config.gesture.volume_max_distance,
                )
                volume_candidate = classify_volume_joystick(
                    self._volume.anchor if isinstance(self._volume.anchor, float) else None,
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
            elif effective_secondary_gesture == GESTURE_PINCH:
                self._mark_motion_grace("motion_grace")
            elif effective_secondary_gesture != GESTURE_PINCH:
                if self._volume.anchor is not None:
                    if self._explicit_non_motion_secondary(secondary_gesture):
                        self._reset_volume_tracking()
                    else:
                        self._mark_motion_grace("motion_lost")
                else:
                    self._reset_volume_tracking()

            if (
                command_gesture is None
                and effective_secondary_gesture == GESTURE_POINT
                and point_commandable
            ):
                pointer_position = self._pointer_position(secondary_hand)
                if not isinstance(self._pointer.anchor, tuple):
                    self._pointer.anchor = pointer_position
                pointer_distance = self._pointer_distance(pointer_reference_size)
                pointer_candidate = classify_pointer_joystick(
                    self._pointer.anchor if isinstance(self._pointer.anchor, tuple) else None,
                    pointer_position,
                    pointer_distance,
                    self._config.gesture.pointer_dominance,
                    GESTURE_POINT,
                )
                self._record_pointer_decision(pointer_candidate)
                pointer_gesture = self._pointer_joystick_command(
                    pointer_candidate,
                    pointer_position,
                    now,
                )
                command_gesture = pointer_gesture
            elif command_gesture is None and effective_secondary_gesture == GESTURE_POINT:
                self._mark_motion_grace("motion_grace")
            elif effective_secondary_gesture != GESTURE_POINT:
                if self._pointer.anchor is not None:
                    if self._explicit_non_motion_secondary(secondary_gesture):
                        self._reset_pointer_tracking()
                    else:
                        self._mark_motion_grace("motion_lost")
                else:
                    self._reset_pointer_tracking()

            if command_gesture is None and secondary_command_gesture == GESTURE_TWO_FINGERS:
                mic_gesture = GESTURE_MIC
                command_gesture = mic_gesture
            elif secondary_command_gesture != GESTURE_TWO_FINGERS:
                mic_gesture = None

        self._activation.previous_gesture = primary_gesture
        if secondary_command_gesture is not None:
            self.secondary_previous_gesture = secondary_command_gesture
        elif secondary_hand is None:
            self.secondary_previous_gesture = None

        anchor_locked = self._motion_anchor_locked()
        freeze_zoom = freeze_zoom or anchor_locked
        if anchor_locked:
            zoom_freeze_reason = "motion_anchor"

        return GestureDecision(
            command_gesture=command_gesture,
            activated=True,
            debug_message=(
                f"hands={len(hand_states)} activated=True "
                f"gestures={debug_gestures} "
                f"primary={primary_gesture or DEBUG_UNKNOWN} "
                f"secondary={secondary_gesture or DEBUG_NONE} "
                f"effective_secondary={effective_secondary_gesture or DEBUG_NONE} "
                f"secondary_command={secondary_command_gesture or DEBUG_NONE} "
                f"secondary_pose_frames={self._secondary_pose_candidate_frames} "
                f"secondary_pose_blocked={self._secondary_pose_blocked_reason or DEBUG_NONE} "
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
                f"zoom_freeze_reason={zoom_freeze_reason} "
                f"anchor_locked={anchor_locked} "
                f"{hand_debug}"
            ),
            freeze_zoom=freeze_zoom,
            anchor_locked=anchor_locked,
            zoom_landmarks=zoom_landmarks,
            pointer_debug=self._pointer_debug(pointer_position),
        )

    def should_emit(self, command_gesture: str, command: str | None, now: float) -> bool:
        return self._emit.should_emit(
            command_gesture,
            now,
            self._config.gesture.debounce_seconds,
        )

    def record_emit(self, command_gesture: str, now: float) -> None:
        self._emit.record_emit(command_gesture, now)

    def record_idle(self) -> None:
        self._emit.record_idle()

    def reset_motion_tracking(self) -> None:
        self._reset_volume_tracking()
        self._reset_pointer_tracking()

    def _reset_activation(self) -> None:
        self._activation.reset()
        self.secondary_previous_gesture = None
        self._reset_secondary_pose_tracking()
        self._secondary.reset()
        self._emit.record_idle()
        self._command_decision.reset()
        self._reset_volume_tracking()
        self._reset_pointer_tracking()

    def _volume_joystick_command(
        self,
        decision: JoystickDecision,
        current_y: float,
        now: float,
    ) -> str | None:
        return self._volume.command(
            decision,
            current_y,
            now,
            self._config.gesture.debounce_seconds,
        )

    def _pointer_joystick_command(
        self,
        decision: JoystickDecision,
        current_position: tuple[float, float],
        now: float,
    ) -> str | None:
        return self._pointer.command(
            decision,
            current_position,
            now,
            self._config.gesture.debounce_seconds,
        )

    def _record_volume_decision(self, decision: JoystickDecision) -> None:
        self._volume.record_decision(decision)

    def _record_pointer_decision(self, decision: JoystickDecision) -> None:
        self._pointer.record_decision(decision)

    def _reset_volume_tracking(self) -> None:
        self._volume.reset_tracking()

    def _reset_volume_motion_state(self) -> None:
        self._volume.reset_motion_state()

    def _reset_volume_diagnostics(self) -> None:
        self._volume.reset_diagnostics()

    def _reset_pointer_tracking(self) -> None:
        self._pointer.reset_tracking()

    def _reset_pointer_motion_state(self) -> None:
        self._pointer.reset_motion_state()

    def _reset_pointer_diagnostics(self) -> None:
        self._pointer.reset_diagnostics()

    def _mark_motion_grace(self, reason: str) -> None:
        if self._pointer.anchor is not None:
            self._pointer.last_blocked_reason = reason
        if self._volume.anchor is not None:
            self._volume.last_blocked_reason = reason

    def _motion_anchor_locked(self) -> bool:
        return self._pointer.anchor is not None or self._volume.anchor is not None

    def _secondary_motion_gesture(
        self,
        secondary_gesture: str | None,
        secondary_command_gesture: str | None,
    ) -> str | None:
        if secondary_gesture is None:
            return None
        if isinstance(self._pointer.anchor, tuple) and secondary_gesture != GESTURE_POINT:
            return DEBUG_UNKNOWN
        if isinstance(self._volume.anchor, float) and secondary_gesture != GESTURE_PINCH:
            return DEBUG_UNKNOWN
        if secondary_gesture in {GESTURE_PINCH, GESTURE_POINT}:
            if secondary_command_gesture == secondary_gesture:
                return secondary_gesture
            return DEBUG_UNKNOWN
        return DEBUG_UNKNOWN

    @staticmethod
    def _explicit_non_motion_secondary(secondary_gesture: str | None) -> bool:
        return (
            secondary_gesture is not None
            and secondary_gesture != DEBUG_UNKNOWN
            and secondary_gesture not in {GESTURE_PINCH, GESTURE_POINT}
        )

    def _effective_secondary_motion_gesture(
        self,
        secondary_gesture: str | None,
        now: float,
    ) -> str | None:
        return self._secondary.effective_motion_gesture(secondary_gesture, now)

    def _secondary_command_gesture(
        self,
        secondary_gesture: str | None,
        secondary_size: float,
    ) -> str | None:
        self._secondary_pose_blocked_reason = None

        if secondary_gesture is None:
            self._reset_secondary_pose_tracking()
            return None

        if (
            secondary_gesture in SECONDARY_SIZE_GATED_GESTURES
            and secondary_size < SECONDARY_COMMAND_MIN_HAND_SIZE
        ):
            self._reset_secondary_pose_tracking()
            self._secondary_pose_blocked_reason = "hand_too_small"
            return None

        if secondary_gesture not in SECONDARY_DISCRETE_COMMAND_GESTURES:
            self._secondary_pose_candidate = secondary_gesture
            self._secondary_pose_candidate_frames = 1
            return secondary_gesture

        if secondary_gesture == self._secondary_pose_candidate:
            self._secondary_pose_candidate_frames += 1
        else:
            self._secondary_pose_candidate = secondary_gesture
            self._secondary_pose_candidate_frames = 1

        if (
            self._secondary_pose_candidate_frames
            < SECONDARY_DISCRETE_COMMAND_STABLE_FRAMES
        ):
            self._secondary_pose_blocked_reason = "settling_pose"
            return None

        return secondary_gesture

    def _reset_secondary_pose_tracking(self) -> None:
        self._secondary_pose_candidate = None
        self._secondary_pose_candidate_frames = 0

    def _secondary_missing_within_grace(self, now: float) -> bool:
        return self._secondary.missing_within_grace(now)

    def _zoom_freeze_reason(self, secondary_hand: HandState | None, now: float) -> str:
        return self._secondary.zoom_freeze_reason(secondary_hand, now)

    def _pointer_position(self, secondary_hand: HandState) -> tuple[float, float]:
        if len(secondary_hand.landmarks) > LANDMARK_INDEX_TIP:
            self._pointer.position_source = "index_tip"
            return landmark_position(secondary_hand.landmarks, LANDMARK_INDEX_TIP)

        self._pointer.position_source = "center"
        return secondary_hand.center

    def _primary_missing_within_grace(self, now: float) -> bool:
        return self._activation.missing_within_grace(self._config, now)

    def _primary_hand_index(self, hands: list[HandState]) -> int | None:
        return self._activation.find_primary_index(hands, self._config)

    def _distance_from_primary(self, hand: HandState) -> float:
        return self._activation.distance_from_primary(hand)

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

    def _pointer_distance(self, reference_size: float) -> float:
        return max(0.0, reference_size) * self._config.gesture.pointer_screen_radius_ratio
