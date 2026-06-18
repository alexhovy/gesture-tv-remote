import sys
import types
import unittest
from types import SimpleNamespace

from src.infrastructure.camera.video_preprocessing import CropRect


def _install_service_import_stubs() -> None:
    cv2 = types.ModuleType("cv2")
    cv2.COLOR_BGR2RGB = 1
    cv2.cvtColor = lambda frame, code: frame
    cv2.flip = lambda frame, flip_code: frame
    cv2.INTER_LINEAR = 1
    cv2.resize = lambda frame, size, interpolation=None: FakeResizedFrame(frame, size)
    cv2.line = lambda *args, **kwargs: None
    cv2.circle = lambda *args, **kwargs: None
    cv2.imshow = lambda *args, **kwargs: None
    cv2.waitKey = lambda delay: 0
    cv2.destroyAllWindows = lambda: None
    sys.modules.setdefault("cv2", cv2)

    hand_tracking = types.ModuleType("src.infrastructure.hand_tracking.hand_tracking")
    hand_tracking.DetectedHand = object
    hand_tracking.MediaPipeHandTracker = object
    sys.modules.setdefault("src.infrastructure.hand_tracking.hand_tracking", hand_tracking)


_install_service_import_stubs()

from src.services.gesture_remote_service import GestureRemoteService  # noqa: E402


class FakeFrame:
    def __init__(
        self,
        height: int,
        width: int,
        crop: tuple[slice, slice] | None = None,
    ) -> None:
        self.shape = (height, width, 3)
        self.crop = crop

    def __getitem__(self, key):
        y_slice, x_slice = key
        return FakeFrame(
            y_slice.stop - y_slice.start,
            x_slice.stop - x_slice.start,
            crop=(y_slice, x_slice),
        )


class FakeResizedFrame:
    def __init__(self, source: FakeFrame, size: tuple[int, int]) -> None:
        width, height = size
        self.shape = (height, width, 3)
        self.source_crop = source.crop


class FakeZoomController:
    def __init__(self) -> None:
        self.updated_with = None

    def update(self, landmarks_by_hand, crop):
        self.updated_with = (landmarks_by_hand, crop)
        return True

    def current_crop(self) -> CropRect:
        return CropRect(0.25, 0.25, 0.5, 0.5)


class GestureRemoteServiceTests(unittest.TestCase):
    def test_detection_frame_uses_fixed_camera_zoom(self) -> None:
        frame = FakeFrame(6, 8)

        detection_frame = GestureRemoteService._detection_frame(frame, 2.0)

        self.assertEqual(detection_frame.frame.shape, frame.shape)
        self.assertEqual(detection_frame.crop, CropRect(0.25, 1 / 6, 0.5, 0.5))

    def test_update_zoom_uses_filtered_zoom_landmarks(self) -> None:
        zoom_controller = FakeZoomController()
        landmarks = [_landmark(0.25, 0.50), _landmark(0.75, 1.00)]

        changed = GestureRemoteService._update_zoom(
            GestureRemoteService.__new__(GestureRemoteService),
            zoom_controller,
            [landmarks],
            activated=True,
            primary_temporarily_lost=False,
        )

        self.assertTrue(changed)
        self.assertEqual(
            zoom_controller.updated_with,
            ([landmarks], CropRect(0.0, 0.0, 1.0, 1.0)),
        )

    def test_update_zoom_holds_crop_during_temporary_primary_loss(self) -> None:
        zoom_controller = FakeZoomController()

        changed = GestureRemoteService._update_zoom(
            GestureRemoteService.__new__(GestureRemoteService),
            zoom_controller,
            [],
            activated=True,
            primary_temporarily_lost=True,
        )

        self.assertFalse(changed)
        self.assertIsNone(zoom_controller.updated_with)

def _landmark(x: float, y: float):
    return SimpleNamespace(x=x, y=y)


if __name__ == "__main__":
    unittest.main()
