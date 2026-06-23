import unittest
from types import SimpleNamespace

from src.domain.constants import (
    GESTURE_FIST,
    GESTURE_OPEN_PALM,
    GESTURE_PINCH,
    GESTURE_TWO_FINGERS,
    HANDEDNESS_RIGHT,
)
from src.domain.geometry.landmarks import (
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
from src.domain.gestures.gesture_classification import classify_static_hand_pose


class GestureRuleTests(unittest.TestCase):
    def test_static_pose_classifier_accepts_upright_open_palm(self) -> None:
        self.assertEqual(
            classify_static_hand_pose(_open_palm_landmarks(), HANDEDNESS_RIGHT, 0.22),
            GESTURE_OPEN_PALM,
        )

    def test_static_pose_classifier_rejects_sideways_open_palm(self) -> None:
        self.assertIsNone(
            classify_static_hand_pose(
                _open_palm_landmarks(wrist=(0.40, 0.80), middle_mcp=(0.80, 0.70)),
                HANDEDNESS_RIGHT,
                0.22,
            )
        )

    def test_static_pose_classifier_rejects_upside_down_open_palm(self) -> None:
        self.assertIsNone(
            classify_static_hand_pose(
                _open_palm_landmarks(wrist=(0.50, 0.20), middle_mcp=(0.50, 0.55)),
                HANDEDNESS_RIGHT,
                0.22,
            )
        )

    def test_static_pose_classifier_allows_non_upright_hand_when_requirement_disabled(
        self,
    ) -> None:
        self.assertEqual(
            classify_static_hand_pose(
                _open_palm_landmarks(wrist=(0.40, 0.80), middle_mcp=(0.80, 0.70)),
                HANDEDNESS_RIGHT,
                0.22,
                require_upright_hand=False,
            ),
            GESTURE_OPEN_PALM,
        )

    def test_static_pose_classifier_allows_configured_tilt_tolerance(self) -> None:
        self.assertEqual(
            classify_static_hand_pose(
                _open_palm_landmarks(wrist=(0.50, 0.80), middle_mcp=(0.70, 0.50)),
                HANDEDNESS_RIGHT,
                0.22,
                upright_max_tilt_ratio=0.75,
            ),
            GESTURE_OPEN_PALM,
        )

    def test_static_pose_classifier_detects_two_fingers(self) -> None:
        self.assertEqual(
            classify_static_hand_pose(_two_finger_landmarks(), HANDEDNESS_RIGHT, 0.22),
            GESTURE_TWO_FINGERS,
        )

    def test_static_pose_classifier_treats_folded_thumb_as_fist(self) -> None:
        self.assertEqual(
            classify_static_hand_pose(
                _fist_with_folded_thumb_landmarks(),
                HANDEDNESS_RIGHT,
                0.22,
            ),
            GESTURE_FIST,
        )

    def test_static_pose_classifier_treats_extended_thumb_as_fist(self) -> None:
        self.assertEqual(
            classify_static_hand_pose(
                _fist_landmarks(thumb_tip=(0.24, 0.50)),
                HANDEDNESS_RIGHT,
                0.22,
            ),
            GESTURE_FIST,
        )

    def test_static_pose_classifier_treats_thumb_touching_closed_index_as_fist(
        self,
    ) -> None:
        self.assertEqual(
            classify_static_hand_pose(
                _fist_landmarks(thumb_tip=(0.43, 0.62)),
                HANDEDNESS_RIGHT,
                0.22,
            ),
            GESTURE_FIST,
        )

    def test_static_pose_classifier_detects_pinch_when_index_is_not_closed(
        self,
    ) -> None:
        self.assertEqual(
            classify_static_hand_pose(_pinch_landmarks(), HANDEDNESS_RIGHT, 0.22),
            GESTURE_PINCH,
        )


def _open_palm_landmarks(
    wrist: tuple[float, float] = (0.50, 0.80),
    middle_mcp: tuple[float, float] = (0.50, 0.50),
    thumb_ip: tuple[float, float] = (0.36, 0.56),
    thumb_tip: tuple[float, float] = (0.24, 0.50),
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
    landmarks[LANDMARK_THUMB_IP] = _landmark(*thumb_ip)
    landmarks[LANDMARK_THUMB_TIP] = _landmark(*thumb_tip)
    return landmarks


def _two_finger_landmarks() -> list[SimpleNamespace]:
    landmarks = [_landmark(0.50, 0.50) for _ in range(LANDMARK_COUNT)]
    landmarks[LANDMARK_WRIST] = _landmark(0.50, 0.80)
    landmarks[LANDMARK_INDEX_MCP] = _landmark(0.42, 0.54)
    landmarks[LANDMARK_MIDDLE_MCP] = _landmark(0.50, 0.50)
    landmarks[LANDMARK_RING_MCP] = _landmark(0.58, 0.54)
    landmarks[LANDMARK_PINKY_MCP] = _landmark(0.64, 0.58)
    landmarks[LANDMARK_INDEX_PIP] = _landmark(0.42, 0.45)
    landmarks[LANDMARK_MIDDLE_PIP] = _landmark(0.50, 0.44)
    landmarks[LANDMARK_RING_PIP] = _landmark(0.58, 0.45)
    landmarks[LANDMARK_PINKY_PIP] = _landmark(0.64, 0.48)
    landmarks[LANDMARK_INDEX_TIP] = _landmark(0.42, 0.24)
    landmarks[LANDMARK_MIDDLE_TIP] = _landmark(0.50, 0.24)
    landmarks[LANDMARK_RING_TIP] = _landmark(0.58, 0.62)
    landmarks[LANDMARK_PINKY_TIP] = _landmark(0.64, 0.63)
    landmarks[LANDMARK_THUMB_TIP] = _landmark(0.36, 0.56)
    return landmarks


def _fist_with_folded_thumb_landmarks() -> list[SimpleNamespace]:
    return _fist_landmarks(thumb_tip=(0.40, 0.48))


def _fist_landmarks(thumb_tip: tuple[float, float]) -> list[SimpleNamespace]:
    landmarks = [_landmark(0.50, 0.50) for _ in range(LANDMARK_COUNT)]
    landmarks[LANDMARK_WRIST] = _landmark(0.50, 0.80)
    landmarks[LANDMARK_INDEX_MCP] = _landmark(0.42, 0.54)
    landmarks[LANDMARK_MIDDLE_MCP] = _landmark(0.50, 0.50)
    landmarks[LANDMARK_RING_MCP] = _landmark(0.58, 0.54)
    landmarks[LANDMARK_PINKY_MCP] = _landmark(0.64, 0.58)
    landmarks[LANDMARK_INDEX_PIP] = _landmark(0.42, 0.45)
    landmarks[LANDMARK_MIDDLE_PIP] = _landmark(0.50, 0.44)
    landmarks[LANDMARK_RING_PIP] = _landmark(0.58, 0.45)
    landmarks[LANDMARK_PINKY_PIP] = _landmark(0.64, 0.48)
    landmarks[LANDMARK_INDEX_TIP] = _landmark(0.42, 0.62)
    landmarks[LANDMARK_MIDDLE_TIP] = _landmark(0.50, 0.62)
    landmarks[LANDMARK_RING_TIP] = _landmark(0.58, 0.62)
    landmarks[LANDMARK_PINKY_TIP] = _landmark(0.64, 0.63)
    landmarks[LANDMARK_THUMB_TIP] = _landmark(*thumb_tip)
    return landmarks


def _pinch_landmarks() -> list[SimpleNamespace]:
    landmarks = _fist_landmarks(thumb_tip=(0.43, 0.25))
    landmarks[LANDMARK_INDEX_TIP] = _landmark(0.42, 0.24)
    return landmarks


def _landmark(x: float, y: float) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y)


if __name__ == "__main__":
    unittest.main()
