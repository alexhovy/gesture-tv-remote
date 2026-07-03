import json
import unittest
from types import SimpleNamespace

from src.application.ports.hand_tracker import DetectedHand
from src.domain.geometry.camera_geometry import CropRect
from src.domain.session.session_types import PointerDebug
from src.infrastructure.camera.browser_debug_display import BrowserDebugDisplay
from src.infrastructure.web.debug_stream import BrowserDebugStream


class BrowserDebugDisplayTests(unittest.TestCase):
    def test_render_publishes_landmarks_and_pointer_debug_snapshot(self) -> None:
        stream = BrowserDebugStream()
        display = BrowserDebugDisplay(stream)
        landmarks = [_landmark(0.1, 0.2), _landmark(0.3, 0.4)]

        display.debug_message(
            "active",
            CropRect(0.0, 0.0, 1.0, 1.0),
            CropRect(0.0, 0.0, 1.0, 1.0),
            zoom_frozen=True,
        )
        display.draw_detected_hands(
            object(),
            [DetectedHand(landmarks=landmarks, handedness="Right")],
            CropRect(0.0, 0.0, 1.0, 1.0),
            CropRect(0.0, 0.0, 1.0, 1.0),
        )
        display.draw_pointer_zones(
            object(),
            PointerDebug(
                anchor=(0.5, 0.5),
                current=(0.7, 0.5),
                active_gesture="POINT_RIGHT",
                candidate_gesture="POINT_RIGHT",
                phase="triggered",
                armed=False,
                activation_distance=0.1,
                neutral_distance=0.05,
                threshold_ratio=2.0,
                in_neutral=False,
                blocked_reason="holding",
            ),
            CropRect(0.0, 0.0, 1.0, 1.0),
        )
        display.draw_volume_zones(object(), None, CropRect(0.0, 0.0, 1.0, 1.0))

        display.render("app", object())

        snapshot = json.loads(stream._latest)
        self.assertEqual(snapshot["debugMessage"], "active")
        self.assertTrue(snapshot["zoomFrozen"])
        self.assertEqual(snapshot["hands"][0][0], {"x": 0.1, "y": 0.2})
        self.assertEqual(snapshot["pointer"]["activeGesture"], "POINT_RIGHT")
        self.assertIsNone(snapshot["volume"])

    def test_landmarks_use_display_crop_space_but_pointer_stays_original_space(
        self,
    ) -> None:
        stream = BrowserDebugStream()
        display = BrowserDebugDisplay(stream)

        display.debug_message(
            "active",
            CropRect(0.0, 0.0, 1.0, 1.0),
            CropRect(0.25, 0.25, 0.5, 0.5),
        )
        display.draw_detected_hands(
            object(),
            [DetectedHand(landmarks=[_landmark(0.75, 0.50)], handedness="Right")],
            CropRect(0.0, 0.0, 1.0, 1.0),
            CropRect(0.25, 0.25, 0.5, 0.5),
        )
        display.draw_pointer_zones(
            object(),
            PointerDebug(
                anchor=(0.75, 0.50),
                current=(0.80, 0.50),
                active_gesture=None,
                candidate_gesture="POINT_RIGHT",
                phase="armed",
                armed=True,
                activation_distance=0.1,
                neutral_distance=0.05,
                threshold_ratio=2.0,
                in_neutral=False,
                blocked_reason=None,
            ),
            CropRect(0.25, 0.25, 0.5, 0.5),
        )
        display.draw_volume_zones(object(), None, CropRect(0.25, 0.25, 0.5, 0.5))

        display.render("app", object())

        snapshot = json.loads(stream._latest)
        self.assertEqual(snapshot["displayCrop"]["x"], 0.25)
        self.assertEqual(snapshot["hands"][0][0], {"x": 1.0, "y": 0.5})
        self.assertEqual(snapshot["pointer"]["anchor"], {"x": 0.75, "y": 0.5})


def _landmark(x: float, y: float) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y)


if __name__ == "__main__":
    unittest.main()
