import threading
import unittest
from types import SimpleNamespace

from src.infrastructure.camera.camera_zoom import CameraZoomController
from src.infrastructure.camera.frame_source import LatestFrameSource
from src.infrastructure.camera.landmark_projection import (
    hand_state_to_original_space,
    landmarks_to_crop_space,
    landmarks_to_original_bounds,
)
from src.infrastructure.camera.video_preprocessing import (
    CropRect,
    apply_center_crop_zoom,
    apply_crop,
)
from src.domain.constants import GESTURE_POINT
from src.domain.session_types import HandState
from src.shared.config import AppConfig


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


class VideoPreprocessingTests(unittest.TestCase):
    def test_zoom_one_returns_original_frame(self) -> None:
        frame = FakeFrame(4, 6)

        self.assertIs(apply_center_crop_zoom(frame, 1.0), frame)

    def test_latest_frame_source_keeps_newest_frame(self) -> None:
        first_frame = FakeFrame(4, 6)
        second_frame = FakeFrame(5, 7)
        capture = FakeCapture([first_frame, second_frame])
        source = LatestFrameSource(capture)

        source.start()
        self.assertTrue(capture.finished.wait(timeout=1.0))
        source.stop()

        self.assertIs(source.latest(), second_frame)
        self.assertTrue(source.failed())

    def test_center_crop_zoom_preserves_frame_dimensions(self) -> None:
        frame = FakeFrame(6, 8)

        zoomed = apply_center_crop_zoom(frame, 2.0, resize=_fake_resize)

        self.assertEqual(zoomed.shape, frame.shape)

    def test_center_crop_zoom_uses_center_region(self) -> None:
        frame = FakeFrame(6, 8)

        zoomed = apply_center_crop_zoom(frame, 2.0, resize=_fake_resize)

        self.assertEqual(zoomed.source_crop, (slice(1, 4), slice(2, 6)))

    def test_apply_crop_returns_effective_crop(self) -> None:
        frame = FakeFrame(6, 8)

        cropped = apply_crop(frame, CropRect(0.25, 0.25, 0.5, 0.5), _fake_resize)

        self.assertEqual(cropped.frame.shape, frame.shape)
        self.assertEqual(cropped.crop, CropRect(0.25, 1 / 6, 0.5, 0.5))

    def test_landmarks_to_original_bounds_maps_from_crop_coordinates(self) -> None:
        bounds = landmarks_to_original_bounds(
            [_landmark(0.25, 0.50), _landmark(0.75, 1.00)],
            CropRect(0.20, 0.10, 0.50, 0.40),
        )

        self.assertAlmostEqual(bounds.x, 0.325)
        self.assertAlmostEqual(bounds.y, 0.30)
        self.assertAlmostEqual(bounds.width, 0.25)
        self.assertAlmostEqual(bounds.height, 0.20)

    def test_landmarks_to_crop_space_maps_original_coordinates(self) -> None:
        mapped = landmarks_to_crop_space(
            [_landmark(0.50, 0.75)],
            CropRect(0.25, 0.25, 0.50, 0.50),
        )

        self.assertAlmostEqual(mapped[0].x, 0.50)
        self.assertAlmostEqual(mapped[0].y, 1.00)

    def test_landmarks_to_crop_space_preserves_extra_attributes(self) -> None:
        landmark = SimpleNamespace(x=0.50, y=0.75, z=0.20, visibility=0.80)

        mapped = landmarks_to_crop_space(
            [landmark],
            CropRect(0.25, 0.25, 0.50, 0.50),
        )

        self.assertEqual(mapped[0].z, 0.20)
        self.assertEqual(mapped[0].visibility, 0.80)

    def test_hand_state_to_original_space_maps_coordinates_and_size(self) -> None:
        hand_state = HandState(
            landmarks=[_landmark(0.25, 0.50), _landmark(0.75, 1.00)],
            gesture=GESTURE_POINT,
            center=(0.50, 0.75),
            size=0.50,
            upright=False,
        )

        mapped = hand_state_to_original_space(
            hand_state,
            CropRect(0.20, 0.10, 0.50, 0.40),
        )

        self.assertEqual(mapped.gesture, GESTURE_POINT)
        self.assertAlmostEqual(mapped.landmarks[0].x, 0.325)
        self.assertAlmostEqual(mapped.landmarks[0].y, 0.30)
        self.assertAlmostEqual(mapped.landmarks[1].x, 0.575)
        self.assertAlmostEqual(mapped.landmarks[1].y, 0.50)
        self.assertAlmostEqual(mapped.center[0], 0.45)
        self.assertAlmostEqual(mapped.center[1], 0.40)
        self.assertAlmostEqual(mapped.size, 0.25)
        self.assertFalse(mapped.upright)

    def test_auto_zoom_follows_detected_hand(self) -> None:
        controller = CameraZoomController(
            AppConfig(
                auto_zoom_enabled=True,
                auto_zoom_min=1.0,
                auto_zoom_max=2.0,
                auto_zoom_smoothing=1.0,
            )
        )

        controller.update(
            [[_landmark(0.70, 0.40), _landmark(0.80, 0.60)]],
            CropRect(0.0, 0.0, 1.0, 1.0),
        )

        self.assertEqual(controller.current_crop(), CropRect(0.5, 0.25, 0.5, 0.5))

    def test_auto_zoom_zooms_out_for_two_hand_bounds(self) -> None:
        controller = CameraZoomController(
            AppConfig(
                auto_zoom_enabled=True,
                auto_zoom_min=1.0,
                auto_zoom_max=3.0,
                auto_zoom_padding=0.0,
                auto_zoom_smoothing=1.0,
            )
        )

        controller.update(
            [
                [_landmark(0.10, 0.40), _landmark(0.20, 0.60)],
                [_landmark(0.80, 0.40), _landmark(0.90, 0.60)],
            ],
            CropRect(0.0, 0.0, 1.0, 1.0),
        )

        self.assertEqual(
            controller.current_crop(),
            CropRect(0.09999999999999998, 0.09999999999999998, 0.8, 0.8),
        )

    def test_auto_zoom_returns_to_center_when_hands_disappear(self) -> None:
        controller = CameraZoomController(
            AppConfig(
                auto_zoom_enabled=True,
                auto_zoom_min=1.0,
                auto_zoom_max=2.0,
                auto_zoom_smoothing=1.0,
            )
        )
        controller.update(
            [[_landmark(0.70, 0.40), _landmark(0.80, 0.60)]],
            CropRect(0.0, 0.0, 1.0, 1.0),
        )

        controller.update([], CropRect(0.5, 0.0, 0.5, 0.5))

        self.assertEqual(controller.current_crop(), CropRect(0.0, 0.0, 1.0, 1.0))

    def test_auto_zoom_reset_returns_to_default_crop(self) -> None:
        controller = CameraZoomController(
            AppConfig(
                auto_zoom_enabled=True,
                auto_zoom_min=1.0,
                auto_zoom_max=2.0,
                auto_zoom_smoothing=1.0,
            )
        )
        controller.update(
            [[_landmark(0.70, 0.40), _landmark(0.80, 0.60)]],
            CropRect(0.0, 0.0, 1.0, 1.0),
        )

        controller.reset()

        self.assertEqual(controller.current_crop(), CropRect(0.0, 0.0, 1.0, 1.0))

    def test_auto_zoom_ignores_small_target_changes_inside_deadband(self) -> None:
        controller = CameraZoomController(
            AppConfig(
                auto_zoom_enabled=True,
                auto_zoom_min=1.0,
                auto_zoom_max=5.0,
                auto_zoom_padding=0.0,
                auto_zoom_smoothing=1.0,
                auto_zoom_position_deadband=0.05,
                auto_zoom_scale_deadband=0.20,
            )
        )

        changed = controller.update(
            [[_landmark(0.08, 0.08), _landmark(0.92, 0.92)]],
            CropRect(0.0, 0.0, 1.0, 1.0),
        )

        self.assertFalse(changed)
        self.assertEqual(controller.current_crop(), CropRect(0.0, 0.0, 1.0, 1.0))

    def test_auto_zoom_still_follows_hand_near_crop_edge(self) -> None:
        controller = CameraZoomController(
            AppConfig(
                auto_zoom_enabled=True,
                auto_zoom_min=1.0,
                auto_zoom_max=2.0,
                auto_zoom_padding=0.0,
                auto_zoom_smoothing=1.0,
                auto_zoom_position_deadband=0.10,
                auto_zoom_scale_deadband=0.20,
            )
        )

        changed = controller.update(
            [[_landmark(0.02, 0.40), _landmark(0.12, 0.60)]],
            CropRect(0.0, 0.0, 1.0, 1.0),
        )

        self.assertTrue(changed)
        self.assertNotEqual(controller.current_crop(), CropRect(0.0, 0.0, 1.0, 1.0))

    def test_auto_zoom_zooms_out_when_hand_reaches_cropped_edge(self) -> None:
        controller = CameraZoomController(
            AppConfig(
                auto_zoom_enabled=True,
                auto_zoom_min=1.0,
                auto_zoom_max=4.0,
                auto_zoom_padding=0.0,
                auto_zoom_smoothing=1.0,
                auto_zoom_position_deadband=0.10,
                auto_zoom_scale_deadband=0.20,
            )
        )
        controller.update(
            [[_landmark(0.40, 0.40), _landmark(0.60, 0.60)]],
            CropRect(0.0, 0.0, 1.0, 1.0),
        )
        cropped = controller.current_crop()

        changed = controller.update(
            [[_landmark(0.90, 0.40), _landmark(0.98, 0.60)]],
            cropped,
        )

        self.assertTrue(changed)
        self.assertEqual(controller.current_crop(), CropRect(0.0, 0.0, 1.0, 1.0))


class ResizedFrame:
    def __init__(self, source: FakeFrame, size: tuple[int, int]) -> None:
        width, height = size
        self.shape = (height, width, 3)
        self.source_crop = source.crop


class FakeCapture:
    def __init__(self, frames: list[FakeFrame]) -> None:
        self._frames = frames
        self.finished = threading.Event()

    def read(self):
        if self._frames:
            return True, self._frames.pop(0)
        self.finished.set()
        return False, None


def _fake_resize(frame: FakeFrame, size: tuple[int, int]) -> ResizedFrame:
    return ResizedFrame(frame, size)


def _landmark(x: float, y: float):
    return SimpleNamespace(x=x, y=y)


if __name__ == "__main__":
    unittest.main()
