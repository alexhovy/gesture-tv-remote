from src.domain.evaluators.active_session_evaluator import ActiveSessionEvaluator
from src.domain.evaluators.inactive_session_evaluator import InactiveSessionEvaluator
from src.domain.evaluators.lost_session_evaluator import LostSessionEvaluator
from src.domain.evaluators.motion_interaction_coordinator import (
    MotionInteractionCoordinator,
)
from src.domain.session.session_debug import SessionDebugRenderer
from src.domain.session.session_state import GestureSessionState
from src.domain.session.session_types import GestureDecision, HandState
from src.shared.config import AppConfig


class GestureSession:
    MOTION_GRACE_SECONDS = 0.6

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._state = GestureSessionState.create(
            motion_grace_seconds=self.MOTION_GRACE_SECONDS
        )
        debug_renderer = SessionDebugRenderer()
        inactive_evaluator = InactiveSessionEvaluator(debug_renderer)
        self._lost_evaluator = LostSessionEvaluator(
            debug_renderer,
            inactive_evaluator,
        )
        self._inactive_evaluator = inactive_evaluator
        self._active_evaluator = ActiveSessionEvaluator(
            debug_renderer,
            MotionInteractionCoordinator(),
        )

    def update_config(self, config: AppConfig) -> None:
        self._config = config

    def evaluate(
        self,
        hand_states: list[HandState],
        now: float,
        pointer_reference_size: float = 1.0,
    ) -> GestureDecision:
        active_anchor = self._state.active.position
        active_index = self._state.active.find_active_index(hand_states, self._config)
        if active_index is None and self._state.active.has_active_hand():
            active_index = self._state.active.find_continuation_open_palm_index(
                hand_states,
            )
            if active_index is not None:
                self._state.reset_for_handoff()
                active_anchor = None

        active_hand = hand_states[active_index] if active_index is not None else None

        if active_hand is None:
            return self._lost_evaluator.evaluate(
                self._state,
                self._config,
                hand_states,
                active_anchor,
                now,
            )

        if not active_hand.upright:
            return self._inactive_evaluator.evaluate(
                self._state,
                self._config,
                hand_states,
                active_anchor,
                active_index,
            )

        return self._active_evaluator.evaluate(
            self._state,
            self._config,
            hand_states,
            active_anchor,
            active_index,
            active_hand,
            now,
            pointer_reference_size,
        )

    def should_emit(
        self, command_gesture: str, command: str | None, now: float
    ) -> bool:
        return self._state.emit.should_emit(
            command_gesture,
            now,
            self._config.gesture.debounce_seconds,
        )

    def record_emit(self, command_gesture: str, now: float) -> None:
        self._state.emit.record_emit(command_gesture, now)

    def record_idle(self) -> None:
        self._state.emit.record_idle()

    def reset_motion_tracking(self) -> None:
        self._state.reset_motion_tracking()
