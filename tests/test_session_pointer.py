import unittest

from src.domain.constants import (
    GESTURE_OPEN_PALM,
    GESTURE_POINT,
    GESTURE_POINT_DOWN,
    GESTURE_POINT_LEFT,
    GESTURE_POINT_RIGHT,
    GESTURE_POINT_UP,
)
from src.domain.session import GestureSession
from src.shared.config import AppConfig
from tests.session_helpers import evaluate_pointer_move, hand_state


class SessionPointerTests(unittest.TestCase):
    def test_pointer_distance_scales_with_hand_size(self) -> None:
        self.assertEqual(
            evaluate_pointer_move(hand_size=0.10, start_x=0.50, end_x=0.55),
            GESTURE_POINT_RIGHT,
        )
        self.assertEqual(
            evaluate_pointer_move(hand_size=0.25, start_x=0.50, end_x=0.55),
            GESTURE_POINT_RIGHT,
        )

    def test_pointer_movement_accumulates_from_anchor_until_threshold(self) -> None:
        session = GestureSession(AppConfig())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        first_under_threshold = self._point(session, primary, (0.50, 0.52), now=0.1)
        second_under_threshold = self._point(session, primary, (0.50, 0.535), now=0.2)
        crossed_threshold = self._point(session, primary, (0.50, 0.56), now=0.3)

        self.assertIsNone(first_under_threshold.command_gesture)
        self.assertIsNone(second_under_threshold.command_gesture)
        self.assertEqual(crossed_threshold.command_gesture, GESTURE_POINT_DOWN)
        self.assertTrue(crossed_threshold.freeze_zoom)

    def test_pointer_debug_reports_anchor_threshold_and_neutral_state(self) -> None:
        session = GestureSession(AppConfig())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        near_miss = self._point(session, primary, (0.50, 0.535), now=0.1)

        self.assertIsNone(near_miss.command_gesture)
        self.assertIn("anchor=(0.50,0.50)", near_miss.debug_message)
        self.assertIn("candidate=none", near_miss.debug_message)
        self.assertIn("magnitude=0.035", near_miss.debug_message)
        self.assertIn("activation=0.036", near_miss.debug_message)
        self.assertIn("threshold_ratio=0.97", near_miss.debug_message)
        self.assertIn("in_neutral=False", near_miss.debug_message)
        self.assertIn("blocked=below_threshold", near_miss.debug_message)

    def test_pointer_neutral_zone_recenters_after_stable_return(self) -> None:
        session = GestureSession(AppConfig())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        neutral_move = self._point(session, primary, (0.50, 0.515), now=0.1)
        neutral_settling = self._point(session, primary, (0.50, 0.515), now=0.2)
        neutral_settled = self._point(session, primary, (0.50, 0.515), now=0.3)
        below_threshold_from_new_anchor = self._point(session, primary, (0.50, 0.54), now=0.4)
        crossed_from_new_anchor = self._point(session, primary, (0.50, 0.56), now=0.5)

        self.assertIsNone(neutral_move.command_gesture)
        self.assertIn("in_neutral=True", neutral_move.debug_message)
        self.assertIsNone(neutral_settling.command_gesture)
        self.assertIn("phase=armed", neutral_settled.debug_message)
        self.assertIsNone(below_threshold_from_new_anchor.command_gesture)
        self.assertEqual(crossed_from_new_anchor.command_gesture, GESTURE_POINT_DOWN)
        self.assertIn("anchor=(0.50,0.52)", crossed_from_new_anchor.debug_message)

    def test_pointer_hold_does_not_repeat_before_neutral_return(self) -> None:
        session = GestureSession(AppConfig(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        first = self._point(session, primary, (0.56, 0.50), now=0.1)
        held_too_soon = self._point(session, primary, (0.57, 0.50), now=0.2)
        repeated = self._point(session, primary, (0.57, 0.50), now=0.41)

        self.assertEqual(first.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(held_too_soon.command_gesture)
        self.assertIn("blocked=awaiting_neutral", held_too_soon.debug_message)
        self.assertIsNone(repeated.command_gesture)
        self.assertIn("blocked=awaiting_neutral", repeated.debug_message)

    def test_pointer_return_to_neutral_stops_repeat_and_allows_new_direction(self) -> None:
        session = GestureSession(AppConfig(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        first_down = self._point(session, primary, (0.50, 0.56), now=0.1)
        neutral = self._point(session, primary, (0.50, 0.505), now=0.2)
        neutral_settling = self._point(session, primary, (0.50, 0.505), now=0.3)
        neutral_settled = self._point(session, primary, (0.50, 0.505), now=0.4)
        first_up = self._point(session, primary, (0.50, 0.45), now=0.5)

        self.assertEqual(first_down.command_gesture, GESTURE_POINT_DOWN)
        self.assertIsNone(neutral.command_gesture)
        self.assertIn("in_neutral=True", neutral.debug_message)
        self.assertIn("phase=settling", neutral_settling.debug_message)
        self.assertIn("phase=armed", neutral_settled.debug_message)
        self.assertEqual(first_up.command_gesture, GESTURE_POINT_UP)

    def test_pointer_requires_neutral_return_before_horizontal_direction_switch(self) -> None:
        session = GestureSession(AppConfig(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        right = self._point(session, primary, (0.56, 0.50), now=0.1)
        left = self._point(session, primary, (0.44, 0.50), now=0.2)
        self._point(session, primary, (0.505, 0.50), now=0.3)
        self._point(session, primary, (0.505, 0.50), now=0.4)
        self._point(session, primary, (0.505, 0.50), now=0.5)
        rearmed_left = self._point(session, primary, (0.44, 0.50), now=0.6)

        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(left.command_gesture)
        self.assertIn("blocked=awaiting_neutral", left.debug_message)
        self.assertEqual(rearmed_left.command_gesture, GESTURE_POINT_LEFT)

    def _point(
        self,
        session: GestureSession,
        primary,
        center: tuple[float, float],
        now: float,
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
        )


if __name__ == "__main__":
    unittest.main()
