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
from tests.session_helpers import (
    evaluate_pointer_move,
    hand_state,
)


class SessionPointerTests(unittest.TestCase):
    def test_pointer_distance_scales_with_hand_size(self) -> None:
        self.assertEqual(
            evaluate_pointer_move(hand_size=0.10, start_x=0.50, end_x=0.55),
            GESTURE_POINT_RIGHT,
        )
        self.assertIsNone(
            evaluate_pointer_move(hand_size=0.25, start_x=0.50, end_x=0.55)
        )

    def test_pointer_movement_accumulates_before_threshold(self) -> None:
        session = GestureSession(AppConfig())
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
        first_under_threshold = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.52),
                    size=0.20,
                    index_position=(0.50, 0.52),
                ),
            ],
            now=0.1,
        )
        second_under_threshold = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.54),
                    size=0.20,
                    index_position=(0.50, 0.54),
                ),
            ],
            now=0.2,
        )
        crossed_threshold = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.56),
                    size=0.20,
                    index_position=(0.50, 0.56),
                ),
            ],
            now=0.3,
        )

        self.assertIsNone(first_under_threshold.command_gesture)
        self.assertIsNone(second_under_threshold.command_gesture)
        self.assertEqual(crossed_threshold.command_gesture, GESTURE_POINT_DOWN)

    def test_pointer_tracks_secondary_hand_center_when_fingertip_is_stable(self) -> None:
        session = GestureSession(AppConfig())
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
        moved_right = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.56, 0.50),
                    size=0.20,
                    index_position=(0.50, 0.50),
                ),
            ],
            now=0.1,
        )

        self.assertEqual(moved_right.command_gesture, GESTURE_POINT_RIGHT)

    def test_pointer_return_to_center_suppresses_repeat_until_released(self) -> None:
        session = GestureSession(AppConfig())
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
        first_down = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.56),
                    size=0.20,
                    index_position=(0.50, 0.56),
                ),
            ],
            now=0.1,
        )
        held_down = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.60),
                    size=0.20,
                    index_position=(0.50, 0.60),
                ),
            ],
            now=0.2,
        )
        slight_return = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.57),
                    size=0.20,
                    index_position=(0.50, 0.57),
                ),
            ],
            now=0.3,
        )
        returning_down = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.56),
                    size=0.20,
                    index_position=(0.50, 0.56),
                ),
            ],
            now=0.35,
        )
        released = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.51),
                    size=0.20,
                    index_position=(0.50, 0.51),
                ),
            ],
            now=0.4,
        )
        gesture_released = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_OPEN_PALM,
                    center=(0.50, 0.51),
                    size=0.20,
                    index_position=(0.50, 0.51),
                ),
            ],
            now=0.45,
        )
        second_start = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.51),
                    size=0.20,
                    index_position=(0.50, 0.51),
                ),
            ],
            now=0.5,
        )
        second_down = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.57),
                    size=0.20,
                    index_position=(0.50, 0.57),
                ),
            ],
            now=0.6,
        )

        self.assertEqual(first_down.command_gesture, GESTURE_POINT_DOWN)
        self.assertIsNone(held_down.command_gesture)
        self.assertIsNone(slight_return.command_gesture)
        self.assertIsNone(returning_down.command_gesture)
        self.assertIsNone(released.command_gesture)
        self.assertIsNone(gesture_released.command_gesture)
        self.assertIsNone(second_start.command_gesture)
        self.assertEqual(second_down.command_gesture, GESTURE_POINT_DOWN)

    def test_pointer_return_past_center_does_not_emit_opposite_direction(self) -> None:
        session = GestureSession(AppConfig())
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
        first_up = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.44),
                    size=0.20,
                    index_position=(0.50, 0.44),
                ),
            ],
            now=0.1,
        )
        returning_to_center = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.50),
                    size=0.20,
                    index_position=(0.50, 0.50),
                ),
            ],
            now=0.2,
        )
        crossed_center = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.52),
                    size=0.20,
                    index_position=(0.50, 0.52),
                ),
            ],
            now=0.3,
        )

        self.assertEqual(first_up.command_gesture, GESTURE_POINT_UP)
        self.assertIsNone(returning_to_center.command_gesture)
        self.assertIsNone(crossed_center.command_gesture)

    def test_pointer_new_direction_works_after_held_neutral(self) -> None:
        session = GestureSession(AppConfig())
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
        first_right = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.56, 0.50),
                    size=0.20,
                    index_position=(0.56, 0.50),
                ),
            ],
            now=0.1,
        )
        neutral = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.50),
                    size=0.20,
                    index_position=(0.50, 0.50),
                ),
            ],
            now=0.2,
        )
        second_down = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.56),
                    size=0.20,
                    index_position=(0.50, 0.56),
                ),
            ],
            now=0.3,
        )

        self.assertEqual(first_right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(neutral.command_gesture)
        self.assertEqual(second_down.command_gesture, GESTURE_POINT_DOWN)

    def test_pointer_new_direction_rearms_after_neutral_rebase(self) -> None:
        session = GestureSession(AppConfig())
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
        first_right = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.80, 0.50),
                    size=0.20,
                    index_position=(0.80, 0.50),
                ),
            ],
            now=0.1,
        )
        returning = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.62, 0.50),
                    size=0.20,
                    index_position=(0.62, 0.50),
                ),
            ],
            now=0.2,
        )
        neutral = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.50),
                    size=0.20,
                    index_position=(0.50, 0.50),
                ),
            ],
            now=0.3,
        )
        second_up = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.44),
                    size=0.20,
                    index_position=(0.50, 0.44),
                ),
            ],
            now=0.4,
        )

        self.assertEqual(first_right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(returning.command_gesture)
        self.assertIsNone(neutral.command_gesture)
        self.assertIn("rebased=True", neutral.debug_message)
        self.assertEqual(second_up.command_gesture, GESTURE_POINT_UP)

    def test_pointer_return_stroke_does_not_emit_opposite_direction(self) -> None:
        session = GestureSession(AppConfig())
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
        first_right = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.80, 0.50),
                    size=0.20,
                    index_position=(0.80, 0.50),
                ),
            ],
            now=0.1,
        )
        returning = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.68, 0.50),
                    size=0.20,
                    index_position=(0.68, 0.50),
                ),
            ],
            now=0.2,
        )
        rearmed = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.62, 0.50),
                    size=0.20,
                    index_position=(0.62, 0.50),
                ),
            ],
            now=0.3,
        )
        continued_return = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.50),
                    size=0.20,
                    index_position=(0.50, 0.50),
                ),
            ],
            now=0.4,
        )
        crossed_return = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.42, 0.50),
                    size=0.20,
                    index_position=(0.42, 0.50),
                ),
            ],
            now=0.5,
        )
        settled = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.42, 0.50),
                    size=0.20,
                    index_position=(0.42, 0.50),
                ),
            ],
            now=0.6,
        )
        mild_opposite = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.36, 0.50),
                    size=0.20,
                    index_position=(0.36, 0.50),
                ),
            ],
            now=0.7,
        )
        second_left = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.32, 0.50),
                    size=0.20,
                    index_position=(0.32, 0.50),
                ),
            ],
            now=0.8,
        )

        self.assertEqual(first_right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(returning.command_gesture)
        self.assertIsNone(rearmed.command_gesture)
        self.assertIsNone(continued_return.command_gesture)
        self.assertEqual(crossed_return.command_gesture, GESTURE_POINT_LEFT)
        self.assertIsNone(settled.command_gesture)
        self.assertIsNone(mild_opposite.command_gesture)
        self.assertIsNone(second_left.command_gesture)

    def test_pointer_vertical_return_rearms_opposite_after_neutral(self) -> None:
        session = GestureSession(AppConfig())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.50),
                    size=0.20,
                    index_position=(0.70, 0.50),
                ),
            ],
            now=0.0,
        )
        first_down = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.80),
                    size=0.20,
                    index_position=(0.70, 0.80),
                ),
            ],
            now=0.1,
        )
        returning = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.68),
                    size=0.20,
                    index_position=(0.70, 0.68),
                ),
            ],
            now=0.2,
        )
        rearmed = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.62),
                    size=0.20,
                    index_position=(0.70, 0.62),
                ),
            ],
            now=0.3,
        )
        continued_return = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.50),
                    size=0.20,
                    index_position=(0.70, 0.50),
                ),
            ],
            now=0.4,
        )
        crossed_return = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.42),
                    size=0.20,
                    index_position=(0.70, 0.42),
                ),
            ],
            now=0.5,
        )
        settled = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.42),
                    size=0.20,
                    index_position=(0.70, 0.42),
                ),
            ],
            now=0.6,
        )
        mild_opposite = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.36),
                    size=0.20,
                    index_position=(0.70, 0.36),
                ),
            ],
            now=0.7,
        )
        second_up = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.31),
                    size=0.20,
                    index_position=(0.70, 0.31),
                ),
            ],
            now=0.8,
        )

        self.assertEqual(first_down.command_gesture, GESTURE_POINT_DOWN)
        self.assertIsNone(returning.command_gesture)
        self.assertIsNone(rearmed.command_gesture)
        self.assertIsNone(continued_return.command_gesture)
        self.assertEqual(crossed_return.command_gesture, GESTURE_POINT_UP)
        self.assertIsNone(settled.command_gesture)
        self.assertIsNone(mild_opposite.command_gesture)
        self.assertIsNone(second_up.command_gesture)

    def test_pointer_vertical_motion_allows_opposite_after_neutral_reset(self) -> None:
        session = GestureSession(AppConfig())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.74),
                    size=0.20,
                    index_position=(0.70, 0.74),
                ),
            ],
            now=0.0,
        )
        first_down = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.82),
                    size=0.20,
                    index_position=(0.70, 0.82),
                ),
            ],
            now=0.1,
        )
        neutral_return = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.75),
                    size=0.20,
                    index_position=(0.70, 0.75),
                ),
            ],
            now=0.2,
        )
        mild_opposite = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.67),
                    size=0.20,
                    index_position=(0.70, 0.67),
                ),
            ],
            now=0.3,
        )
        strong_opposite = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.64),
                    size=0.20,
                    index_position=(0.70, 0.64),
                ),
            ],
            now=0.4,
        )

        self.assertEqual(first_down.command_gesture, GESTURE_POINT_DOWN)
        self.assertIsNone(neutral_return.command_gesture)
        self.assertIn("rebased=True", neutral_return.debug_message)
        self.assertEqual(mild_opposite.command_gesture, GESTURE_POINT_UP)
        self.assertIsNone(strong_opposite.command_gesture)

    def test_pointer_vertical_motion_allows_opposite_after_neutral_dwell(self) -> None:
        session = GestureSession(AppConfig())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.74),
                    size=0.20,
                    index_position=(0.70, 0.74),
                ),
            ],
            now=0.0,
        )
        first_down = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.82),
                    size=0.20,
                    index_position=(0.70, 0.82),
                ),
            ],
            now=0.1,
        )
        neutral_return = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.75),
                    size=0.20,
                    index_position=(0.70, 0.75),
                ),
            ],
            now=0.2,
        )
        for index in range(6):
            idle = session.evaluate(
                [
                    primary,
                    hand_state(
                        GESTURE_POINT,
                        center=(0.70, 0.75),
                        size=0.20,
                        index_position=(0.70, 0.75),
                    ),
                ],
                now=0.3 + index * 0.1,
            )

        opposite_after_dwell = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.67),
                    size=0.20,
                    index_position=(0.70, 0.67),
                ),
            ],
            now=1.0,
        )

        self.assertEqual(first_down.command_gesture, GESTURE_POINT_DOWN)
        self.assertIsNone(neutral_return.command_gesture)
        self.assertIsNone(idle.command_gesture)
        self.assertEqual(opposite_after_dwell.command_gesture, GESTURE_POINT_UP)

    def test_pointer_opposite_direction_works_after_gesture_release(self) -> None:
        session = GestureSession(AppConfig())
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
        first_right = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.56, 0.50),
                    size=0.20,
                    index_position=(0.56, 0.50),
                ),
            ],
            now=0.1,
        )
        session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_OPEN_PALM,
                    center=(0.50, 0.50),
                    size=0.20,
                    index_position=(0.50, 0.50),
                ),
            ],
            now=0.2,
        )
        second_start = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.50, 0.50),
                    size=0.20,
                    index_position=(0.50, 0.50),
                ),
            ],
            now=0.3,
        )
        second_left = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.44, 0.50),
                    size=0.20,
                    index_position=(0.44, 0.50),
                ),
            ],
            now=0.4,
        )

        self.assertEqual(first_right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(second_start.command_gesture)
        self.assertEqual(second_left.command_gesture, GESTURE_POINT_LEFT)

    def test_pointer_uses_fresh_start_after_secondary_hand_loss(self) -> None:
        session = GestureSession(AppConfig())
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
        first_right = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.56, 0.50),
                    size=0.20,
                    index_position=(0.56, 0.50),
                ),
            ],
            now=0.1,
        )
        secondary_lost = session.evaluate([primary], now=0.2)
        second_start = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.80, 0.50),
                    size=0.20,
                    index_position=(0.80, 0.50),
                ),
            ],
            now=0.3,
        )
        second_left = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.74, 0.50),
                    size=0.20,
                    index_position=(0.74, 0.50),
                ),
            ],
            now=0.4,
        )

        self.assertEqual(first_right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertIsNone(secondary_lost.command_gesture)
        self.assertIsNone(second_start.command_gesture)
        self.assertEqual(second_left.command_gesture, GESTURE_POINT_LEFT)

    def test_pointer_hold_does_not_emit_again(self) -> None:
        session = GestureSession(AppConfig())
        primary = hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

        session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.50),
                    size=0.20,
                    index_position=(0.50, 0.50),
                ),
            ],
            now=0.0,
        )
        first_down = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.60),
                    size=0.20,
                    index_position=(0.50, 0.60),
                ),
            ],
            now=0.1,
        )
        self.assertTrue(
            session.should_emit(first_down.command_gesture, "DPAD_DOWN", now=0.1)
        )
        session.record_emit(first_down.command_gesture, now=0.1)

        held_down = session.evaluate(
            [
                primary,
                hand_state(
                    GESTURE_POINT,
                    center=(0.70, 0.58),
                    size=0.20,
                    index_position=(0.50, 0.58),
                ),
            ],
            now=0.41,
        )

        self.assertIsNone(held_down.command_gesture)


if __name__ == "__main__":
    unittest.main()
