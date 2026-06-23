import unittest

from src.domain.constants import (
    GESTURE_FIST,
    GESTURE_OPEN_PALM,
    GESTURE_OPEN_TO_FIST,
    GESTURE_PINCH,
    GESTURE_POINT,
    GESTURE_POINT_RIGHT,
    GESTURE_VOLUME_DOWN,
)
from src.domain.evaluators.active_session_evaluator import ActiveSessionEvaluator
from src.domain.evaluators.inactive_session_evaluator import InactiveSessionEvaluator
from src.domain.evaluators.lost_session_evaluator import LostSessionEvaluator
from src.domain.evaluators.motion_interaction_coordinator import (
    MotionInteractionCoordinator,
)
from src.domain.session.session_debug import (
    ActiveDebugContext,
    SessionDebugRenderer,
    build_debug_snapshot,
)
from src.domain.session.session_state import GestureSessionState
from tests.config_helpers import app_config
from tests.session_helpers import hand_state


class SessionPhaseEvaluatorTests(unittest.TestCase):
    def test_inactive_evaluator_resets_state_and_reports_inactive(self) -> None:
        state = _state()
        renderer = SessionDebugRenderer()
        evaluator = InactiveSessionEvaluator(renderer)
        state.active.position = (0.20, 0.50)
        state.pointer.anchor = (0.50, 0.50)

        decision = evaluator.evaluate(
            state,
            app_config(),
            [hand_state(GESTURE_POINT, center=(0.20, 0.50), size=0.20)],
            active_anchor=state.active.position,
        )

        self.assertFalse(decision.activated)
        self.assertIsNone(state.active.position)
        self.assertIsNone(state.pointer.anchor)
        self.assertIn("need_upright_open_palm", decision.debug_message)

    def test_lost_evaluator_keeps_session_inside_grace(self) -> None:
        config = app_config(active_hand_lost_grace_seconds=0.35)
        state = _state()
        renderer = SessionDebugRenderer()
        evaluator = LostSessionEvaluator(renderer, InactiveSessionEvaluator(renderer))
        state.active.position = (0.20, 0.50)
        state.active.last_seen_time = 0.0
        state.active.previous_gesture = GESTURE_OPEN_PALM

        decision = evaluator.evaluate(state, config, [], state.active.position, now=0.2)

        self.assertTrue(decision.activated)
        self.assertTrue(decision.active_temporarily_lost)
        self.assertIn("active_hand_temporarily_lost", decision.debug_message)

    def test_lost_evaluator_resets_after_grace_expires(self) -> None:
        config = app_config(active_hand_lost_grace_seconds=0.35)
        state = _state()
        renderer = SessionDebugRenderer()
        evaluator = LostSessionEvaluator(renderer, InactiveSessionEvaluator(renderer))
        state.active.position = (0.20, 0.50)
        state.active.last_seen_time = 0.0

        decision = evaluator.evaluate(
            state,
            config,
            [],
            active_anchor=state.active.position,
            now=0.36,
        )

        self.assertFalse(decision.activated)
        self.assertIsNone(state.active.position)

    def test_active_evaluator_routes_select_command(self) -> None:
        config = app_config()
        state = _state()
        renderer = SessionDebugRenderer()
        evaluator = ActiveSessionEvaluator(renderer, MotionInteractionCoordinator())
        active_anchor = (0.20, 0.50)
        state.active.position = active_anchor
        state.active.previous_gesture = GESTURE_FIST
        state.command_decision.fist_started_at = 0.1
        open_hand = hand_state(GESTURE_OPEN_PALM, center=active_anchor, size=0.20)

        decision = evaluator.evaluate(
            state,
            config,
            [open_hand],
            active_anchor,
            active_index=0,
            active_hand=open_hand,
            now=0.2,
            pointer_reference_size=1.0,
        )

        self.assertEqual(decision.command_gesture, GESTURE_OPEN_TO_FIST)
        self.assertIn("command=OPEN_TO_FIST", decision.debug_message)


class MotionInteractionCoordinatorTests(unittest.TestCase):
    def test_coordinator_selects_pointer_interaction(self) -> None:
        state = _state()
        coordinator = MotionInteractionCoordinator()
        config = app_config()
        start = hand_state(
            GESTURE_POINT,
            center=(0.50, 0.50),
            size=0.20,
            index_position=(0.50, 0.50),
        )
        moved = hand_state(
            GESTURE_POINT,
            center=(0.67, 0.50),
            size=0.20,
            index_position=(0.67, 0.50),
        )

        preparation = coordinator.prepare(state, start.gesture, start.size, 1.0, 0.1)
        coordinator.evaluate(
            state,
            start,
            start.gesture,
            preparation.commandable_motion_gesture,
            preparation.effective_motion_gesture,
            1.0,
            config,
            0.1,
        )
        preparation = coordinator.prepare(state, moved.gesture, moved.size, 1.0, 0.2)
        result = coordinator.evaluate(
            state,
            moved,
            moved.gesture,
            preparation.commandable_motion_gesture,
            preparation.effective_motion_gesture,
            1.0,
            config,
            0.2,
        )

        self.assertEqual(result.command_gesture, GESTURE_POINT_RIGHT)
        self.assertEqual(result.pointer_gesture, GESTURE_POINT_RIGHT)

    def test_coordinator_selects_volume_interaction(self) -> None:
        state = _state()
        coordinator = MotionInteractionCoordinator()
        config = app_config()
        start = hand_state(GESTURE_PINCH, center=(0.70, 0.50), size=0.20)
        moved = hand_state(GESTURE_PINCH, center=(0.70, 0.70), size=0.20)

        preparation = coordinator.prepare(state, start.gesture, start.size, 1.0, 0.1)
        coordinator.evaluate(
            state,
            start,
            start.gesture,
            preparation.commandable_motion_gesture,
            preparation.effective_motion_gesture,
            1.0,
            config,
            0.1,
        )
        preparation = coordinator.prepare(state, moved.gesture, moved.size, 1.0, 0.2)
        result = coordinator.evaluate(
            state,
            moved,
            moved.gesture,
            preparation.commandable_motion_gesture,
            preparation.effective_motion_gesture,
            1.0,
            config,
            0.2,
        )

        self.assertEqual(result.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertEqual(result.volume_gesture, GESTURE_VOLUME_DOWN)

    def test_coordinator_selects_neither_for_non_motion_gesture(self) -> None:
        state = _state()
        coordinator = MotionInteractionCoordinator()
        hand = hand_state(GESTURE_OPEN_PALM, center=(0.50, 0.50), size=0.20)

        preparation = coordinator.prepare(state, hand.gesture, hand.size, 1.0, 0.1)
        result = coordinator.evaluate(
            state,
            hand,
            hand.gesture,
            preparation.commandable_motion_gesture,
            preparation.effective_motion_gesture,
            1.0,
            app_config(),
            0.1,
        )

        self.assertIsNone(result.command_gesture)
        self.assertIsNone(state.pointer.anchor)
        self.assertIsNone(state.volume.anchor)

    def test_coordinator_clears_pointer_when_volume_starts(self) -> None:
        state = _state()
        state.pointer.anchor = (0.50, 0.50)
        coordinator = MotionInteractionCoordinator()
        hand = hand_state(GESTURE_PINCH, center=(0.70, 0.50), size=0.20)

        preparation = coordinator.prepare(state, hand.gesture, hand.size, 1.0, 0.1)
        coordinator.evaluate(
            state,
            hand,
            hand.gesture,
            preparation.commandable_motion_gesture,
            preparation.effective_motion_gesture,
            1.0,
            app_config(),
            0.1,
        )

        self.assertIsNone(state.pointer.anchor)
        self.assertEqual(state.volume.anchor, 0.50)


class SessionDebugRendererTests(unittest.TestCase):
    def test_debug_renderer_handles_inactive_lost_and_active_states(self) -> None:
        state = _state()
        config = app_config()
        renderer = SessionDebugRenderer()
        hands = [hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)]
        snapshot = build_debug_snapshot(state, config, hands, active_anchor=None)

        inactive = renderer.render_inactive(snapshot)
        lost = renderer.render_temporarily_lost(
            snapshot,
            command_gesture=None,
            zoom_freeze_reason="none",
            anchor_locked=False,
        )
        active = renderer.render_active(
            snapshot,
            ActiveDebugContext(
                active_index=0,
                active_gesture=GESTURE_OPEN_PALM,
                effective_motion_gesture=None,
                commandable_motion_gesture=None,
                volume_gesture=None,
                pointer_gesture=None,
                two_finger_back_gesture=None,
                active_size=0.20,
                pointer_distance=0.0,
                volume_distance=0.0,
                command_gesture=None,
                pointer_position=None,
                zoom_hands=1,
                zoom_freeze_reason="none",
                anchor_locked=False,
            ),
        )

        self.assertIn("activated=False", inactive)
        self.assertIn("active_hand_temporarily_lost", lost)
        self.assertIn("active=OPEN_PALM", active)


def _state() -> GestureSessionState:
    return GestureSessionState.create(motion_grace_seconds=0.6)


if __name__ == "__main__":
    unittest.main()
