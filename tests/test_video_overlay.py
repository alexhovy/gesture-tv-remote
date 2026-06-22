import sys
import types
import unittest

from src.domain.session_types import PointerDebug, VolumeDebug
from src.infrastructure.camera.video_preprocessing import CropRect


cv2_stub = types.ModuleType("cv2")
cv2_stub.line = lambda *args, **kwargs: None
cv2_stub.circle = lambda *args, **kwargs: None
cv2_stub.putText = lambda *args, **kwargs: None
cv2_stub.FONT_HERSHEY_SIMPLEX = 0
sys.modules.setdefault("cv2", cv2_stub)

from src.infrastructure.camera import video_overlay  # noqa: E402


class VideoOverlayTests(unittest.TestCase):
    def test_pointer_zones_draw_anchor_current_thresholds_and_labels(self) -> None:
        cv2 = FakeCv2()
        original_cv2 = video_overlay.cv2
        video_overlay.cv2 = cv2
        try:
            video_overlay.draw_pointer_zones(
                FakeFrame(100, 200),
                PointerDebug(
                    anchor=(0.50, 0.50),
                    current=(0.60, 0.50),
                    active_gesture="POINT_RIGHT",
                    candidate_gesture="POINT_RIGHT",
                    phase="triggered",
                    armed=False,
                    activation_distance=0.05,
                    neutral_distance=0.08,
                    threshold_ratio=2.0,
                    in_neutral=False,
                    blocked_reason="holding",
                ),
                CropRect(0.0, 0.0, 1.0, 1.0),
            )
        finally:
            video_overlay.cv2 = original_cv2

        self.assertGreaterEqual(len(cv2.circles), 3)
        self.assertIn(((100, 50), 8, video_overlay.COLOR_RELEASE, 2), cv2.circles)
        self.assertIn(((100, 50), 5, video_overlay.COLOR_ACTIVE, -1), cv2.circles)
        self.assertIn(((120, 50), 6, video_overlay.COLOR_CURRENT, 2), cv2.circles)
        self.assertIn(((90, 0), (90, 100), video_overlay.COLOR_DIRECTION, 1), cv2.lines)
        self.assertIn(((110, 0), (110, 100), video_overlay.COLOR_DIRECTION, 1), cv2.lines)
        self.assertIn(((100, 50), (120, 50), video_overlay.COLOR_ACTIVE, 2), cv2.lines)
        self.assertTrue(any(call[0] == "LEFT" for call in cv2.text))
        self.assertTrue(any(call[0].startswith("POINT_RIGHT") for call in cv2.text))

    def test_pointer_zones_skip_missing_anchor(self) -> None:
        cv2 = FakeCv2()
        original_cv2 = video_overlay.cv2
        video_overlay.cv2 = cv2
        try:
            video_overlay.draw_pointer_zones(
                FakeFrame(100, 200),
                PointerDebug(
                    anchor=None,
                    current=(0.60, 0.50),
                    active_gesture=None,
                    candidate_gesture=None,
                    phase="armed",
                    armed=True,
                    activation_distance=0.05,
                    neutral_distance=0.02,
                    threshold_ratio=0.0,
                    in_neutral=True,
                    blocked_reason=None,
                ),
                CropRect(0.0, 0.0, 1.0, 1.0),
            )
        finally:
            video_overlay.cv2 = original_cv2

        self.assertEqual(cv2.circles, [])
        self.assertEqual(cv2.lines, [])
        self.assertEqual(cv2.text, [])

    def test_volume_zones_draw_anchor_current_thresholds_and_labels(self) -> None:
        cv2 = FakeCv2()
        original_cv2 = video_overlay.cv2
        video_overlay.cv2 = cv2
        try:
            video_overlay.draw_volume_zones(
                FakeFrame(100, 200),
                VolumeDebug(
                    anchor=(0.50, 0.50),
                    anchor_y=0.50,
                    current=(0.60, 0.70),
                    active_gesture="VOLUME_DOWN",
                    candidate_gesture="VOLUME_DOWN",
                    phase="triggered",
                    armed=False,
                    activation_distance=0.05,
                    neutral_distance=0.08,
                    threshold_ratio=4.0,
                    in_neutral=False,
                    blocked_reason="holding",
                ),
                CropRect(0.0, 0.0, 1.0, 1.0),
            )
        finally:
            video_overlay.cv2 = original_cv2

        self.assertIn(((100, 50), 5, video_overlay.COLOR_ACTIVE, -1), cv2.circles)
        self.assertIn(((120, 70), 6, video_overlay.COLOR_CURRENT, 2), cv2.circles)
        self.assertIn(((0, 42), (200, 42), video_overlay.COLOR_RELEASE, 2), cv2.lines)
        self.assertIn(((0, 58), (200, 58), video_overlay.COLOR_RELEASE, 2), cv2.lines)
        self.assertIn(((0, 45), (200, 45), video_overlay.COLOR_DIRECTION, 1), cv2.lines)
        self.assertIn(((0, 55), (200, 55), video_overlay.COLOR_DIRECTION, 1), cv2.lines)
        self.assertIn(((100, 50), (120, 70), video_overlay.COLOR_ACTIVE, 2), cv2.lines)
        self.assertTrue(any(call[0] == "UP" for call in cv2.text))
        self.assertTrue(any(call[0] == "DOWN" for call in cv2.text))
        self.assertTrue(any(call[0].startswith("VOLUME_DOWN") for call in cv2.text))

    def test_volume_zones_skip_missing_anchor(self) -> None:
        cv2 = FakeCv2()
        original_cv2 = video_overlay.cv2
        video_overlay.cv2 = cv2
        try:
            video_overlay.draw_volume_zones(
                FakeFrame(100, 200),
                VolumeDebug(
                    anchor=None,
                    anchor_y=None,
                    current=(0.60, 0.70),
                    active_gesture=None,
                    candidate_gesture=None,
                    phase="armed",
                    armed=True,
                    activation_distance=0.05,
                    neutral_distance=0.02,
                    threshold_ratio=0.0,
                    in_neutral=True,
                    blocked_reason=None,
                ),
                CropRect(0.0, 0.0, 1.0, 1.0),
            )
        finally:
            video_overlay.cv2 = original_cv2

        self.assertEqual(cv2.circles, [])
        self.assertEqual(cv2.lines, [])
        self.assertEqual(cv2.text, [])


class FakeFrame:
    def __init__(self, height: int, width: int) -> None:
        self.shape = (height, width, 3)


class FakeCv2:
    FONT_HERSHEY_SIMPLEX = 0

    def __init__(self) -> None:
        self.circles = []
        self.lines = []
        self.text = []

    def circle(self, frame, point, radius, color, thickness) -> None:
        del frame
        self.circles.append((point, radius, color, thickness))

    def line(self, frame, start, end, color, thickness) -> None:
        del frame
        self.lines.append((start, end, color, thickness))

    def putText(self, frame, text, position, font, scale, color, thickness) -> None:
        del frame, font, scale, color, thickness
        self.text.append((text, position))


if __name__ == "__main__":
    unittest.main()
