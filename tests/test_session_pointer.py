import unittest

from src.domain.constants import (
    DEBUG_UNKNOWN,
    GESTURE_OPEN_PALM,
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
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0, pointer_reference_size=0.5)
        right = self._point(
            session,
            primary,
            (0.59, 0.50),
            now=0.1,
            pointer_reference_size=0.5,
        )

        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIn("activation=0.081", right.debug_message)
        self.assertIn("neutral=0.070", right.debug_message)

    def test_pointer_uses_fixed_neutral_circle_from_initial_index_tip(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        inside = self._point(session, primary, (0.50, 0.63), now=0.1)
        margin = self._point(session, primary, (0.50, 0.65), now=0.2)
        outside = self._point(session, primary, (0.50, 0.67), now=0.3)

        self.assertIsNone(inside.command_gesture)
        self.assertIn("anchor=(0.50,0.50)", inside.debug_message)
        self.assertIn("activation=0.161", inside.debug_message)
        self.assertIn("neutral=0.140", inside.debug_message)
        self.assertIn("in_neutral=True", inside.debug_message)
        self.assertTrue(inside.anchor_locked)
        self.assertIn("zoom_freeze_reason=motion_anchor", inside.debug_message)
        self.assertIn("anchor_locked=True", inside.debug_message)
        self.assertIsNone(margin.command_gesture)
        self.assertIn("blocked=inside_activation", margin.debug_message)
        self.assertEqual(outside.command_gesture, GESTURE_POINT_DOWN)
        self.assertTrue(outside.freeze_zoom)

    def test_pointer_return_to_neutral_rearms_without_recentering_anchor(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        first_down = self._point(session, primary, (0.50, 0.67), now=0.1)
        neutral = self._point(session, primary, (0.50, 0.51), now=0.2)
        first_up = self._point(session, primary, (0.50, 0.33), now=0.3)

        self.assertEqual(first_down.command_gesture, GESTURE_POINT_DOWN)
        self.assertIsNone(neutral.command_gesture)
        self.assertIn("blocked=rearmed", neutral.debug_message)
        self.assertIn("anchor=(0.50,0.50)", neutral.debug_message)
        self.assertEqual(first_up.command_gesture, GESTURE_POINT_UP)

    def test_pointer_hold_repeats_after_debounce_interval(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        first = self._point(session, primary, (0.67, 0.50), now=0.1)
        held_too_soon = self._point(session, primary, (0.68, 0.50), now=0.2)
        repeated = self._point(session, primary, (0.68, 0.50), now=0.41)

        self.assertEqual(first.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(held_too_soon.command_gesture)
        self.assertIn("blocked=holding", held_too_soon.debug_message)
        self.assertEqual(repeated.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIn("blocked=repeat", repeated.debug_message)

    def test_pointer_requires_neutral_return_before_direction_switch(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        right = self._point(session, primary, (0.67, 0.50), now=0.1)
        left_without_neutral = self._point(session, primary, (0.33, 0.50), now=0.2)
        neutral = self._point(session, primary, (0.50, 0.50), now=0.3)
        left = self._point(session, primary, (0.33, 0.50), now=0.4)

        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(left_without_neutral.command_gesture)
        self.assertIn("blocked=awaiting_neutral", left_without_neutral.debug_message)
        self.assertIn("blocked=rearmed", neutral.debug_message)
        self.assertEqual(left.command_gesture, GESTURE_POINT_LEFT)

    def test_pointer_undersized_point_does_not_recenter_anchor(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        undersized = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.67, 0.50),
                    size=0.09,
                    index_position=(0.67, 0.50),
                ),
            ],
            now=0.1,
        )
        right = self._point(session, primary, (0.67, 0.50), now=0.2)

        self.assertIsNone(undersized.command_gesture)
        self.assertIn("secondary_pose_blocked=hand_too_small", undersized.debug_message)
        self.assertIn("anchor=(0.50,0.50)", undersized.debug_message)
        self.assertIn("blocked=motion_grace", undersized.debug_message)
        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIn("anchor=(0.50,0.50)", right.debug_message)

    def test_pointer_preserves_anchor_when_secondary_hand_disappears(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        self._point(session, primary, (0.71, 0.50), now=0.1)
        missing_secondary = session.evaluate([primary], now=0.2)
        expired = session.evaluate([primary], now=0.8)
        right = self._point(session, primary, (0.71, 0.50), now=0.9)

        self.assertIsNone(missing_secondary.command_gesture)
        self.assertIn("secondary=none", missing_secondary.debug_message)
        self.assertIn("pointer_state=anchor=(0.50,0.50)", missing_secondary.debug_message)
        self.assertIn("blocked=secondary_grace", missing_secondary.debug_message)
        self.assertTrue(missing_secondary.anchor_locked)
        self.assertIsNone(expired.command_gesture)
        self.assertIn("pointer_state=anchor=(0.50,0.50)", expired.debug_message)
        self.assertIn("blocked=secondary_lost", expired.debug_message)
        self.assertTrue(expired.anchor_locked)
        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIn("pointer_state=anchor=(0.50,0.50)", right.debug_message)
        self.assertTrue(right.anchor_locked)

    def test_pointer_preserves_anchor_during_primary_temporary_loss(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        missing_primary = session.evaluate([], now=0.2)
        right = self._point(session, primary, (0.71, 0.50), now=0.3)

        self.assertTrue(missing_primary.primary_temporarily_lost)
        self.assertTrue(missing_primary.anchor_locked)
        self.assertTrue(missing_primary.freeze_zoom)
        self.assertIn("pointer_state=anchor=(0.50,0.50)", missing_primary.debug_message)
        self.assertIn("blocked=primary_grace", missing_primary.debug_message)
        self.assertIn("zoom_freeze_reason=motion_anchor", missing_primary.debug_message)
        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIn("pointer_state=anchor=(0.50,0.50)", right.debug_message)

    def test_pointer_preserves_anchor_through_brief_open_palm_misread(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        misread = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_OPEN_PALM,
                    center=(0.67, 0.50),
                    size=0.20,
                    index_position=(0.67, 0.50),
                ),
            ],
            now=0.2,
        )
        right = self._point(session, primary, (0.67, 0.50), now=0.3)

        self.assertIsNone(misread.command_gesture)
        self.assertIn("secondary=OPEN_PALM effective_secondary=POINT", misread.debug_message)
        self.assertIn("anchor=(0.50,0.50)", misread.debug_message)
        self.assertIn("blocked=motion_grace", misread.debug_message)
        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIn("anchor=(0.50,0.50)", right.debug_message)

    def test_pointer_preserves_anchor_through_brief_pinch_misread(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        misread = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_PINCH,
                    center=(0.67, 0.50),
                    size=0.20,
                    index_position=(0.67, 0.50),
                ),
            ],
            now=0.2,
        )
        right = self._point(session, primary, (0.67, 0.50), now=0.3)

        self.assertIsNone(misread.command_gesture)
        self.assertIn("secondary=PINCH effective_secondary=POINT", misread.debug_message)
        self.assertIn("anchor=(0.50,0.50)", misread.debug_message)
        self.assertIn("blocked=motion_grace", misread.debug_message)
        self.assertIn("volume_state=anchor=none", misread.debug_message)
        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIn("anchor=(0.50,0.50)", right.debug_message)

    def test_pointer_uses_index_tip_for_horizontal_movement(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.50),
                    size=0.20,
                    index_position=(0.50, 0.50),
                ),
            ],
            now=0.0,
        )
        left = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.49, 0.50),
                    size=0.20,
                    index_position=(0.33, 0.50),
                ),
            ],
            now=0.1,
        )

        self.assertEqual(left.command_gesture, GESTURE_POINT_LEFT)
        self.assertIn("source=index_tip", left.debug_message)

    def test_pointer_survives_brief_unknown_secondary_gesture(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        unknown = session.evaluate(
            [
                primary,
                hand_state(
                    DEBUG_UNKNOWN,
                    center=(0.49, 0.50),
                    size=0.20,
                    index_position=(0.33, 0.50),
                ),
            ],
            now=0.2,
        )

        self.assertEqual(unknown.command_gesture, GESTURE_POINT_LEFT)
        self.assertTrue(unknown.freeze_zoom)
        self.assertIn("secondary=UNKNOWN effective_secondary=POINT", unknown.debug_message)

    def test_pointer_preserves_anchor_through_extended_unknown_secondary(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        unknown = session.evaluate(
            [
                primary,
                hand_state(
                    DEBUG_UNKNOWN,
                    center=(0.72, 0.50),
                    size=0.20,
                    index_position=(0.72, 0.50),
                ),
            ],
            now=0.8,
        )
        neutral = self._point(session, primary, (0.50, 0.50), now=0.9)
        right = self._point(session, primary, (0.67, 0.50), now=1.0)

        self.assertIsNone(unknown.command_gesture)
        self.assertTrue(unknown.anchor_locked)
        self.assertIn("secondary=UNKNOWN effective_secondary=none", unknown.debug_message)
        self.assertIn("pointer_state=anchor=(0.50,0.50)", unknown.debug_message)
        self.assertIn("blocked=motion_lost", unknown.debug_message)
        self.assertIn("pointer_state=anchor=(0.50,0.50)", neutral.debug_message)
        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)

    def test_zoom_freezes_while_secondary_hand_is_unknown(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        decision = session.evaluate(
            [
                primary,
                hand_state(DEBUG_UNKNOWN, center=(0.50, 0.50), size=0.20),
            ],
            now=0.0,
        )

        self.assertTrue(decision.freeze_zoom)
        self.assertIn("zoom_freeze_reason=secondary_present", decision.debug_message)

    def _point(
        self,
        session: GestureSession,
        primary,
        center: tuple[float, float],
        now: float,
        pointer_reference_size: float = 1.0,
    ):
        return session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=center,
                    size=0.20,
                    index_position=center,
                ),
            ],
            now=now,
            pointer_reference_size=pointer_reference_size,
        )


if __name__ == "__main__":
    unittest.main()
