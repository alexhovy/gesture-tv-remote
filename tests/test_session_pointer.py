import unittest

from src.domain.constants import (
    DEBUG_UNKNOWN,
    GESTURE_OPEN_PALM,
    GESTURE_FIST,
    GESTURE_PINCH,
    GESTURE_POINT,
    GESTURE_POINT_DOWN,
    GESTURE_POINT_LEFT,
    GESTURE_POINT_RIGHT,
    GESTURE_POINT_UP,
)
from src.domain.session import GestureSession
from tests.config_helpers import app_config
from tests.session_helpers import evaluate_pointer_move, hand_state


class SessionPointerTests(unittest.TestCase):
    def test_pointer_distance_uses_display_crop_reference_size(self) -> None:
        self.assertEqual(
            evaluate_pointer_move(hand_size=0.10, start_x=0.50, end_x=0.67),
            GESTURE_POINT_RIGHT,
        )
        self.assertEqual(
            evaluate_pointer_move(hand_size=0.25, start_x=0.50, end_x=0.67),
            GESTURE_POINT_RIGHT,
        )

        session = GestureSession(app_config())
        self._activate(session, (0.50, 0.50))

        self._point(session, (0.50, 0.50), now=0.1, pointer_reference_size=0.5)
        right = self._point(
            session,
            (0.59, 0.50),
            now=0.2,
            pointer_reference_size=0.5,
        )

        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIn("activation=0.081", right.debug_message)
        self.assertIn("neutral=0.070", right.debug_message)

    def test_pointer_uses_fixed_neutral_circle_from_initial_index_tip(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, (0.50, 0.50))

        self._point(session, (0.50, 0.50), now=0.1)
        inside = self._point(session, (0.50, 0.63), now=0.2)
        margin = self._point(session, (0.50, 0.65), now=0.3)
        outside = self._point(session, (0.50, 0.67), now=0.4)

        self.assertIsNone(inside.command_gesture)
        self.assertIn("anchor=(0.50,0.50)", inside.debug_message)
        self.assertIn("activation=0.161", inside.debug_message)
        self.assertIn("neutral=0.140", inside.debug_message)
        self.assertIn("in_neutral=True", inside.debug_message)
        self.assertTrue(inside.anchor_locked)
        self.assertIn("zoom_freeze_reason=motion_anchor", inside.debug_message)
        self.assertIsNone(margin.command_gesture)
        self.assertIn("blocked=inside_activation", margin.debug_message)
        self.assertEqual(outside.command_gesture, GESTURE_POINT_DOWN)
        self.assertTrue(outside.freeze_zoom)

    def test_pointer_return_to_neutral_rearms_without_recentering_anchor(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        self._activate(session, (0.50, 0.50))

        self._point(session, (0.50, 0.50), now=0.1)
        first_down = self._point(session, (0.50, 0.67), now=0.2)
        neutral = self._point(session, (0.50, 0.51), now=0.3)
        first_up = self._point(session, (0.50, 0.33), now=0.4)

        self.assertEqual(first_down.command_gesture, GESTURE_POINT_DOWN)
        self.assertIsNone(neutral.command_gesture)
        self.assertIn("blocked=rearmed", neutral.debug_message)
        self.assertIn("anchor=(0.50,0.50)", neutral.debug_message)
        self.assertEqual(first_up.command_gesture, GESTURE_POINT_UP)

    def test_pointer_hold_repeats_after_debounce_interval(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        self._activate(session, (0.50, 0.50))

        self._point(session, (0.50, 0.50), now=0.1)
        first = self._point(session, (0.67, 0.50), now=0.2)
        held_too_soon = self._point(session, (0.68, 0.50), now=0.3)
        repeated = self._point(session, (0.68, 0.50), now=0.51)

        self.assertEqual(first.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(held_too_soon.command_gesture)
        self.assertIn("blocked=holding", held_too_soon.debug_message)
        self.assertEqual(repeated.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIn("blocked=repeat", repeated.debug_message)

    def test_pointer_requires_neutral_return_before_direction_switch(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        self._activate(session, (0.50, 0.50))

        self._point(session, (0.50, 0.50), now=0.1)
        right = self._point(session, (0.67, 0.50), now=0.2)
        left_without_neutral = self._point(session, (0.33, 0.50), now=0.3)
        neutral = self._point(session, (0.50, 0.50), now=0.4)
        left = self._point(session, (0.33, 0.50), now=0.5)

        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(left_without_neutral.command_gesture)
        self.assertIn("blocked=awaiting_neutral", left_without_neutral.debug_message)
        self.assertIn("blocked=rearmed", neutral.debug_message)
        self.assertEqual(left.command_gesture, GESTURE_POINT_LEFT)

    def test_pointer_undersized_point_does_not_recenter_anchor(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, (0.50, 0.50))

        self._point(session, (0.50, 0.50), now=0.1)
        undersized = session.evaluate(
            [hand_state(
                GESTURE_POINT,
                center=(0.67, 0.50),
                size=0.09,
                index_position=(0.67, 0.50),
            )],
            now=0.2,
        )
        right = self._point(session, (0.67, 0.50), now=0.3)

        self.assertIsNone(undersized.command_gesture)
        self.assertIn("pose_blocked=hand_too_small", undersized.debug_message)
        self.assertIn("anchor=(0.50,0.50)", undersized.debug_message)
        self.assertIn("blocked=motion_grace", undersized.debug_message)
        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)

    def test_zoomed_small_original_frame_point_can_activate_pointer(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, (0.50, 0.50))

        session.evaluate(
            [hand_state(
                GESTURE_POINT,
                center=(0.50, 0.50),
                size=0.07,
                index_position=(0.50, 0.50),
            )],
            now=0.1,
            pointer_reference_size=0.15,
        )
        right = session.evaluate(
            [hand_state(
                GESTURE_POINT,
                center=(0.53, 0.50),
                size=0.07,
                index_position=(0.53, 0.50),
            )],
            now=0.2,
            pointer_reference_size=0.15,
        )

        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIn("pose_blocked=none", right.debug_message)
        self.assertIn("pointer_distance=0.02", right.debug_message)

    def test_small_full_frame_point_still_does_not_activate_pointer(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, (0.50, 0.50))

        decision = session.evaluate(
            [hand_state(
                GESTURE_POINT,
                center=(0.50, 0.50),
                size=0.07,
                index_position=(0.50, 0.50),
            )],
            now=0.1,
            pointer_reference_size=1.0,
        )

        self.assertIsNone(decision.command_gesture)
        self.assertIn("pose_blocked=hand_too_small", decision.debug_message)
        self.assertIn("pointer_state=anchor=none", decision.debug_message)

    def test_pointer_preserves_anchor_during_active_hand_temporary_loss(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, (0.50, 0.50))

        self._point(session, (0.50, 0.50), now=0.1)
        missing = session.evaluate([], now=0.2)
        right = self._point(session, (0.71, 0.50), now=0.3)

        self.assertTrue(missing.active_temporarily_lost)
        self.assertTrue(missing.anchor_locked)
        self.assertTrue(missing.freeze_zoom)
        self.assertIn("pointer_state=anchor=(0.50,0.50)", missing.debug_message)
        self.assertIn("blocked=active_hand_grace", missing.debug_message)
        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)

    def test_pointer_clears_anchor_on_open_palm(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, (0.50, 0.50))

        self._point(session, (0.50, 0.50), now=0.1)
        open_palm = session.evaluate(
            [hand_state(
                GESTURE_OPEN_PALM,
                center=(0.67, 0.50),
                size=0.20,
                index_position=(0.67, 0.50),
            )],
            now=0.2,
        )

        self.assertIsNone(open_palm.command_gesture)
        self.assertFalse(open_palm.anchor_locked)
        self.assertFalse(open_palm.freeze_zoom)
        self.assertIn("active=OPEN_PALM effective_motion=none", open_palm.debug_message)
        self.assertIn("pointer_state=anchor=none", open_palm.debug_message)

    def test_pointer_clears_anchor_on_fist(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, (0.50, 0.50))

        self._point(session, (0.50, 0.50), now=0.1)
        fist = session.evaluate(
            [hand_state(
                GESTURE_FIST,
                center=(0.67, 0.50),
                size=0.20,
                index_position=(0.67, 0.50),
            )],
            now=0.2,
        )

        self.assertIsNone(fist.command_gesture)
        self.assertFalse(fist.anchor_locked)
        self.assertTrue(fist.freeze_zoom)
        self.assertIn("active=FIST effective_motion=none", fist.debug_message)
        self.assertIn("pointer_state=anchor=none", fist.debug_message)
        self.assertIn("zoom_hands=0", fist.debug_message)
        self.assertIn("zoom_freeze_reason=command_pose", fist.debug_message)

    def test_pointer_clears_anchor_after_extended_open_palm(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, (0.50, 0.50))

        self._point(session, (0.50, 0.50), now=0.1)
        open_palm = session.evaluate(
            [hand_state(
                GESTURE_OPEN_PALM,
                center=(0.67, 0.50),
                size=0.20,
                index_position=(0.67, 0.50),
            )],
            now=0.8,
        )

        self.assertIsNone(open_palm.command_gesture)
        self.assertFalse(open_palm.anchor_locked)
        self.assertIn("active=OPEN_PALM effective_motion=none", open_palm.debug_message)
        self.assertIn("pointer_state=anchor=none", open_palm.debug_message)

    def test_pointer_switches_to_pinch_motion(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, (0.50, 0.50))

        self._point(session, (0.50, 0.50), now=0.1)
        pinch = session.evaluate(
            [hand_state(
                GESTURE_PINCH,
                center=(0.67, 0.50),
                size=0.20,
                index_position=(0.67, 0.50),
            )],
            now=0.2,
        )

        self.assertIsNone(pinch.command_gesture)
        self.assertIn("active=PINCH effective_motion=PINCH", pinch.debug_message)
        self.assertIn("pointer_state=anchor=none", pinch.debug_message)
        self.assertIn("volume_state=anchor=0.50", pinch.debug_message)

    def test_pointer_uses_index_tip_for_horizontal_movement(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, (0.50, 0.50))

        session.evaluate(
            [hand_state(
                GESTURE_POINT,
                center=(0.50, 0.50),
                size=0.20,
                index_position=(0.50, 0.50),
            )],
            now=0.1,
        )
        left = session.evaluate(
            [hand_state(
                GESTURE_POINT,
                center=(0.49, 0.50),
                size=0.20,
                index_position=(0.33, 0.50),
            )],
            now=0.2,
        )

        self.assertEqual(left.command_gesture, GESTURE_POINT_LEFT)
        self.assertIn("source=index_tip", left.debug_message)

    def test_pointer_survives_brief_unknown_gesture(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, (0.50, 0.50))

        self._point(session, (0.50, 0.50), now=0.1)
        unknown = session.evaluate(
            [hand_state(
                DEBUG_UNKNOWN,
                center=(0.49, 0.50),
                size=0.20,
                index_position=(0.33, 0.50),
            )],
            now=0.2,
        )

        self.assertEqual(unknown.command_gesture, GESTURE_POINT_LEFT)
        self.assertTrue(unknown.freeze_zoom)
        self.assertIn("active=UNKNOWN effective_motion=POINT", unknown.debug_message)

    def _activate(self, session: GestureSession, center: tuple[float, float]) -> None:
        session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=center, size=0.20)],
            now=0.0,
        )

    def _point(
        self,
        session: GestureSession,
        center: tuple[float, float],
        now: float,
        pointer_reference_size: float = 1.0,
    ):
        return session.evaluate(
            [hand_state(
                GESTURE_POINT,
                center=center,
                size=0.20,
                index_position=center,
            )],
            now=now,
            pointer_reference_size=pointer_reference_size,
        )


if __name__ == "__main__":
    unittest.main()
