import unittest

from src.domain.constants import (
    GESTURE_POINT,
    GESTURE_POINT_RIGHT,
    GESTURE_VOLUME_DOWN,
    GESTURE_VOLUME_UP,
)
from src.domain.gestures import detect_direction, detect_volume


class GestureRuleTests(unittest.TestCase):
    def test_detect_direction_requires_minimum_distance(self) -> None:
        self.assertIsNone(
            detect_direction(
                start=(0.5, 0.5),
                end=(0.52, 0.51),
                distance=0.08,
                dominance=1.15,
                prefix=GESTURE_POINT,
            )
        )

    def test_detect_direction_returns_dominant_axis(self) -> None:
        self.assertEqual(
            detect_direction(
                start=(0.5, 0.5),
                end=(0.7, 0.53),
                distance=0.08,
                dominance=1.15,
                prefix=GESTURE_POINT,
            ),
            GESTURE_POINT_RIGHT,
        )

    def test_detect_volume_maps_upward_motion_to_volume_up(self) -> None:
        self.assertEqual(detect_volume(0.6, 0.4, distance=0.16), GESTURE_VOLUME_UP)

    def test_detect_volume_maps_downward_motion_to_volume_down(self) -> None:
        self.assertEqual(detect_volume(0.4, 0.6, distance=0.16), GESTURE_VOLUME_DOWN)


if __name__ == "__main__":
    unittest.main()
