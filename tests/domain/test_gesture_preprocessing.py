import unittest
from types import SimpleNamespace

from src.domain.constants import HANDEDNESS_RIGHT
from src.domain.gestures.gesture_preprocessing import (
    RawDetectedHandState,
    deduplicate_raw_hands,
    hand_landmark_sets_are_duplicates,
)


class GesturePreprocessingTests(unittest.TestCase):
    def test_duplicate_hand_landmark_sets_match_log_pattern(self) -> None:
        first = _landmarks(center=(0.48, 0.78), size=0.14)
        second = _landmarks(center=(0.48, 0.76), size=0.17)

        self.assertTrue(hand_landmark_sets_are_duplicates(first, second))

    def test_separated_hands_are_not_duplicates(self) -> None:
        first = _landmarks(center=(0.20, 0.50), size=0.20)
        second = _landmarks(center=(0.80, 0.50), size=0.20)

        self.assertFalse(hand_landmark_sets_are_duplicates(first, second))

    def test_deduplicate_raw_hands_keeps_larger_duplicate(self) -> None:
        smaller = RawDetectedHandState(
            landmarks=_landmarks(center=(0.48, 0.78), size=0.14),
            handedness=HANDEDNESS_RIGHT,
        )
        larger = RawDetectedHandState(
            landmarks=_landmarks(center=(0.48, 0.76), size=0.17),
            handedness=HANDEDNESS_RIGHT,
        )

        self.assertEqual(deduplicate_raw_hands([smaller, larger]), [larger])

    def test_deduplicate_raw_hands_preserves_distinct_hands(self) -> None:
        left = RawDetectedHandState(
            landmarks=_landmarks(center=(0.20, 0.50), size=0.20),
            handedness=HANDEDNESS_RIGHT,
        )
        right = RawDetectedHandState(
            landmarks=_landmarks(center=(0.80, 0.50), size=0.20),
            handedness=HANDEDNESS_RIGHT,
        )

        self.assertEqual(deduplicate_raw_hands([left, right]), [left, right])


def _landmarks(center: tuple[float, float], size: float) -> list[SimpleNamespace]:
    center_x, center_y = center
    half_size = size / 2
    corners = (
        (center_x - half_size, center_y - half_size),
        (center_x + half_size, center_y - half_size),
        (center_x + half_size, center_y + half_size),
        (center_x - half_size, center_y + half_size),
    )
    return [SimpleNamespace(x=x, y=y) for x, y in corners]


if __name__ == "__main__":
    unittest.main()
