from src.domain.constants import GESTURE_FIST
from src.domain.evaluators.inactive_session_evaluator import InactiveSessionEvaluator
from src.domain.session.session_debug import SessionDebugRenderer, build_debug_snapshot
from src.domain.session.session_state import GestureSessionState
from src.domain.session.session_types import GestureDecision, HandState
from src.shared.config import AppConfig


class LostSessionEvaluator:
    def __init__(
        self,
        debug_renderer: SessionDebugRenderer,
        inactive_evaluator: InactiveSessionEvaluator,
    ) -> None:
        self._debug_renderer = debug_renderer
        self._inactive_evaluator = inactive_evaluator

    def evaluate(
        self,
        state: GestureSessionState,
        config: AppConfig,
        hand_states: list[HandState],
        active_anchor: tuple[float, float] | None,
        now: float,
    ) -> GestureDecision:
        if not state.active.missing_within_grace(config, now):
            return self._inactive_evaluator.evaluate(
                state,
                config,
                hand_states,
                active_anchor,
            )

        command_gesture = state.command_decision.evaluate(
            state.active.previous_gesture,
            None,
            now,
            config.gesture.fist_hold_home_seconds,
        )
        anchor_locked = state.motion_anchor_locked()
        command_pose_locked = state.active.previous_gesture == GESTURE_FIST
        freeze_zoom = anchor_locked or command_pose_locked
        zoom_freeze_reason = "none"
        if anchor_locked:
            state.mark_motion_grace("active_hand_grace")
            zoom_freeze_reason = "motion_anchor"
        elif command_pose_locked:
            state.reset_motion_tracking()
            zoom_freeze_reason = "command_pose"
        else:
            state.reset_motion_tracking()

        return GestureDecision(
            command_gesture=command_gesture,
            activated=True,
            debug_message=self._debug_renderer.render_temporarily_lost(
                build_debug_snapshot(state, config, hand_states, active_anchor),
                command_gesture,
                zoom_freeze_reason,
                anchor_locked,
            ),
            active_temporarily_lost=True,
            freeze_zoom=freeze_zoom,
            anchor_locked=anchor_locked,
            pointer_debug=self._debug_renderer.pointer_debug(state.pointer, None),
            volume_debug=self._debug_renderer.volume_debug(state.volume, None),
        )
