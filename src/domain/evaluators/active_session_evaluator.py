from src.domain.constants import GESTURE_FIST, GESTURE_HOME
from src.domain.evaluators.motion_interaction_coordinator import (
    MotionCommandResult,
    MotionInteractionCoordinator,
)
from src.domain.session.session_debug import (
    ActiveDebugContext,
    SessionDebugRenderer,
    build_debug_snapshot,
)
from src.domain.session.session_state import GestureSessionState
from src.domain.session.session_types import GestureDecision, HandState
from src.shared.config import AppConfig


class ZoomLandmark:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y


class ActiveSessionEvaluator:
    def __init__(
        self,
        debug_renderer: SessionDebugRenderer,
        motion_coordinator: MotionInteractionCoordinator,
    ) -> None:
        self._debug_renderer = debug_renderer
        self._motion_coordinator = motion_coordinator

    def evaluate(
        self,
        state: GestureSessionState,
        config: AppConfig,
        hand_states: list[HandState],
        active_anchor: tuple[float, float] | None,
        active_index: int,
        active_hand: HandState,
        now: float,
        pointer_reference_size: float,
    ) -> GestureDecision:
        active_gesture = active_hand.gesture
        state.active.update_seen(active_hand, now)
        state.motion.record_seen(now)
        state.reset_motion_diagnostics()

        command_pose_locked = active_gesture == GESTURE_FIST
        zoom_landmarks = (
            [] if command_pose_locked else [self._zoom_landmarks_for_hand(active_hand)]
        )

        command_gesture = state.command_decision.evaluate(
            state.active.previous_gesture,
            active_gesture,
            now,
            config.gesture.fist_hold_home_seconds,
        )
        if command_gesture == GESTURE_HOME:
            state.reset_motion_tracking()

        motion_preparation = self._motion_coordinator.prepare(
            state,
            active_gesture,
            active_hand.size,
            pointer_reference_size,
            now,
        )
        motion_result = MotionCommandResult()
        two_finger_back_gesture = None

        if command_gesture is None:
            motion_result = self._motion_coordinator.evaluate(
                state,
                active_hand,
                active_gesture,
                motion_preparation.commandable_motion_gesture,
                motion_preparation.effective_motion_gesture,
                pointer_reference_size,
                config,
                now,
            )
            command_gesture = motion_result.command_gesture

        if command_gesture is None:
            two_finger_back_gesture = state.two_finger_back.evaluate(active_gesture)
            command_gesture = two_finger_back_gesture

        state.active.previous_gesture = active_gesture
        anchor_locked = state.motion_anchor_locked()
        freeze_zoom = anchor_locked or command_pose_locked
        zoom_freeze_reason = _zoom_freeze_reason(anchor_locked, command_pose_locked)

        return GestureDecision(
            command_gesture=command_gesture,
            activated=True,
            debug_message=self._debug_renderer.render_active(
                build_debug_snapshot(state, config, hand_states, active_anchor),
                ActiveDebugContext(
                    active_index=active_index,
                    active_gesture=active_gesture,
                    effective_motion_gesture=(
                        motion_preparation.effective_motion_gesture
                    ),
                    commandable_motion_gesture=(
                        motion_preparation.commandable_motion_gesture
                    ),
                    volume_gesture=motion_result.volume_gesture,
                    pointer_gesture=motion_result.pointer_gesture,
                    two_finger_back_gesture=two_finger_back_gesture,
                    active_size=active_hand.size,
                    pointer_distance=motion_result.pointer_distance,
                    volume_distance=motion_result.volume_distance,
                    command_gesture=command_gesture,
                    pointer_position=motion_result.pointer_position,
                    zoom_hands=len(zoom_landmarks),
                    zoom_freeze_reason=zoom_freeze_reason,
                    anchor_locked=anchor_locked,
                ),
            ),
            freeze_zoom=freeze_zoom,
            anchor_locked=anchor_locked,
            zoom_landmarks=zoom_landmarks,
            pointer_debug=self._debug_renderer.pointer_debug(
                state.pointer,
                motion_result.pointer_position,
            ),
            volume_debug=self._debug_renderer.volume_debug(
                state.volume,
                motion_result.volume_position,
            ),
        )

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


def _zoom_freeze_reason(anchor_locked: bool, command_pose_locked: bool) -> str:
    if anchor_locked:
        return "motion_anchor"
    if command_pose_locked:
        return "command_pose"
    return "none"


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
