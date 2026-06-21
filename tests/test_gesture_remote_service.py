import asyncio
import sys
import time
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.domain.constants import (
    TV_COMMAND_DPAD_DOWN,
    TV_COMMAND_HOME,
    TV_COMMAND_VOLUME_DOWN,
    TV_COMMAND_VOLUME_UP,
)
from src.domain.session_types import GestureDecision
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
    CONFIG_RELOAD_INTERVAL_SECONDS,
    GestureRemoteService,
)
from src.services.pipeline_metrics import PipelineMetrics  # noqa: E402
from src.services.pipelines import (  # noqa: E402
    CommandDispatchPipeline,
    DisplayPipeline,
    FrameCapturePipeline,
    GestureDecisionPipeline,
)
from src.services.remote_command_dispatcher import (  # noqa: E402
    MAX_PENDING_COMMANDS,
    RemoteCommandDispatcher,
)
from src.shared.config import AppConfig  # noqa: E402
from tests.config_helpers import app_config  # noqa: E402


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
        self.conditional_update_with = None

    def update(self, landmarks_by_hand, crop):
        self.updated_with = (landmarks_by_hand, crop)
        return True

    def update_if_current_crop_needs_landmarks(self, landmarks_by_hand, crop):
        self.conditional_update_with = (landmarks_by_hand, crop)
        return True

    def current_crop(self) -> CropRect:
        return CropRect(0.25, 0.25, 0.5, 0.5)


class GestureRemoteServiceTests(unittest.TestCase):
    def test_detection_frame_uses_fixed_camera_zoom(self) -> None:
        frame = FakeFrame(6, 8)

        detection_frame = FrameCapturePipeline().detection_frame(frame, 2.0)

        self.assertEqual(detection_frame.frame.shape, frame.shape)
        self.assertEqual(detection_frame.crop, CropRect(0.25, 1 / 6, 0.5, 0.5))

    def test_update_zoom_uses_filtered_zoom_landmarks(self) -> None:
        zoom_controller = FakeZoomController()
        landmarks = [_landmark(0.25, 0.50), _landmark(0.75, 1.00)]

        changed = GestureDecisionPipeline(
            FakeDecisionSession(),
            zoom_controller,
        ).update_zoom(
            GestureDecision(
                command_gesture=None,
                activated=True,
                debug_message="",
                zoom_landmarks=[landmarks],
            )
        )

        self.assertTrue(changed)
        self.assertEqual(
            zoom_controller.updated_with,
            ([landmarks], CropRect(0.0, 0.0, 1.0, 1.0)),
        )

    def test_update_zoom_holds_crop_during_temporary_primary_loss(self) -> None:
        zoom_controller = FakeZoomController()

        changed = GestureDecisionPipeline(
            FakeDecisionSession(),
            zoom_controller,
        ).update_zoom(
            GestureDecision(
                command_gesture=None,
                activated=True,
                debug_message="",
                primary_temporarily_lost=True,
            )
        )

        self.assertFalse(changed)
        self.assertIsNone(zoom_controller.updated_with)

    def test_update_zoom_conditionally_frames_hands_when_motion_freezes_zoom(self) -> None:
        zoom_controller = FakeZoomController()
        landmarks = [_landmark(0.25, 0.50)]

        changed = GestureDecisionPipeline(
            FakeDecisionSession(),
            zoom_controller,
        ).update_zoom(
            GestureDecision(
                command_gesture=None,
                activated=True,
                debug_message="",
                freeze_zoom=True,
                zoom_landmarks=[landmarks],
            )
        )

        self.assertTrue(changed)
        self.assertIsNone(zoom_controller.updated_with)
        self.assertEqual(
            zoom_controller.conditional_update_with,
            ([landmarks], CropRect(0.0, 0.0, 1.0, 1.0)),
        )

    def test_debug_message_includes_detection_and_display_crops(self) -> None:
        debug_message = DisplayPipeline(FakeLogger()).debug_message(
            "hands=2 activated=True",
            CropRect(0.0, 0.0, 1.0, 1.0),
            CropRect(0.25, 0.25, 0.5, 0.5),
            zoom_frozen=True,
        )

        self.assertEqual(
            debug_message,
            (
                "hands=2 activated=True "
                "detection_crop=(0.00,0.00,1.00,1.00) "
                "display_crop=(0.25,0.25,0.50,0.50) "
                "zoom_frozen=True"
            ),
        )


class GestureRemoteDecisionTests(unittest.IsolatedAsyncioTestCase):
    async def test_activated_empty_decision_does_not_clear_last_command(self) -> None:
        gesture_session = FakeGestureSession()
        pipeline = CommandDispatchPipeline(
            gesture_session,
            FakeVoiceCapture(),
            FakeCommandDispatcher(),
            None,
            FakeLogger(),
        )

        voice_task = await pipeline.handle_decision(
            command_gesture=None,
            activated=True,
            now=1.0,
            voice_task=None,
        )

        self.assertIsNone(voice_task)
        self.assertFalse(gesture_session.idle_recorded)


class PipelineMetricsTests(unittest.TestCase):
    def test_dispatch_snapshot_includes_dropped_commands(self) -> None:
        metrics = PipelineMetrics("roku")

        metrics.record_dispatch(
            queue_depth=3,
            send_latency_seconds=0.125,
            dropped_commands=2,
        )

        snapshot = metrics.snapshot()
        self.assertEqual(snapshot.dispatch_queue_depth, 3)
        self.assertEqual(snapshot.command_send_latency_ms, 125.0)
        self.assertEqual(snapshot.dropped_commands, 2)


class GestureRemoteConfigReloadTests(unittest.TestCase):
    def test_reload_config_applies_live_fields_to_runtime_collaborators(self) -> None:
        initial_config = app_config(
            tv_host="10.0.0.10",
            webcam_index=0,
            camera_zoom=1.0,
            debug_log_seconds=0.5,
        )
        latest_config = app_config(
            tv_host="10.0.0.20",
            webcam_index=2,
            camera_zoom=2.0,
            debug_log_seconds=0.1,
        )
        service = GestureRemoteService.__new__(GestureRemoteService)
        service._config = initial_config
        service._config_provider = lambda: latest_config
        service._last_config_reload_time = -CONFIG_RELOAD_INTERVAL_SECONDS
        service._logger = FakeLogger()
        service._gesture_session = FakeReloadableConfig()
        service._voice_capture = FakeReloadableConfig()
        zoom_controller = FakeReloadableConfig()
        hand_tracker = FakeReloadableConfig()

        service._reload_config_if_needed(
            now=CONFIG_RELOAD_INTERVAL_SECONDS,
            zoom_controller=zoom_controller,
            hand_tracker=hand_tracker,
        )

        self.assertEqual(service._config.tv.host, "10.0.0.10")
        self.assertEqual(service._config.camera.webcam_index, 0)
        self.assertEqual(service._config.camera.zoom, 2.0)
        self.assertEqual(service._config.debug.log_seconds, 0.1)
        self.assertEqual(service._gesture_session.config, service._config)
        self.assertEqual(service._voice_capture.config, service._config)
        self.assertEqual(zoom_controller.config, service._config)
        self.assertEqual(hand_tracker.config, service._config)
        self.assertIn("Reloaded live config settings.", service._logger.messages)

    def test_reload_config_is_throttled(self) -> None:
        service = GestureRemoteService.__new__(GestureRemoteService)
        service._config = app_config()
        service._config_provider = ProviderCounter(app_config())
        service._last_config_reload_time = 10.0

        service._reload_config_if_needed(
            now=10.0 + CONFIG_RELOAD_INTERVAL_SECONDS - 0.01,
            zoom_controller=FakeReloadableConfig(),
            hand_tracker=FakeReloadableConfig(),
        )

        self.assertEqual(service._config_provider.calls, 0)


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
    async def test_commands_queue_while_remote_is_busy(self) -> None:
        remote = BlockingRemote()
        dispatcher = RemoteCommandDispatcher(remote, FakeLogger())
        dispatcher.start()

        dispatcher.enqueue("VOLUME_UP", TV_COMMAND_VOLUME_UP)
        await asyncio.wait_for(remote.first_started.wait(), timeout=1.0)

        dispatcher.enqueue("VOLUME_DOWN", TV_COMMAND_VOLUME_DOWN)

        self.assertEqual(remote.commands, [TV_COMMAND_VOLUME_UP])

        remote.release_first.set()
        await asyncio.wait_for(remote.second_started.wait(), timeout=1.0)

        self.assertEqual(
            remote.commands,
            [TV_COMMAND_VOLUME_UP, TV_COMMAND_VOLUME_DOWN],
        )
        await dispatcher.close()

    async def test_commands_queue_in_order(self) -> None:
        remote = BlockingRemote()
        dispatcher = RemoteCommandDispatcher(remote, FakeLogger())
        dispatcher.start()

        dispatcher.enqueue("VOLUME_UP", TV_COMMAND_VOLUME_UP)
        await asyncio.wait_for(remote.first_started.wait(), timeout=1.0)

        dispatcher.enqueue("HOME", TV_COMMAND_HOME)

        remote.release_first.set()
        await asyncio.wait_for(remote.second_started.wait(), timeout=1.0)

        self.assertEqual(remote.commands, [TV_COMMAND_VOLUME_UP, TV_COMMAND_HOME])
        await dispatcher.close()

    async def test_dpad_commands_queue_in_order(self) -> None:
        remote = BlockingRemote()
        dispatcher = RemoteCommandDispatcher(remote, FakeLogger())
        dispatcher.start()

        dispatcher.enqueue("POINT_DOWN", TV_COMMAND_DPAD_DOWN)
        await asyncio.wait_for(remote.first_started.wait(), timeout=1.0)

        dispatcher.enqueue("POINT_DOWN", TV_COMMAND_DPAD_DOWN)

        remote.release_first.set()
        await asyncio.wait_for(remote.second_started.wait(), timeout=1.0)

        self.assertEqual(
            remote.commands,
            [TV_COMMAND_DPAD_DOWN, TV_COMMAND_DPAD_DOWN],
        )
        await dispatcher.close()

    async def test_queue_overflow_drops_oldest_pending_command(self) -> None:
        remote = BlockingRemote()
        dispatcher = RemoteCommandDispatcher(remote, FakeLogger())
        dispatcher.start()

        dispatcher.enqueue("VOLUME_UP", TV_COMMAND_VOLUME_UP)
        await asyncio.wait_for(remote.first_started.wait(), timeout=1.0)
        for index in range(MAX_PENDING_COMMANDS):
            dispatcher.enqueue(f"HOME_{index}", TV_COMMAND_HOME)

        dispatcher.enqueue("VOLUME_DOWN", TV_COMMAND_VOLUME_DOWN)

        self.assertEqual(dispatcher.queue_depth, MAX_PENDING_COMMANDS)
        self.assertEqual(dispatcher.dropped_commands, 1)

        remote.release_first.set()
        await dispatcher.close()

    async def test_queue_overflow_replaces_newest_duplicate_without_drop_count(self) -> None:
        remote = BlockingRemote()
        dispatcher = RemoteCommandDispatcher(remote, FakeLogger())
        dispatcher.start()

        dispatcher.enqueue("VOLUME_UP", TV_COMMAND_VOLUME_UP)
        await asyncio.wait_for(remote.first_started.wait(), timeout=1.0)
        for index in range(MAX_PENDING_COMMANDS):
            dispatcher.enqueue(f"HOME_{index}", TV_COMMAND_HOME)

        dispatcher.enqueue("HOME_NEWER", TV_COMMAND_HOME)

        self.assertEqual(dispatcher.queue_depth, MAX_PENDING_COMMANDS)
        self.assertEqual(dispatcher.dropped_commands, 0)

        remote.release_first.set()
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


class FakeReloadableConfig:
    def __init__(self) -> None:
        self.config = None

    def update_config(self, config: AppConfig) -> None:
        self.config = config


class ProviderCounter:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.calls = 0

    def __call__(self) -> AppConfig:
        self.calls += 1
        return self.config


class FakeGestureSession:
    def __init__(self) -> None:
        self.idle_recorded = False

    def record_idle(self) -> None:
        self.idle_recorded = True

    def should_emit(self, command_gesture, command, now) -> bool:
        return True

    def record_emit(self, command_gesture, now) -> None:
        pass


class FakeDecisionSession:
    def evaluate(self, hand_states, now):
        return GestureDecision(None, False, "")


class FakeVoiceCapture:
    async def capture(self) -> None:
        pass


class FakeCommandDispatcher:
    queue_depth = 0
    last_send_latency_seconds = None
    dropped_commands = 0

    def enqueue(self, gesture, command) -> None:
        pass


def _landmark(x: float, y: float):
    return SimpleNamespace(x=x, y=y)


if __name__ == "__main__":
    unittest.main()
