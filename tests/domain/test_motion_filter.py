import unittest

from src.domain.constants import (
    GESTURE_POINT,
    GESTURE_POINT_DOWN,
    GESTURE_POINT_RIGHT,
    GESTURE_VOLUME_DOWN,
    GESTURE_VOLUME_UP,
)
from src.domain.geometry.display_geometry import DisplayMotionScale
from src.domain.gestures.motion_filter import (
    classify_pointer_joystick,
    classify_volume_joystick,
)


class MotionFilterTests(unittest.TestCase):
    def test_pointer_uses_neutral_radius_from_anchor(self) -> None:
        decision = classify_pointer_joystick(
            anchor_position=(0.50, 0.50),
            current_position=(0.50, 0.61),
            distance=0.05,
            dominance=1.0,
            prefix=GESTURE_POINT,
        )

        self.assertEqual(decision.gesture, GESTURE_POINT_DOWN)
        self.assertAlmostEqual(decision.activation_distance, 0.0575)
        self.assertAlmostEqual(decision.neutral_distance, 0.05)
        self.assertAlmostEqual(decision.threshold_ratio, 1.91, places=2)
        self.assertFalse(decision.in_neutral)
        self.assertIsNone(decision.blocked_reason)

    def test_pointer_reports_inside_neutral_radius(self) -> None:
        decision = classify_pointer_joystick(
            anchor_position=(0.50, 0.50),
            current_position=(0.50, 0.54),
            distance=0.05,
            dominance=1.0,
            prefix=GESTURE_POINT,
        )

        self.assertIsNone(decision.gesture)
        self.assertTrue(decision.in_neutral)
        self.assertEqual(decision.blocked_reason, "neutral")

    def test_pointer_uses_euclidean_circle_for_neutral(self) -> None:
        decision = classify_pointer_joystick(
            anchor_position=(0.50, 0.50),
            current_position=(0.535, 0.535),
            distance=0.05,
            dominance=1.0,
            prefix=GESTURE_POINT,
        )

        self.assertIsNone(decision.gesture)
        self.assertTrue(decision.in_neutral)
        self.assertEqual(decision.blocked_reason, "neutral")
        self.assertAlmostEqual(decision.threshold_ratio, 0.86, places=2)

    def test_pointer_blocks_between_neutral_and_activation_margin(self) -> None:
        decision = classify_pointer_joystick(
            anchor_position=(0.50, 0.50),
            current_position=(0.50, 0.555),
            distance=0.05,
            dominance=1.0,
            prefix=GESTURE_POINT,
        )

        self.assertIsNone(decision.gesture)
        self.assertFalse(decision.in_neutral)
        self.assertEqual(decision.blocked_reason, "inside_activation")

    def test_pointer_uses_dominant_axis(self) -> None:
        decision = classify_pointer_joystick(
            anchor_position=(0.50, 0.50),
            current_position=(0.58, 0.51),
            distance=0.05,
            dominance=1.25,
            prefix=GESTURE_POINT,
        )

        self.assertEqual(decision.gesture, GESTURE_POINT_RIGHT)
        self.assertAlmostEqual(decision.magnitude, 0.08)

    def test_pointer_scales_motion_for_tall_rendered_display(self) -> None:
        unscaled = classify_pointer_joystick(
            anchor_position=(0.50, 0.50),
            current_position=(0.50, 0.59),
            distance=0.10,
            dominance=1.0,
            prefix=GESTURE_POINT,
        )
        scaled = classify_pointer_joystick(
            anchor_position=(0.50, 0.50),
            current_position=(0.50, 0.59),
            distance=0.10,
            dominance=1.0,
            prefix=GESTURE_POINT,
            motion_scale=DisplayMotionScale(x=1.0, y=2.0),
        )

        self.assertIsNone(unscaled.gesture)
        self.assertEqual(scaled.gesture, GESTURE_POINT_DOWN)

    def test_volume_uses_neutral_band_from_anchor(self) -> None:
        decision = classify_volume_joystick(
            anchor_y=0.50,
            current_y=0.44,
            distance=0.05,
        )

        self.assertEqual(decision.gesture, GESTURE_VOLUME_UP)
        self.assertAlmostEqual(decision.activation_distance, 0.0575)
        self.assertAlmostEqual(decision.neutral_distance, 0.05)
        self.assertAlmostEqual(decision.threshold_ratio, 1.04, places=2)

    def test_volume_scales_motion_for_tall_rendered_display(self) -> None:
        unscaled = classify_volume_joystick(
            anchor_y=0.50,
            current_y=0.59,
            distance=0.10,
        )
        scaled = classify_volume_joystick(
            anchor_y=0.50,
            current_y=0.59,
            distance=0.10,
            motion_scale=DisplayMotionScale(x=1.0, y=2.0),
        )

        self.assertIsNone(unscaled.gesture)
        self.assertEqual(scaled.gesture, GESTURE_VOLUME_DOWN)


if __name__ == "__main__":
    unittest.main()
