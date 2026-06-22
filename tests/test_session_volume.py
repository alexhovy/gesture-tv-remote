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
            evaluate_volume_move(hand_size=0.10, start_y=0.50, end_y=0.70),
            GESTURE_VOLUME_DOWN,
        )
        self.assertEqual(
            evaluate_volume_move(hand_size=0.25, start_y=0.50, end_y=0.70),
            GESTURE_VOLUME_DOWN,
        )

    def test_volume_uses_fixed_neutral_band_from_initial_pinch(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._pinch(session, primary, 0.50, now=0.0)
        inside = self._pinch(session, primary, 0.64, now=0.1)
        outside = self._pinch(session, primary, 0.70, now=0.2)

        self.assertIsNone(inside.command_gesture)
        self.assertIn("anchor=0.50", inside.debug_message)
        self.assertIn("activation=0.184", inside.debug_message)
        self.assertIn("neutral=0.160", inside.debug_message)
        self.assertIn("in_neutral=True", inside.debug_message)
        self.assertEqual(outside.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertTrue(outside.freeze_zoom)

    def test_volume_return_to_neutral_rearms_without_recentering_anchor(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._pinch(session, primary, 0.50, now=0.0)
        first_down = self._pinch(session, primary, 0.70, now=0.1)
        neutral = self._pinch(session, primary, 0.51, now=0.2)
        first_up = self._pinch(session, primary, 0.29, now=0.3)

        self.assertEqual(first_down.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertIsNone(neutral.command_gesture)
        self.assertIn("blocked=rearmed", neutral.debug_message)
        self.assertIn("anchor=0.50", neutral.debug_message)
        self.assertEqual(first_up.command_gesture, GESTURE_VOLUME_UP)

    def test_volume_hold_repeats_after_debounce_interval(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._pinch(session, primary, 0.50, now=0.0)
        first = self._pinch(session, primary, 0.70, now=0.1)
        held_too_soon = self._pinch(session, primary, 0.71, now=0.2)
        repeated = self._pinch(session, primary, 0.71, now=0.41)

        self.assertEqual(first.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertIsNone(held_too_soon.command_gesture)
        self.assertIn("blocked=holding", held_too_soon.debug_message)
        self.assertEqual(repeated.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertIn("blocked=repeat", repeated.debug_message)

    def test_volume_requires_neutral_return_before_direction_switch(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._pinch(session, primary, 0.50, now=0.0)
        down = self._pinch(session, primary, 0.70, now=0.1)
        up_without_neutral = self._pinch(session, primary, 0.29, now=0.2)
        neutral = self._pinch(session, primary, 0.50, now=0.3)
        up = self._pinch(session, primary, 0.29, now=0.4)

        self.assertEqual(down.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertIsNone(up_without_neutral.command_gesture)
        self.assertIn("blocked=awaiting_neutral", up_without_neutral.debug_message)
        self.assertIn("blocked=rearmed", neutral.debug_message)
        self.assertEqual(up.command_gesture, GESTURE_VOLUME_UP)

    def test_volume_survives_brief_unknown_secondary_gesture(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._pinch(session, primary, 0.50, now=0.0)
        unknown = session.evaluate(
            [
                primary,
                hand_state(DEBUG_UNKNOWN, center=(0.70, 0.70), size=0.20),
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
