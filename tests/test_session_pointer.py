import unittest

from src.domain.constants import (
    DEBUG_UNKNOWN,
    GESTURE_OPEN_PALM,
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
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        first_under_threshold = self._point(session, primary, (0.50, 0.52), now=0.1)
        second_under_threshold = self._point(session, primary, (0.50, 0.53), now=0.2)
        crossed_threshold = self._point(session, primary, (0.50, 0.54), now=0.3)

        self.assertIsNone(first_under_threshold.command_gesture)
        self.assertIsNone(second_under_threshold.command_gesture)
        self.assertEqual(crossed_threshold.command_gesture, GESTURE_POINT_DOWN)
        self.assertTrue(crossed_threshold.freeze_zoom)

    def test_pointer_debug_reports_anchor_threshold_and_neutral_state(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        near_miss = self._point(session, primary, (0.50, 0.53), now=0.1)

        self.assertIsNone(near_miss.command_gesture)
        self.assertIn("anchor=(0.50,0.50)", near_miss.debug_message)
        self.assertIn("candidate=none", near_miss.debug_message)
        self.assertIn("magnitude=0.030", near_miss.debug_message)
        self.assertIn("activation=0.033", near_miss.debug_message)
        self.assertIn("threshold_ratio=0.92", near_miss.debug_message)
        self.assertIn("in_neutral=False", near_miss.debug_message)
        self.assertIn("blocked=below_threshold", near_miss.debug_message)

    def test_pointer_neutral_zone_rearms_without_recentering_anchor(self) -> None:
        session = GestureSession(app_config())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        neutral_move = self._point(session, primary, (0.50, 0.512), now=0.1)
        neutral_settling = self._point(session, primary, (0.50, 0.512), now=0.2)
        crossed_from_original_anchor = self._point(session, primary, (0.50, 0.54), now=0.3)

        self.assertIsNone(neutral_move.command_gesture)
        self.assertIn("in_neutral=True", neutral_move.debug_message)
        self.assertIn("phase=armed", neutral_move.debug_message)
        self.assertIn("blocked=rearmed", neutral_move.debug_message)
        self.assertIsNone(neutral_settling.command_gesture)
        self.assertEqual(crossed_from_original_anchor.command_gesture, GESTURE_POINT_DOWN)
        self.assertIn("anchor=(0.50,0.50)", crossed_from_original_anchor.debug_message)

    def test_pointer_release_settle_frames_are_configurable(self) -> None:
        session = GestureSession(app_config(pointer_release_settle_frames=3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        self._point(session, primary, (0.56, 0.50), now=0.1)
        first_neutral = self._point(session, primary, (0.505, 0.50), now=0.2)
        second_neutral = self._point(session, primary, (0.505, 0.50), now=0.3)
        third_neutral = self._point(session, primary, (0.505, 0.50), now=0.4)
        rearmed_left = self._point(session, primary, (0.44, 0.50), now=0.5)

        self.assertIn("phase=settling", first_neutral.debug_message)
        self.assertIn("phase=settling", second_neutral.debug_message)
        self.assertIn("phase=armed", third_neutral.debug_message)
        self.assertEqual(rearmed_left.command_gesture, GESTURE_POINT_LEFT)

    def test_pointer_hold_does_not_repeat_before_neutral_return(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        first = self._point(session, primary, (0.56, 0.50), now=0.1)
        held_too_soon = self._point(session, primary, (0.57, 0.50), now=0.2)
        repeated = self._point(session, primary, (0.57, 0.50), now=0.41)

        self.assertEqual(first.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(held_too_soon.command_gesture)
        self.assertIn("blocked=awaiting_release", held_too_soon.debug_message)
        self.assertIsNone(repeated.command_gesture)
        self.assertIn("blocked=awaiting_release", repeated.debug_message)

    def test_pointer_return_to_neutral_stops_repeat_and_allows_new_direction(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        first_down = self._point(session, primary, (0.50, 0.56), now=0.1)
        neutral = self._point(session, primary, (0.50, 0.505), now=0.2)
        neutral_settling = self._point(session, primary, (0.50, 0.505), now=0.3)
        first_up = self._point(session, primary, (0.50, 0.45), now=0.4)

        self.assertEqual(first_down.command_gesture, GESTURE_POINT_DOWN)
        self.assertIsNone(neutral.command_gesture)
        self.assertIn("in_neutral=True", neutral.debug_message)
        self.assertIn("phase=armed", neutral_settling.debug_message)
        self.assertIn("blocked=rearmed", neutral_settling.debug_message)
        self.assertEqual(first_up.command_gesture, GESTURE_POINT_UP)

    def test_pointer_requires_neutral_return_before_horizontal_direction_switch(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        right = self._point(session, primary, (0.56, 0.50), now=0.1)
        left = self._point(session, primary, (0.44, 0.50), now=0.2)
        self._point(session, primary, (0.505, 0.50), now=0.3)
        self._point(session, primary, (0.505, 0.50), now=0.4)
        rearmed_left = self._point(session, primary, (0.44, 0.50), now=0.5)

        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(left.command_gesture)
        self.assertIn("blocked=awaiting_release", left.debug_message)
        self.assertEqual(rearmed_left.command_gesture, GESTURE_POINT_LEFT)

    def test_pointer_release_return_allows_repeat_without_exact_neutral(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        first = self._point(session, primary, (0.56, 0.50), now=0.1)
        release = self._point(session, primary, (0.525, 0.50), now=0.2)
        rearmed = self._point(session, primary, (0.525, 0.50), now=0.3)
        repeated = self._point(session, primary, (0.56, 0.50), now=0.4)

        self.assertEqual(first.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(release.command_gesture)
        self.assertIn("in_neutral=False", release.debug_message)
        self.assertIn("in_release=True", release.debug_message)
        self.assertIn("blocked=rearmed", rearmed.debug_message)
        self.assertEqual(repeated.command_gesture, GESTURE_POINT_RIGHT)

    def test_pointer_release_return_allows_new_direction_without_exact_neutral(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        up = self._point(session, primary, (0.50, 0.44), now=0.1)
        self._point(session, primary, (0.50, 0.525), now=0.2)
        released = self._point(session, primary, (0.50, 0.525), now=0.3)
        left = self._point(session, primary, (0.44, 0.50), now=0.4)

        self.assertEqual(up.command_gesture, GESTURE_POINT_UP)
        self.assertIn("blocked=rearmed", released.debug_message)
        self.assertEqual(left.command_gesture, GESTURE_POINT_LEFT)

    def test_pointer_left_return_toward_anchor_does_not_emit_right(self) -> None:
        session = GestureSession(app_config(debounce_seconds=0.3))
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        self._point(session, primary, (0.50, 0.50), now=0.0)
        left = self._point(session, primary, (0.44, 0.50), now=0.1)
        returning = self._point(session, primary, (0.525, 0.50), now=0.2)
        rearmed = self._point(session, primary, (0.525, 0.50), now=0.3)
        near_anchor = self._point(session, primary, (0.50, 0.50), now=0.4)

        self.assertEqual(left.command_gesture, GESTURE_POINT_LEFT)
        self.assertIsNone(returning.command_gesture)
        self.assertIn("in_release=True", returning.debug_message)
        self.assertIn("blocked=rearmed", rearmed.debug_message)
        self.assertIsNone(near_anchor.command_gesture)
        self.assertIn("anchor=(0.50,0.50)", near_anchor.debug_message)

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
                    index_position=(0.45, 0.50),
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
                    index_position=(0.45, 0.50),
                ),
            ],
            now=0.2,
        )

        self.assertEqual(unknown.command_gesture, GESTURE_POINT_LEFT)
        self.assertTrue(unknown.freeze_zoom)
        self.assertIn("secondary=UNKNOWN effective_secondary=POINT", unknown.debug_message)

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
