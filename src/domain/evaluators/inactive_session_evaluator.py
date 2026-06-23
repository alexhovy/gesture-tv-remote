from src.domain.session.session_debug import SessionDebugRenderer, build_debug_snapshot
from src.domain.session.session_state import GestureSessionState
from src.domain.session.session_types import GestureDecision, HandState
from src.shared.config import AppConfig


class InactiveSessionEvaluator:
    def __init__(self, debug_renderer: SessionDebugRenderer) -> None:
        self._debug_renderer = debug_renderer

    def evaluate(
        self,
        state: GestureSessionState,
        config: AppConfig,
        hand_states: list[HandState],
        active_anchor: tuple[float, float] | None,
        active_index: int | None = None,
        reset: bool = True,
    ) -> GestureDecision:
        if reset:
            state.reset_activation()
        return GestureDecision(
            command_gesture=None,
            activated=False,
            debug_message=self._debug_renderer.render_inactive(
                build_debug_snapshot(state, config, hand_states, active_anchor),
                active_index,
            ),
        )
