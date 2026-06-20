import asyncio
import sys
import time
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.domain.constants import (
    TV_COMMAND_HOME,
    TV_COMMAND_VOLUME_DOWN,
    TV_COMMAND_VOLUME_UP,
)
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
    cv2.pollKey = lambda: 0
    cv2.destroyAllWindows = lambda: None
    sys.modules.setdefault("cv2", cv2)

    hand_tracking = types.ModuleType("src.infrastructure.hand_tracking.hand_tracking")
    hand_tracking.DetectedHand = object
    hand_tracking.MediaPipeHandTracker = object
    sys.modules.setdefault("src.infrastructure.hand_tracking.hand_tracking", hand_tracking)


_install_service_import_stubs()

from src.services.gesture_remote_service import (  # noqa: E402
    GestureRemoteService,
    RemoteCommandDispatcher,
)


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

    def test_debug_message_includes_detection_and_display_crops(self) -> None:
        debug_message = GestureRemoteService._debug_message(
            "hands=2 activated=True",
            CropRect(0.0, 0.0, 1.0, 1.0),
            CropRect(0.25, 0.25, 0.5, 0.5),
        )

        self.assertEqual(
            debug_message,
            (
                "hands=2 activated=True "
                "detection_crop=(0.00,0.00,1.00,1.00) "
                "display_crop=(0.25,0.25,0.50,0.50)"
            ),
        )


class GestureRemoteCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_cleanup_timeout_does_not_wait_for_blocked_method(self) -> None:
        service = GestureRemoteService.__new__(GestureRemoteService)
        service._logger = FakeLogger()

        def blocked_cleanup() -> None:
            time.sleep(10.0)

        with patch(
            "src.services.gesture_remote_service.CLEANUP_TIMEOUT_SECONDS",
            0.01,
        ):
            started = time.monotonic()
            await service._cleanup_sync_step("blocked cleanup", blocked_cleanup)
            elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.5)
        self.assertIn(
            "Timed out while cleaning up blocked cleanup.",
            service._logger.messages,
        )


class RemoteCommandDispatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeatable_commands_coalesce_while_remote_is_busy(self) -> None:
        remote = BlockingRemote()
        dispatcher = RemoteCommandDispatcher(remote, FakeLogger())
        dispatcher.start()

        dispatcher.enqueue("VOLUME_UP", TV_COMMAND_VOLUME_UP)
        await asyncio.wait_for(remote.first_started.wait(), timeout=1.0)

        dispatcher.enqueue("VOLUME_UP", TV_COMMAND_VOLUME_UP)
        dispatcher.enqueue("VOLUME_DOWN", TV_COMMAND_VOLUME_DOWN)

        self.assertEqual(remote.commands, [TV_COMMAND_VOLUME_UP])

        remote.release_first.set()
        await asyncio.wait_for(remote.second_started.wait(), timeout=1.0)

        self.assertEqual(
            remote.commands,
            [TV_COMMAND_VOLUME_UP, TV_COMMAND_VOLUME_DOWN],
        )
        await dispatcher.close()

    async def test_nonrepeatable_command_replaces_stale_repeatable_command(self) -> None:
        remote = BlockingRemote()
        dispatcher = RemoteCommandDispatcher(remote, FakeLogger())
        dispatcher.start()

        dispatcher.enqueue("VOLUME_UP", TV_COMMAND_VOLUME_UP)
        await asyncio.wait_for(remote.first_started.wait(), timeout=1.0)

        dispatcher.enqueue("VOLUME_DOWN", TV_COMMAND_VOLUME_DOWN)
        dispatcher.enqueue("HOME", TV_COMMAND_HOME)

        remote.release_first.set()
        await asyncio.wait_for(remote.second_started.wait(), timeout=1.0)

        self.assertEqual(remote.commands, [TV_COMMAND_VOLUME_UP, TV_COMMAND_HOME])
        await dispatcher.close()


class BlockingRemote:
    def __init__(self) -> None:
        self.commands = []
        self.first_started = asyncio.Event()
        self.second_started = asyncio.Event()
        self.release_first = asyncio.Event()

    async def send_key_command(self, command: str) -> None:
        self.commands.append(command)
        if len(self.commands) == 1:
            self.first_started.set()
            await self.release_first.wait()
        elif len(self.commands) == 2:
            self.second_started.set()


class FakeLogger:
    def __init__(self) -> None:
        self.messages = []

    def info(self, message: str) -> None:
        self.messages.append(message)

    def error(self, message: str) -> None:
        self.messages.append(message)


def _landmark(x: float, y: float):
    return SimpleNamespace(x=x, y=y)


if __name__ == "__main__":
    unittest.main()
