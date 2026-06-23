from dataclasses import dataclass

from src.domain.activation_tracker import ActiveHandTracker
from src.domain.command_decision import (
    CommandDecision,
    EmitDebounce,
    TwoFingerBackDecision,
)
from src.domain.constants import (
    DEBUG_UNKNOWN,
    GESTURE_FIST,
    GESTURE_HOME,
    GESTURE_PINCH,
    GESTURE_POINT,
)
from src.domain.evaluators.pointer_evaluator import evaluate_pointer_motion
from src.domain.evaluators.volume_evaluator import evaluate_volume_motion
from src.domain.landmarks import LANDMARK_INDEX_TIP, landmark_position
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


@dataclass(frozen=True)
class MotionCommandResult:
    command_gesture: str | None = None
    volume_gesture: str | None = None
    pointer_gesture: str | None = None
    two_finger_back_gesture: str | None = None
    volume_distance: float = 0.0
    pointer_distance: float = 0.0
    volume_position: tuple[float, float] | None = None
    pointer_position: tuple[float, float] | None = None


class ZoomLandmark:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


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

        if active_hand is None:
            return self._evaluate_missing_active_hand(
                hand_states,
                active_anchor,
                now,
            )

        if not active_hand.upright:
            self._reset_activation()
            return GestureDecision(
                command_gesture=None,
                activated=False,
                debug_message=self._inactive_debug_message(
                    hand_states,
                    active_anchor,
                    active_index,
                ),
            )

        active_gesture = active_hand.gesture
        self._active.update_seen(active_hand, now)
        self._motion.record_seen(now)
        command_pose_locked = active_gesture == GESTURE_FIST
        zoom_landmarks = (
            [] if command_pose_locked else [self._zoom_landmarks_for_hand(active_hand)]
        )
        active_size = active_hand.size

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
        motion_result = MotionCommandResult()

        if command_gesture is None:
            motion_result = self._evaluate_motion_commands(
                active_hand,
                active_gesture,
                commandable_motion_gesture,
                effective_motion_gesture,
                pointer_reference_size,
                now,
            )
            command_gesture = motion_result.command_gesture

        self._active.previous_gesture = active_gesture
        anchor_locked = self._motion_anchor_locked()
        freeze_zoom = anchor_locked or command_pose_locked
        zoom_freeze_reason = "none"
        if anchor_locked:
            zoom_freeze_reason = "motion_anchor"
        elif command_pose_locked:
            zoom_freeze_reason = "command_pose"

        return GestureDecision(
            command_gesture=command_gesture,
            activated=True,
            debug_message=self._active_debug_message(
                hand_states,
                active_anchor,
                active_index,
                active_gesture,
                effective_motion_gesture,
                commandable_motion_gesture,
                motion_result.volume_gesture,
                motion_result.pointer_gesture,
                motion_result.two_finger_back_gesture,
                active_size,
                motion_result.pointer_distance,
                motion_result.volume_distance,
                command_gesture,
                motion_result.pointer_position,
                len(zoom_landmarks),
                zoom_freeze_reason,
                anchor_locked,
            ),
            freeze_zoom=freeze_zoom,
            anchor_locked=anchor_locked,
            zoom_landmarks=zoom_landmarks,
            pointer_debug=self._pointer_debug(motion_result.pointer_position),
            volume_debug=self._volume_debug(motion_result.volume_position),
        )

    def _evaluate_missing_active_hand(
        self,
        hand_states: list[HandState],
        active_anchor: tuple[float, float] | None,
        now: float,
    ) -> GestureDecision:
        if not self._active_missing_within_grace(now):
            self._reset_activation()
            return GestureDecision(
                command_gesture=None,
                activated=False,
                debug_message=self._inactive_debug_message(hand_states, active_anchor),
            )

        command_gesture = self._command_decision.evaluate(
            self._active.previous_gesture,
            None,
            now,
            self._config.gesture.fist_hold_home_seconds,
        )
        anchor_locked = self._motion_anchor_locked()
        command_pose_locked = self._active.previous_gesture == GESTURE_FIST
        freeze_zoom = anchor_locked or command_pose_locked
        zoom_freeze_reason = "none"
        if anchor_locked:
            self._mark_motion_grace("active_hand_grace")
            zoom_freeze_reason = "motion_anchor"
        elif command_pose_locked:
            self.reset_motion_tracking()
            zoom_freeze_reason = "command_pose"
        else:
            self.reset_motion_tracking()

        return GestureDecision(
            command_gesture=command_gesture,
            activated=True,
            debug_message=self._temporarily_lost_debug_message(
                hand_states,
                active_anchor,
                command_gesture,
                zoom_freeze_reason,
                anchor_locked,
            ),
            active_temporarily_lost=True,
            freeze_zoom=freeze_zoom,
            anchor_locked=anchor_locked,
            pointer_debug=self._pointer_debug(None),
            volume_debug=self._volume_debug(None),
        )

    def _evaluate_motion_commands(
        self,
        active_hand: HandState,
        active_gesture: str | None,
        commandable_motion_gesture: str | None,
        effective_motion_gesture: str | None,
        pointer_reference_size: float,
        now: float,
    ) -> MotionCommandResult:
        volume_result = self._evaluate_volume_command(
            active_hand,
            active_gesture,
            commandable_motion_gesture,
            effective_motion_gesture,
            now,
        )
        if volume_result.command_gesture is not None:
            return volume_result

        pointer_result = self._evaluate_pointer_command(
            active_hand,
            active_gesture,
            commandable_motion_gesture,
            effective_motion_gesture,
            pointer_reference_size,
            now,
        )
        if pointer_result.command_gesture is not None:
            return MotionCommandResult(
                command_gesture=pointer_result.command_gesture,
                volume_gesture=volume_result.volume_gesture,
                pointer_gesture=pointer_result.pointer_gesture,
                volume_distance=volume_result.volume_distance,
                pointer_distance=pointer_result.pointer_distance,
                volume_position=volume_result.volume_position,
                pointer_position=pointer_result.pointer_position,
            )

        two_finger_back_gesture = self._two_finger_back.evaluate(active_gesture)
        return MotionCommandResult(
            command_gesture=two_finger_back_gesture,
            volume_gesture=volume_result.volume_gesture,
            pointer_gesture=pointer_result.pointer_gesture,
            two_finger_back_gesture=two_finger_back_gesture,
            volume_distance=volume_result.volume_distance,
            pointer_distance=pointer_result.pointer_distance,
            volume_position=volume_result.volume_position,
            pointer_position=pointer_result.pointer_position,
        )

    def _evaluate_volume_command(
        self,
        active_hand: HandState,
        active_gesture: str | None,
        commandable_motion_gesture: str | None,
        effective_motion_gesture: str | None,
        now: float,
    ) -> MotionCommandResult:
        pinch_commandable = (
            commandable_motion_gesture == GESTURE_PINCH
            or active_gesture == DEBUG_UNKNOWN
        )
        if effective_motion_gesture == GESTURE_PINCH and pinch_commandable:
            self._reset_pointer_tracking()
            volume = evaluate_volume_motion(
                self._volume,
                active_hand.center,
                active_hand.size,
                self._config,
                now,
            )
            return MotionCommandResult(
                command_gesture=volume.command_gesture,
                volume_gesture=volume.command_gesture,
                volume_distance=volume.distance,
                volume_position=volume.position,
            )

        if effective_motion_gesture == GESTURE_PINCH:
            self._mark_motion_grace("motion_grace")
        elif effective_motion_gesture != GESTURE_PINCH:
            self._clear_or_grace_volume_tracking(
                active_gesture,
                commandable_motion_gesture,
            )

        return MotionCommandResult()

    def _evaluate_pointer_command(
        self,
        active_hand: HandState,
        active_gesture: str | None,
        commandable_motion_gesture: str | None,
        effective_motion_gesture: str | None,
        pointer_reference_size: float,
        now: float,
    ) -> MotionCommandResult:
        point_commandable = (
            commandable_motion_gesture == GESTURE_POINT
            or active_gesture == DEBUG_UNKNOWN
        )
        if effective_motion_gesture == GESTURE_POINT and point_commandable:
            pointer = evaluate_pointer_motion(
                self._pointer,
                self._pointer_position(active_hand),
                pointer_reference_size,
                self._config,
                now,
            )
            return MotionCommandResult(
                command_gesture=pointer.command_gesture,
                pointer_gesture=pointer.command_gesture,
                pointer_distance=pointer.distance,
                pointer_position=pointer.position,
            )

        if effective_motion_gesture == GESTURE_POINT:
            self._mark_motion_grace("motion_grace")
        elif effective_motion_gesture != GESTURE_POINT:
            self._clear_or_grace_pointer_tracking(
                active_gesture,
                commandable_motion_gesture,
            )

        return MotionCommandResult()

    def _clear_or_grace_volume_tracking(
        self,
        active_gesture: str | None,
        commandable_motion_gesture: str | None,
    ) -> None:
        if self._volume.anchor is None:
            self._reset_volume_tracking()
        elif (
            commandable_motion_gesture == GESTURE_POINT
            or self._explicit_non_motion_gesture(active_gesture)
        ):
            self._reset_volume_tracking()
        else:
            self._mark_motion_grace("motion_lost")

    def _clear_or_grace_pointer_tracking(
        self,
        active_gesture: str | None,
        commandable_motion_gesture: str | None,
    ) -> None:
        if self._pointer.anchor is None:
            self._reset_pointer_tracking()
        elif (
            commandable_motion_gesture == GESTURE_PINCH
            or self._explicit_non_motion_gesture(active_gesture)
        ):
            self._reset_pointer_tracking()
        else:
            self._mark_motion_grace("motion_lost")

    def should_emit(
        self, command_gesture: str, command: str | None, now: float
    ) -> bool:
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

    def _zoom_landmarks_for_hand(self, hand: HandState) -> list[ZoomLandmark]:
        center_x, center_y = hand.center
        half_size = max(hand.size, 0.01) / 2
        return [
            ZoomLandmark(
                _clamp(center_x - half_size, 0.0, 1.0),
                _clamp(center_y - half_size, 0.0, 1.0),
            ),
            ZoomLandmark(
                _clamp(center_x + half_size, 0.0, 1.0),
                _clamp(center_y + half_size, 0.0, 1.0),
            ),
        ]

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
        if gesture == DEBUG_UNKNOWN:
            return DEBUG_UNKNOWN
        if gesture in MOTION_COMMAND_GESTURES:
            if commandable_motion_gesture == gesture:
                return gesture
            return DEBUG_UNKNOWN
        return None

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
