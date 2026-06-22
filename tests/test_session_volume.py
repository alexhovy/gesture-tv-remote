import unittest

from src.domain.constants import (
    DEBUG_UNKNOWN,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_POINT,
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
        self._activate(session, 0.50)

        self._pinch(session, 0.50, now=0.1)
        inside = self._pinch(session, 0.64, now=0.2)
        outside = self._pinch(session, 0.70, now=0.3)

        self.assertIsNone(inside.command_gesture)
        self.assertIn("anchor=0.50", inside.debug_message)
        self.assertIn("activation=0.184", inside.debug_message)
        self.assertIn("neutral=0.160", inside.debug_message)
        self.assertIn("in_neutral=True", inside.debug_message)
        self.assertTrue(inside.anchor_locked)
        self.assertIn("zoom_freeze_reason=motion_anchor", inside.debug_message)
        self.assertEqual(outside.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertTrue(outside.freeze_zoom)

    def test_volume_return_to_neutral_rearms_without_recentering_anchor(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        self._activate(session, 0.50)

        self._pinch(session, 0.50, now=0.1)
        first_down = self._pinch(session, 0.70, now=0.2)
        neutral = self._pinch(session, 0.51, now=0.3)
        first_up = self._pinch(session, 0.29, now=0.4)

        self.assertEqual(first_down.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertIsNone(neutral.command_gesture)
        self.assertIn("blocked=rearmed", neutral.debug_message)
        self.assertIn("anchor=0.50", neutral.debug_message)
        self.assertEqual(first_up.command_gesture, GESTURE_VOLUME_UP)

    def test_volume_hold_repeats_after_debounce_interval(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        self._activate(session, 0.50)

        self._pinch(session, 0.50, now=0.1)
        first = self._pinch(session, 0.70, now=0.2)
        held_too_soon = self._pinch(session, 0.71, now=0.3)
        repeated = self._pinch(session, 0.71, now=0.51)

        self.assertEqual(first.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertIsNone(held_too_soon.command_gesture)
        self.assertIn("blocked=holding", held_too_soon.debug_message)
        self.assertEqual(repeated.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertIn("blocked=repeat", repeated.debug_message)

    def test_volume_requires_neutral_return_before_direction_switch(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        self._activate(session, 0.50)

        self._pinch(session, 0.50, now=0.1)
        down = self._pinch(session, 0.70, now=0.2)
        up_without_neutral = self._pinch(session, 0.29, now=0.3)
        neutral = self._pinch(session, 0.50, now=0.4)
        up = self._pinch(session, 0.29, now=0.5)

        self.assertEqual(down.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertIsNone(up_without_neutral.command_gesture)
        self.assertIn("blocked=awaiting_neutral", up_without_neutral.debug_message)
        self.assertIn("blocked=rearmed", neutral.debug_message)
        self.assertEqual(up.command_gesture, GESTURE_VOLUME_UP)

    def test_volume_preserves_anchor_during_active_hand_temporary_loss(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, 0.50)

        self._pinch(session, 0.50, now=0.1)
        self._pinch(session, 0.70, now=0.2)
        missing = session.evaluate([], now=0.3)
        down = self._pinch(session, 0.70, now=0.6)

        self.assertIsNone(missing.command_gesture)
        self.assertIn("volume_state=anchor=0.50", missing.debug_message)
        self.assertIn("blocked=active_hand_grace", missing.debug_message)
        self.assertTrue(missing.anchor_locked)
        self.assertEqual(down.command_gesture, GESTURE_VOLUME_DOWN)

    def test_volume_survives_brief_unknown_gesture(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, 0.50)

        self._pinch(session, 0.50, now=0.1)
        unknown = session.evaluate(
            [hand_state(DEBUG_UNKNOWN, center=(0.70, 0.70), size=0.20)],
            now=0.2,
        )

        self.assertEqual(unknown.command_gesture, GESTURE_VOLUME_DOWN)
        self.assertTrue(unknown.freeze_zoom)
        self.assertIn("active=UNKNOWN effective_motion=PINCH", unknown.debug_message)

    def test_volume_preserves_anchor_through_brief_open_palm_misread(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, 0.50)

        self._pinch(session, 0.50, now=0.1)
        misread = session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.70, 0.70), size=0.20)],
            now=0.2,
        )
        down = self._pinch(session, 0.70, now=0.3)

        self.assertIsNone(misread.command_gesture)
        self.assertIn("active=OPEN_PALM effective_motion=PINCH", misread.debug_message)
        self.assertIn("volume_state=anchor=0.50", misread.debug_message)
        self.assertIn("blocked=motion_grace", misread.debug_message)
        self.assertEqual(down.command_gesture, GESTURE_VOLUME_DOWN)

    def test_volume_clears_anchor_after_extended_open_palm(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, 0.50)

        self._pinch(session, 0.50, now=0.1)
        open_palm = session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.70, 0.70), size=0.20)],
            now=0.8,
        )

        self.assertIsNone(open_palm.command_gesture)
        self.assertFalse(open_palm.anchor_locked)
        self.assertIn("active=OPEN_PALM effective_motion=none", open_palm.debug_message)
        self.assertIn("volume_state=anchor=none", open_palm.debug_message)

    def test_volume_preserves_anchor_through_brief_point_misread(self) -> None:
        session = GestureSession(app_config())
        self._activate(session, 0.50)

        self._pinch(session, 0.50, now=0.1)
        misread = session.evaluate(
            [hand_state(GESTURE_POINT, center=(0.70, 0.70), size=0.20)],
            now=0.2,
        )
        down = self._pinch(session, 0.70, now=0.3)

        self.assertIsNone(misread.command_gesture)
        self.assertIn("active=POINT effective_motion=PINCH", misread.debug_message)
        self.assertIn("volume_state=anchor=0.50", misread.debug_message)
        self.assertIn("blocked=motion_grace", misread.debug_message)
        self.assertIn("pointer_state=anchor=none", misread.debug_message)
        self.assertEqual(down.command_gesture, GESTURE_VOLUME_DOWN)

    def _activate(self, session: GestureSession, y: float) -> None:
        session.evaluate(
            [hand_state(GESTURE_OPEN_PALM, center=(0.70, y), size=0.20)],
            now=0.0,
        )

    def _pinch(self, session: GestureSession, y: float, now: float):
        return session.evaluate(
            [hand_state(GESTURE_PINCH, center=(0.70, y), size=0.20)],
            now=now,
        )


if __name__ == "__main__":
    unittest.main()
