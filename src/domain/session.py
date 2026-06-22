from src.domain.constants import (
    DEBUG_NONE,
    DEBUG_UNKNOWN,
    GESTURE_FIST,
    GESTURE_HOME,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_POINT,
)
from src.domain.landmarks import LANDMARK_INDEX_TIP, landmark_position
from src.domain.motion_filter import (
    JoystickDecision,
    classify_pointer_joystick,
    classify_volume_joystick,
)
from src.domain.activation_tracker import ActiveHandTracker
from src.domain.command_decision import (
    CommandDecision,
    EmitDebounce,
    TwoFingerBackDecision,
)
from src.domain.motion_gesture import (
    MotionGestureInterpreter,
    MotionJoystickState,
)
from src.domain.session_debug import GestureSessionDebugMixin
from src.domain.session_types import GestureDecision, HandState
from src.shared.config import AppConfig


MOTION_COMMAND_MIN_HAND_SIZE = 0.10
MOTION_COMMAND_GESTURES = {
    GESTURE_PINCH,
    GESTURE_POINT,
}


class GestureSession(GestureSessionDebugMixin):
    MOTION_GRACE_SECONDS = 0.6

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._active = ActiveHandTracker()
        self._motion = MotionGestureInterpreter(
            motion_grace_seconds=self.MOTION_GRACE_SECONDS
        )
        self._command_decision = CommandDecision()
        self._two_finger_back = TwoFingerBackDecision()
        self._emit = EmitDebounce()
        self._volume = MotionJoystickState()
        self._pointer = MotionJoystickState()
        self._pose_blocked_reason: str | None = None

    def update_config(self, config: AppConfig) -> None:
        self._config = config

    def evaluate(
        self,
        hand_states: list[HandState],
        now: float,
        pointer_reference_size: float = 1.0,
    ) -> GestureDecision:
        active_anchor = self._active.position
        active_index = self._active_hand_index(hand_states)
        active_hand = hand_states[active_index] if active_index is not None else None
        debug_gestures = [hand.gesture or DEBUG_UNKNOWN for hand in hand_states]
        hand_debug = self._debug_hands(hand_states, active_anchor)

        if active_hand is None:
            if self._active_missing_within_grace(now):
                command_gesture = self._command_decision.evaluate(
                    self._active.previous_gesture,
                    None,
                    now,
                    self._config.gesture.fist_hold_home_seconds,
                )
                anchor_locked = self._motion_anchor_locked()
                if anchor_locked:
                    self._mark_motion_grace("active_hand_grace")
                else:
                    self.reset_motion_tracking()
                return GestureDecision(
                    command_gesture=command_gesture,
                    activated=True,
                    debug_message=(
                        f"hands={len(hand_states)} activated=True "
                        f"gestures={debug_gestures} active_hand_temporarily_lost "
                        f"command={command_gesture or DEBUG_NONE} "
                        f"active_index=none zoom_hands=0 "
                        f"pointer_state={self._debug_pointer_state(None)} "
                        f"volume_state={self._debug_volume_state()} "
                        f"zoom_freeze_reason={'motion_anchor' if anchor_locked else 'active_hand_grace'} "
                        f"anchor_locked={anchor_locked} {hand_debug}"
                    ),
                    active_temporarily_lost=True,
                    freeze_zoom=anchor_locked,
                    anchor_locked=anchor_locked,
                    pointer_debug=self._pointer_debug(None),
                    volume_debug=self._volume_debug(None),
                )

            self._reset_activation()
            return GestureDecision(
                command_gesture=None,
                activated=False,
                debug_message=(
                    f"hands={len(hand_states)} activated=False "
                    f"gestures={debug_gestures} need_upright_open_palm "
                    f"active_index=none zoom_hands=0 {hand_debug}"
                ),
            )

        if not active_hand.upright:
            self._reset_activation()
            return GestureDecision(
                command_gesture=None,
                activated=False,
                debug_message=(
                    f"hands={len(hand_states)} activated=False "
                    f"gestures={debug_gestures} need_upright_open_palm "
                    f"active_index={active_index} zoom_hands=0 {hand_debug}"
                ),
            )

        active_gesture = active_hand.gesture
        self._active.update_seen(active_hand, now)
        self._motion.record_seen(now)
        zoom_landmarks = [active_hand.landmarks]
        active_size = active_hand.size
        active_center = active_hand.center

        command_gesture = None
        volume_gesture = None
        pointer_gesture = None
        two_finger_back_gesture = None
        volume_distance = 0.0
        pointer_distance = 0.0
        volume_position = None
        pointer_position = None
        self._pointer.last_blocked_reason = None
        self._volume.last_blocked_reason = None
        self._reset_pointer_diagnostics()
        self._reset_volume_diagnostics()

        command_gesture = self._command_decision.evaluate(
            self._active.previous_gesture,
            active_gesture,
            now,
            self._config.gesture.fist_hold_home_seconds,
        )
        if command_gesture == GESTURE_HOME:
            self.reset_motion_tracking()

        commandable_motion_gesture = self._commandable_motion_gesture(
            active_gesture,
            active_size,
            pointer_reference_size,
        )
        motion_gesture = self._motion_gesture(
            active_gesture,
            commandable_motion_gesture,
        )
        effective_motion_gesture = self._effective_motion_gesture(motion_gesture, now)

        if command_gesture is None:
            pinch_commandable = (
                commandable_motion_gesture == GESTURE_PINCH
                or active_gesture == DEBUG_UNKNOWN
            )
            point_commandable = (
                commandable_motion_gesture == GESTURE_POINT
                or active_gesture == DEBUG_UNKNOWN
            )
            if (
                effective_motion_gesture == GESTURE_PINCH
                and pinch_commandable
            ):
                self._reset_pointer_tracking()
                volume_position = active_center
                if not isinstance(self._volume.anchor, float):
                    self._volume.anchor = active_center[1]
                    self._volume.visual_anchor = active_center
                volume_distance = self._scaled_distance(
                    active_size,
                    self._config.gesture.volume_distance_ratio,
                    self._config.gesture.volume_min_distance,
                    self._config.gesture.volume_max_distance,
                )
                volume_candidate = classify_volume_joystick(
                    self._volume.anchor if isinstance(self._volume.anchor, float) else None,
                    active_center[1],
                    volume_distance,
                )
                self._record_volume_decision(volume_candidate)
                volume_gesture = self._volume_joystick_command(
                    volume_candidate,
                    active_center[1],
                    now,
                )
                command_gesture = volume_gesture
            elif effective_motion_gesture == GESTURE_PINCH:
                self._mark_motion_grace("motion_grace")
            elif effective_motion_gesture != GESTURE_PINCH:
                if self._volume.anchor is not None:
                    if self._explicit_non_motion_gesture(active_gesture):
                        self._reset_volume_tracking()
                    else:
                        self._mark_motion_grace("motion_lost")
                else:
                    self._reset_volume_tracking()

            if (
                command_gesture is None
                and effective_motion_gesture == GESTURE_POINT
                and point_commandable
            ):
                pointer_position = self._pointer_position(active_hand)
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
            elif command_gesture is None and effective_motion_gesture == GESTURE_POINT:
                self._mark_motion_grace("motion_grace")
            elif effective_motion_gesture != GESTURE_POINT:
                if self._pointer.anchor is not None:
                    if self._explicit_non_motion_gesture(active_gesture):
                        self._reset_pointer_tracking()
                    else:
                        self._mark_motion_grace("motion_lost")
                else:
                    self._reset_pointer_tracking()

            if command_gesture is None:
                two_finger_back_gesture = self._two_finger_back.evaluate(active_gesture)
                command_gesture = two_finger_back_gesture

        self._active.previous_gesture = active_gesture
        anchor_locked = self._motion_anchor_locked()
        freeze_zoom = anchor_locked
        zoom_freeze_reason = "motion_anchor" if anchor_locked else "none"

        return GestureDecision(
            command_gesture=command_gesture,
            activated=True,
            debug_message=(
                f"hands={len(hand_states)} activated=True "
                f"gestures={debug_gestures} "
                f"active={active_gesture or DEBUG_UNKNOWN} "
                f"effective_motion={effective_motion_gesture or DEBUG_NONE} "
                f"motion_command={commandable_motion_gesture or DEBUG_NONE} "
                f"pose_blocked={self._pose_blocked_reason or DEBUG_NONE} "
                f"volume={volume_gesture or DEBUG_NONE} "
                f"pointer={pointer_gesture or DEBUG_NONE} "
                f"two_finger_back={two_finger_back_gesture or DEBUG_NONE} "
                f"two_finger_back_state={self._debug_two_finger_back_state()} "
                f"size={active_size:.2f} "
                f"pointer_distance={pointer_distance:.2f} "
                f"volume_distance={volume_distance:.2f} "
                f"command={command_gesture or DEBUG_NONE} "
                f"pointer_state={self._debug_pointer_state(pointer_position)} "
                f"volume_state={self._debug_volume_state()} "
                f"active_index={active_index} "
                f"zoom_hands={len(zoom_landmarks)} "
                f"zoom_freeze_reason={zoom_freeze_reason} "
                f"anchor_locked={anchor_locked} {hand_debug}"
            ),
            freeze_zoom=freeze_zoom,
            anchor_locked=anchor_locked,
            zoom_landmarks=zoom_landmarks,
            pointer_debug=self._pointer_debug(pointer_position),
            volume_debug=self._volume_debug(volume_position),
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
        self._active.reset()
        self._motion.reset()
        self._emit.record_idle()
        self._command_decision.reset()
        self._two_finger_back.reset()
        self._reset_volume_tracking()
        self._reset_pointer_tracking()
        self._pose_blocked_reason = None

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

    def _reset_pointer_tracking(self) -> None:
        self._pointer.reset_tracking()

    def _reset_volume_diagnostics(self) -> None:
        self._volume.reset_diagnostics()

    def _reset_pointer_diagnostics(self) -> None:
        self._pointer.reset_diagnostics()

    def _mark_motion_grace(self, reason: str) -> None:
        if self._pointer.anchor is not None:
            self._pointer.last_blocked_reason = reason
        if self._volume.anchor is not None:
            self._volume.last_blocked_reason = reason

    def _debug_two_finger_back_state(self) -> str:
        return (
            f"armed={self._two_finger_back.armed}"
            f":frames={self._two_finger_back.two_finger_frames}"
            f":required={self._two_finger_back.required_frames}"
        )

    def _motion_anchor_locked(self) -> bool:
        return self._pointer.anchor is not None or self._volume.anchor is not None

    def _motion_gesture(
        self,
        gesture: str | None,
        commandable_motion_gesture: str | None,
    ) -> str | None:
        if gesture is None:
            return None
        if isinstance(self._pointer.anchor, tuple) and gesture != GESTURE_POINT:
            return DEBUG_UNKNOWN
        if isinstance(self._volume.anchor, float) and gesture != GESTURE_PINCH:
            return DEBUG_UNKNOWN
        if gesture in MOTION_COMMAND_GESTURES:
            if commandable_motion_gesture == gesture:
                return gesture
            return DEBUG_UNKNOWN
        return DEBUG_UNKNOWN

    @staticmethod
    def _explicit_non_motion_gesture(gesture: str | None) -> bool:
        return (
            gesture is not None
            and gesture != DEBUG_UNKNOWN
            and gesture not in MOTION_COMMAND_GESTURES
        )

    def _effective_motion_gesture(self, gesture: str | None, now: float) -> str | None:
        return self._motion.effective_motion_gesture(gesture, now)

    def _commandable_motion_gesture(
        self,
        gesture: str | None,
        hand_size: float,
        reference_size: float,
    ) -> str | None:
        self._pose_blocked_reason = None
        if gesture not in MOTION_COMMAND_GESTURES:
            return None
        if (
            self._relative_hand_size(hand_size, reference_size)
            < MOTION_COMMAND_MIN_HAND_SIZE
        ):
            self._pose_blocked_reason = "hand_too_small"
            return None
        return gesture

    @staticmethod
    def _relative_hand_size(hand_size: float, reference_size: float) -> float:
        if reference_size <= 0:
            return hand_size
        return hand_size / reference_size

    def _pointer_position(self, active_hand: HandState) -> tuple[float, float]:
        if len(active_hand.landmarks) > LANDMARK_INDEX_TIP:
            self._pointer.position_source = "index_tip"
            return landmark_position(active_hand.landmarks, LANDMARK_INDEX_TIP)

        self._pointer.position_source = "center"
        return active_hand.center

    def _active_missing_within_grace(self, now: float) -> bool:
        return self._active.missing_within_grace(self._config, now)

    def _active_hand_index(self, hands: list[HandState]) -> int | None:
        return self._active.find_active_index(hands, self._config)

    def _distance_from_active(self, hand: HandState) -> float:
        return self._active.distance_from_active(hand)

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
