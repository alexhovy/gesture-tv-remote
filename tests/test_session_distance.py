import unittest

from src.domain.evaluators.volume_evaluator import scaled_distance


class SessionDistanceTests(unittest.TestCase):
    def test_scaled_distance_clamps_to_minimum_and_maximum(self) -> None:
        self.assertEqual(
            scaled_distance(
                hand_size=0.01,
                ratio=0.45,
                min_distance=0.04,
                max_distance=0.14,
            ),
            0.04,
        )
        self.assertEqual(
            scaled_distance(
                hand_size=1.00,
                ratio=0.45,
                min_distance=0.04,
                max_distance=0.14,
            ),
            0.14,
        )


if __name__ == "__main__":
    unittest.main()
