import unittest
from types import SimpleNamespace

from src.domain.constants import (
    GESTURE_OPEN_PALM,
    GESTURE_POINT,
    GESTURE_POINT_RIGHT,
    GESTURE_VOLUME_DOWN,
    GESTURE_VOLUME_UP,
    HANDEDNESS_RIGHT,
)
from src.domain.gestures import detect_direction, detect_volume
from src.domain.gestures import detect_gesture
from src.domain.landmarks import (
    LANDMARK_COUNT,
    LANDMARK_INDEX_MCP,
    LANDMARK_INDEX_PIP,
    LANDMARK_INDEX_TIP,
    LANDMARK_MIDDLE_MCP,
    LANDMARK_MIDDLE_PIP,
    LANDMARK_MIDDLE_TIP,
    LANDMARK_PINKY_MCP,
    LANDMARK_PINKY_PIP,
    LANDMARK_PINKY_TIP,
    LANDMARK_RING_MCP,
    LANDMARK_RING_PIP,
    LANDMARK_RING_TIP,
    LANDMARK_THUMB_IP,
    LANDMARK_THUMB_TIP,
    LANDMARK_WRIST,
)


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

    def test_detect_gesture_accepts_upright_open_palm(self) -> None:
        self.assertEqual(
            detect_gesture(_open_palm_landmarks(), HANDEDNESS_RIGHT, 0.22),
            GESTURE_OPEN_PALM,
        )

    def test_detect_gesture_rejects_sideways_open_palm(self) -> None:
        self.assertIsNone(
            detect_gesture(
                _open_palm_landmarks(wrist=(0.40, 0.80), middle_mcp=(0.80, 0.70)),
                HANDEDNESS_RIGHT,
                0.22,
            )
        )

    def test_detect_gesture_rejects_upside_down_open_palm(self) -> None:
        self.assertIsNone(
            detect_gesture(
                _open_palm_landmarks(wrist=(0.50, 0.20), middle_mcp=(0.50, 0.55)),
                HANDEDNESS_RIGHT,
                0.22,
            )
        )

    def test_detect_gesture_allows_non_upright_hand_when_requirement_disabled(self) -> None:
        self.assertEqual(
            detect_gesture(
                _open_palm_landmarks(wrist=(0.40, 0.80), middle_mcp=(0.80, 0.70)),
                HANDEDNESS_RIGHT,
                0.22,
                require_upright_hand=False,
            ),
            GESTURE_OPEN_PALM,
        )

    def test_detect_gesture_allows_configured_tilt_tolerance(self) -> None:
        self.assertEqual(
            detect_gesture(
                _open_palm_landmarks(wrist=(0.50, 0.80), middle_mcp=(0.70, 0.50)),
                HANDEDNESS_RIGHT,
                0.22,
                upright_max_tilt_ratio=0.75,
            ),
            GESTURE_OPEN_PALM,
        )


def _open_palm_landmarks(
    wrist: tuple[float, float] = (0.50, 0.80),
    middle_mcp: tuple[float, float] = (0.50, 0.50),
) -> list[SimpleNamespace]:
    landmarks = [_landmark(0.50, 0.50) for _ in range(LANDMARK_COUNT)]
    landmarks[LANDMARK_WRIST] = _landmark(*wrist)
    landmarks[LANDMARK_INDEX_MCP] = _landmark(0.40, 0.52)
    landmarks[LANDMARK_MIDDLE_MCP] = _landmark(*middle_mcp)
    landmarks[LANDMARK_RING_MCP] = _landmark(0.60, 0.52)
    landmarks[LANDMARK_PINKY_MCP] = _landmark(0.68, 0.58)
    landmarks[LANDMARK_INDEX_PIP] = _landmark(0.40, 0.38)
    landmarks[LANDMARK_MIDDLE_PIP] = _landmark(0.50, 0.35)
    landmarks[LANDMARK_RING_PIP] = _landmark(0.60, 0.38)
    landmarks[LANDMARK_PINKY_PIP] = _landmark(0.68, 0.42)
    landmarks[LANDMARK_INDEX_TIP] = _landmark(0.40, 0.20)
    landmarks[LANDMARK_MIDDLE_TIP] = _landmark(0.50, 0.16)
    landmarks[LANDMARK_RING_TIP] = _landmark(0.60, 0.20)
    landmarks[LANDMARK_PINKY_TIP] = _landmark(0.68, 0.26)
    landmarks[LANDMARK_THUMB_IP] = _landmark(0.36, 0.56)
    landmarks[LANDMARK_THUMB_TIP] = _landmark(0.24, 0.50)
    return landmarks


def _landmark(x: float, y: float) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y)


if __name__ == "__main__":
    unittest.main()
