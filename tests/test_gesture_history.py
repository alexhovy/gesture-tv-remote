import unittest

from src.domain.gestures.gesture_history import BoundedHistory


class BoundedHistoryTests(unittest.TestCase):
    def test_history_drops_oldest_values_at_capacity(self) -> None:
        history = BoundedHistory[int](3)

        history.append(1)
        history.append(2)
        history.append(3)
        history.append(4)

        self.assertEqual(history.values(), (2, 3, 4))
        self.assertEqual(history.latest(), 4)

    def test_history_requires_positive_capacity(self) -> None:
        with self.assertRaises(ValueError):
            BoundedHistory[int](0)


if __name__ == "__main__":
    unittest.main()
