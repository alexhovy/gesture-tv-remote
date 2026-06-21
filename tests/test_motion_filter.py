import unittest

from src.domain.constants import (
    GESTURE_POINT,
    GESTURE_POINT_DOWN,
    GESTURE_POINT_RIGHT,
    GESTURE_VOLUME_UP,
)
from src.domain.motion_filter import (
    MOTION_ACTIVATION_RATIO,
    MOTION_NEUTRAL_RATIO,
    MOTION_RELEASE_RATIO,
    classify_pointer_joystick,
    classify_volume_joystick,
    neutral_distance,
    release_distance,
)


class MotionFilterTests(unittest.TestCase):
    def test_pointer_uses_activation_threshold_from_anchor(self) -> None:
        decision = classify_pointer_joystick(
            anchor_position=(0.50, 0.50),
            current_position=(0.50, 0.50 + 0.05 * MOTION_ACTIVATION_RATIO),
            distance=0.05,
            dominance=1.0,
            prefix=GESTURE_POINT,
        )

        self.assertEqual(decision.gesture, GESTURE_POINT_DOWN)
        self.assertAlmostEqual(decision.activation_distance, 0.05 * MOTION_ACTIVATION_RATIO)
        self.assertAlmostEqual(decision.threshold_ratio, 1.0)
        self.assertFalse(decision.in_neutral)
        self.assertIsNone(decision.blocked_reason)

    def test_pointer_reports_neutral_zone_before_threshold(self) -> None:
        activation = 0.05 * MOTION_ACTIVATION_RATIO
        decision = classify_pointer_joystick(
            anchor_position=(0.50, 0.50),
            current_position=(0.50, 0.50 + activation * MOTION_NEUTRAL_RATIO),
            distance=0.05,
            dominance=1.0,
            prefix=GESTURE_POINT,
        )

        self.assertIsNone(decision.gesture)
        self.assertTrue(decision.in_neutral)
        self.assertEqual(decision.blocked_reason, "neutral")

    def test_pointer_reports_below_threshold_near_miss(self) -> None:
        decision = classify_pointer_joystick(
            anchor_position=(0.50, 0.50),
            current_position=(0.50, 0.531),
            distance=0.05,
            dominance=1.0,
            prefix=GESTURE_POINT,
        )

        self.assertIsNone(decision.gesture)
        self.assertFalse(decision.in_neutral)
        self.assertFalse(decision.in_release)
        self.assertEqual(decision.blocked_reason, "below_threshold")
        self.assertGreater(decision.threshold_ratio, 0.95)
        self.assertLess(decision.threshold_ratio, 1.0)

    def test_pointer_reports_release_zone_outside_neutral(self) -> None:
        decision = classify_pointer_joystick(
            anchor_position=(0.50, 0.50),
            current_position=(0.50, 0.525),
            distance=0.05,
            dominance=1.0,
            prefix=GESTURE_POINT,
        )

        self.assertIsNone(decision.gesture)
        self.assertFalse(decision.in_neutral)
        self.assertTrue(decision.in_release)
        self.assertEqual(decision.blocked_reason, "below_threshold")

    def test_pointer_uses_dominant_axis(self) -> None:
        decision = classify_pointer_joystick(
            anchor_position=(0.50, 0.50),
            current_position=(0.56, 0.51),
            distance=0.05,
            dominance=1.25,
            prefix=GESTURE_POINT,
        )

        self.assertEqual(decision.gesture, GESTURE_POINT_RIGHT)
        self.assertAlmostEqual(decision.magnitude, 0.06)

    def test_volume_uses_activation_threshold_from_anchor(self) -> None:
        decision = classify_volume_joystick(
            anchor_y=0.50,
            current_y=0.50 - 0.05 * MOTION_ACTIVATION_RATIO,
            distance=0.05,
        )

        self.assertEqual(decision.gesture, GESTURE_VOLUME_UP)
        self.assertAlmostEqual(decision.activation_distance, 0.05 * MOTION_ACTIVATION_RATIO)
        self.assertAlmostEqual(decision.threshold_ratio, 1.0)

    def test_neutral_distance_is_smaller_than_activation_threshold(self) -> None:
        activation = 0.08 * MOTION_ACTIVATION_RATIO

        self.assertAlmostEqual(neutral_distance(activation), activation * MOTION_NEUTRAL_RATIO)

    def test_release_distance_is_larger_than_neutral_and_below_activation(self) -> None:
        activation = 0.08 * MOTION_ACTIVATION_RATIO

        self.assertAlmostEqual(release_distance(activation), activation * MOTION_RELEASE_RATIO)
        self.assertGreater(release_distance(activation), neutral_distance(activation))
        self.assertLess(release_distance(activation), activation)


if __name__ == "__main__":
    unittest.main()
