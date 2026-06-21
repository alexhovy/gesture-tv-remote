import unittest

from src.domain.constants import (
    DEBUG_UNKNOWN,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_VOLUME_DOWN,
    GESTURE_VOLUME_UP,
)
from src.domain.session import GestureSession
from tests.config_helpers import app_config
from tests.session_helpers import evaluate_volume_move, hand_state


class SessionVolumeTests(unittest.TestCase):
    def test_volume_distance_scales_with_hand_size(self) -> None:
        self.assertEqual(
            evaluate_volume_move(hand_size=0.10, start_y=0.50, end_y=0.54),
            GESTURE_VOLUME_DOWN,
        )
        self.assertIsNone(
            evaluate_volume_move(hand_size=0.25, start_y=0.50, end_y=0.54)
        )

    def test_volume_movement_accumulates_from_anchor_until_threshold(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._pinch(session, primary, 0.50, now=0.0)
        first_under_threshold = self._pinch(session, primary, 0.52, now=0.1)
        second_under_threshold = self._pinch(session, primary, 0.53, now=0.2)
        crossed_threshold = self._pinch(session, primary, 0.54, now=0.3)

        self.assertIsNone(first_under_threshold.command_gesture)
        self.assertIsNone(second_under_threshold.command_gesture)
        self.assertEqual(crossed_threshold.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertTrue(crossed_threshold.freeze_zoom)

    def test_volume_debug_reports_anchor_threshold_and_neutral_state(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._pinch(session, primary, 0.50, now=0.0)
        near_miss = self._pinch(session, primary, 0.53, now=0.1)

        self.assertIsNone(near_miss.command_gesture)
        self.assertIn("anchor=0.50", near_miss.debug_message)
        self.assertIn("candidate=none", near_miss.debug_message)
        self.assertIn("magnitude=0.030", near_miss.debug_message)
        self.assertIn("activation=0.033", near_miss.debug_message)
        self.assertIn("threshold_ratio=0.92", near_miss.debug_message)
        self.assertIn("in_neutral=False", near_miss.debug_message)
        self.assertIn("blocked=below_threshold", near_miss.debug_message)

    def test_volume_neutral_zone_recenters_after_stable_return(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._pinch(session, primary, 0.50, now=0.0)
        neutral_move = self._pinch(session, primary, 0.512, now=0.1)
        neutral_settling = self._pinch(session, primary, 0.512, now=0.2)
        neutral_settled = self._pinch(session, primary, 0.512, now=0.3)
        below_threshold_from_new_anchor = self._pinch(session, primary, 0.54, now=0.4)
        crossed_from_new_anchor = self._pinch(session, primary, 0.55, now=0.5)

        self.assertIsNone(neutral_move.command_gesture)
        self.assertIn("in_neutral=True", neutral_move.debug_message)
        self.assertIsNone(neutral_settling.command_gesture)
        self.assertIn("phase=armed", neutral_settled.debug_message)
        self.assertIsNone(below_threshold_from_new_anchor.command_gesture)
        self.assertEqual(crossed_from_new_anchor.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertIn("anchor=0.51", crossed_from_new_anchor.debug_message)

    def test_volume_hold_does_not_repeat_before_neutral_return(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._pinch(session, primary, 0.50, now=0.0)
        first = self._pinch(session, primary, 0.56, now=0.1)
        held_too_soon = self._pinch(session, primary, 0.57, now=0.2)
        repeated = self._pinch(session, primary, 0.57, now=0.41)

        self.assertEqual(first.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertIsNone(held_too_soon.command_gesture)
        self.assertIn("blocked=awaiting_release", held_too_soon.debug_message)
        self.assertIsNone(repeated.command_gesture)
        self.assertIn("blocked=awaiting_release", repeated.debug_message)

    def test_volume_return_to_neutral_stops_repeat_and_allows_new_direction(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._pinch(session, primary, 0.50, now=0.0)
        first_down = self._pinch(session, primary, 0.56, now=0.1)
        neutral = self._pinch(session, primary, 0.505, now=0.2)
        neutral_settling = self._pinch(session, primary, 0.505, now=0.3)
        first_up = self._pinch(session, primary, 0.45, now=0.4)

        self.assertEqual(first_down.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertIsNone(neutral.command_gesture)
        self.assertIn("in_neutral=True", neutral.debug_message)
        self.assertIn("phase=armed", neutral_settling.debug_message)
        self.assertEqual(first_up.command_gesture, GESTURE_VOLUME_UP)

    def test_volume_release_return_allows_repeat_without_exact_neutral(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._pinch(session, primary, 0.50, now=0.0)
        first = self._pinch(session, primary, 0.56, now=0.1)
        release = self._pinch(session, primary, 0.525, now=0.2)
        rearmed = self._pinch(session, primary, 0.525, now=0.3)
        repeated = self._pinch(session, primary, 0.56, now=0.4)

        self.assertEqual(first.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertIsNone(release.command_gesture)
        self.assertIn("in_neutral=False", release.debug_message)
        self.assertIn("in_release=True", release.debug_message)
        self.assertIn("blocked=rearmed", rearmed.debug_message)
        self.assertEqual(repeated.command_gesture, GESTURE_VOLUME_DOWN)

    def test_volume_survives_brief_unknown_secondary_gesture(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._pinch(session, primary, 0.50, now=0.0)
        unknown = session.evaluate(
            [
                primary,
                hand_state(DEBUG_UNKNOWN, center=(0.70, 0.56), size=0.20),
            ],
            now=0.2,
        )

        self.assertEqual(unknown.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertTrue(unknown.freeze_zoom)
        self.assertIn("secondary=UNKNOWN effective_secondary=PINCH", unknown.debug_message)

    def _pinch(
        self,
        session: GestureSession,
        primary,
        y: float,
        now: float,
    ):
        return session.evaluate(
            [
                primary,
                hand_state(GESTURE_PINCH, center=(0.70, y), size=0.20),
            ],
            now=now,
        )


if __name__ == "__main__":
    unittest.main()
