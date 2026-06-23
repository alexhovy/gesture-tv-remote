import unittest

from src.domain.constants import GESTURE_POINT_RIGHT, GESTURE_VOLUME_UP
from src.domain.evaluators.pointer_evaluator import evaluate_pointer_motion
from src.domain.evaluators.volume_evaluator import evaluate_volume_motion
from src.domain.motion_gesture import MotionJoystickState
from tests.config_helpers import app_config


class SessionEvaluatorTests(unittest.TestCase):
    def test_pointer_evaluator_anchors_and_emits_direction(self) -> None:
        pointer = MotionJoystickState()
        config = app_config(debounce_seconds=0.3)

        neutral = evaluate_pointer_motion(
            pointer,
            pointer_position=(0.50, 0.50),
            pointer_reference_size=1.0,
            config=config,
            now=0.1,
        )
        right = evaluate_pointer_motion(
            pointer,
            pointer_position=(0.67, 0.50),
            pointer_reference_size=1.0,
            config=config,
            now=0.2,
        )

        self.assertIsNone(neutral.command_gesture)
        self.assertEqual(pointer.anchor, (0.50, 0.50))
        self.assertEqual(right.command_gesture, GESTURE_POINT_RIGHT)
        self.assertEqual(right.position, (0.67, 0.50))
        self.assertAlmostEqual(right.distance, 0.14)
        self.assertEqual(pointer.active_gesture, GESTURE_POINT_RIGHT)

    def test_volume_evaluator_anchors_and_emits_direction(self) -> None:
        volume = MotionJoystickState()
        config = app_config(debounce_seconds=0.3)

        neutral = evaluate_volume_motion(
            volume,
            active_center=(0.70, 0.50),
            active_size=0.20,
            config=config,
            now=0.1,
        )
        up = evaluate_volume_motion(
            volume,
            active_center=(0.70, 0.29),
            active_size=0.20,
            config=config,
            now=0.2,
        )

        self.assertIsNone(neutral.command_gesture)
        self.assertEqual(volume.anchor, 0.50)
        self.assertEqual(volume.visual_anchor, (0.70, 0.50))
        self.assertEqual(up.command_gesture, GESTURE_VOLUME_UP)
        self.assertEqual(up.position, (0.70, 0.29))
        self.assertAlmostEqual(up.distance, 0.16)
        self.assertEqual(volume.active_gesture, GESTURE_VOLUME_UP)


if __name__ == "__main__":
    unittest.main()
