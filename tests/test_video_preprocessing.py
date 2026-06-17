import unittest
from types import SimpleNamespace

from src.infrastructure.video_preprocessing import (
    CameraZoomController,
    CropRect,
    apply_center_crop_zoom,
    apply_crop,
    landmarks_to_original_bounds,
)
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


class ResizedFrame:
    def __init__(self, source: FakeFrame, size: tuple[int, int]) -> None:
        width, height = size
        self.shape = (height, width, 3)
        self.source_crop = source.crop


def _fake_resize(frame: FakeFrame, size: tuple[int, int]) -> ResizedFrame:
    return ResizedFrame(frame, size)


def _landmark(x: float, y: float):
    return SimpleNamespace(x=x, y=y)


if __name__ == "__main__":
    unittest.main()
