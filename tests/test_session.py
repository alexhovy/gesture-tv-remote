import unittest
from types import SimpleNamespace

from src.domain.constants import (
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_POINT,
    GESTURE_POINT_RIGHT,
    GESTURE_VOLUME_DOWN,
)
from src.domain.landmarks import LANDMARK_COUNT, LANDMARK_INDEX_TIP
from src.domain.session import GestureSession, HandState
from src.shared.config import AppConfig


class GestureSessionTests(unittest.TestCase):
    def test_pointer_distance_scales_with_hand_size(self) -> None:
        self.assertEqual(
            _evaluate_pointer_move(hand_size=0.10, start_x=0.50, end_x=0.55),
            GESTURE_POINT_RIGHT,
        )
        self.assertIsNone(
            _evaluate_pointer_move(hand_size=0.25, start_x=0.50, end_x=0.55)
        )

    def test_volume_distance_scales_with_hand_size(self) -> None:
        self.assertEqual(
            _evaluate_volume_move(hand_size=0.10, start_y=0.50, end_y=0.54),
            GESTURE_VOLUME_DOWN,
        )
        self.assertIsNone(
            _evaluate_volume_move(hand_size=0.25, start_y=0.50, end_y=0.54)
        )

    def test_scaled_distance_clamps_to_minimum_and_maximum(self) -> None:
        self.assertEqual(
            GestureSession._scaled_distance(
                hand_size=0.01,
                ratio=0.45,
                min_distance=0.04,
                max_distance=0.14,
            ),
            0.04,
        )
        self.assertEqual(
            GestureSession._scaled_distance(
                hand_size=1.00,
                ratio=0.45,
                min_distance=0.04,
                max_distance=0.14,
            ),
            0.14,
        )


def _evaluate_pointer_move(hand_size: float, start_x: float, end_x: float) -> str | None:
    session = GestureSession(AppConfig())
    primary = _hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

    session.evaluate(
        [
            primary,
            _hand_state(
                GESTURE_POINT,
                center=(0.70, 0.50),
                size=hand_size,
                index_position=(start_x, 0.50),
            ),
        ],
        now=0.0,
    )
    return session.evaluate(
        [
            primary,
            _hand_state(
                GESTURE_POINT,
                center=(0.70, 0.50),
                size=hand_size,
                index_position=(end_x, 0.50),
            ),
        ],
        now=0.1,
    ).command_gesture


def _evaluate_volume_move(hand_size: float, start_y: float, end_y: float) -> str | None:
    session = GestureSession(AppConfig())
    primary = _hand_state(GESTURE_OPEN_PALM, center=(0.20, 0.50), size=0.20)

    session.evaluate(
        [
            primary,
            _hand_state(GESTURE_PINCH, center=(0.70, start_y), size=hand_size),
        ],
        now=0.0,
    )
    return session.evaluate(
        [
            primary,
            _hand_state(GESTURE_PINCH, center=(0.70, end_y), size=hand_size),
        ],
        now=0.1,
    ).command_gesture


def _hand_state(
    gesture: str,
    center: tuple[float, float],
    size: float,
    index_position: tuple[float, float] = (0.0, 0.0),
) -> HandState:
    landmarks = [SimpleNamespace(x=0.0, y=0.0) for _ in range(LANDMARK_COUNT)]
    landmarks[LANDMARK_INDEX_TIP] = SimpleNamespace(
        x=index_position[0],
        y=index_position[1],
    )

    return HandState(
        landmarks=landmarks,
        gesture=gesture,
        center=center,
        size=size,
    )


if __name__ == "__main__":
    unittest.main()
