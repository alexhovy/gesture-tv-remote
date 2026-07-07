import asyncio
import sys
import time
import types
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from src.domain.constants import (
    GESTURE_MIC,
    TV_COMMAND_DPAD_DOWN,
    TV_COMMAND_HOME,
    TV_COMMAND_POWER_TOGGLE,
    TV_COMMAND_VOLUME_DOWN,
    TV_COMMAND_VOLUME_UP,
)
from src.domain.geometry.camera_geometry import CropRect
from src.domain.session.session_types import GestureDecision


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
    sys.modules.setdefault(
        "src.infrastructure.hand_tracking.hand_tracking", hand_tracking
    )


_install_service_import_stubs()

import src.infrastructure.camera.display as display_module  # noqa: E402
from src.application.pipelines import (  # noqa: E402
    CommandDispatchPipeline,
    FrameCapturePipeline,
    GestureDecisionPipeline,
)
from src.application.ports.display_metrics import DisplaySize  # noqa: E402
from src.application.ports.tv_remote import (  # noqa: E402
    AppVoiceInputRequest,
    CapabilityStatus,
    TvAdapterCapabilities,
    VoiceInputCapabilities,
)
from src.application.services.coordinators.cleanup import (  # noqa: E402
    CleanupCoordinator,
)
from src.application.services.coordinators.config_reload import (  # noqa: E402
    CONFIG_RELOAD_INTERVAL_SECONDS,
    ConfigReloadCoordinator,
)
from src.application.services.coordinators.display_debug import (  # noqa: E402
    DisplayDebugCoordinator,
)
from src.application.services.direct_remote_service import (  # noqa: E402
    MAX_DIRECT_REMOTE_PENDING_COMMANDS,
    DirectRemoteService,
)
from src.application.services.gesture_remote_service import (  # noqa: E402
    GestureRemoteService,
)
from src.application.services.pipeline_metrics import PipelineMetrics  # noqa: E402
from src.application.services.remote_command_dispatcher import (  # noqa: E402
    MAX_PENDING_COMMANDS,
    RemoteCommandDispatcher,
)
from src.infrastructure.camera.display import OpenCvDisplay  # noqa: E402
from src.infrastructure.camera.frame_processor import OpenCvFrameProcessor  # noqa: E402
from src.shared.config import AppConfig  # noqa: E402
from tests.helpers.config_helpers import app_config  # noqa: E402


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

    def detection_crop(self) -> CropRect:
        return CropRect(0.25, 0.25, 0.5, 0.5)


class GestureRemoteServiceTests(unittest.TestCase):
    def test_detection_frame_uses_current_zoom_crop(self) -> None:
        frame = FakeFrame(6, 8)

        detection_frame = FrameCapturePipeline(OpenCvFrameProcessor()).detection_frame(
            frame,
            FakeZoomController(),
        )

        self.assertEqual(detection_frame.frame.shape, frame.shape)
        self.assertEqual(detection_frame.crop, CropRect(0.25, 1 / 6, 0.5, 0.5))

    def test_detection_frame_uses_same_crop_api_as_display(self) -> None:
        frame = FakeFrame(6, 8)
        zoom_controller = FakeZoomController()

        detection_frame = FrameCapturePipeline(OpenCvFrameProcessor()).detection_frame(
            frame,
            zoom_controller,
        )

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

    def test_decision_pipeline_passes_display_crop_size_for_pointer_radius(
        self,
    ) -> None:
        session = FakeDecisionSession()

        GestureDecisionPipeline(
            session,
            FakeZoomController(),
        ).evaluate(
            [],
            CropRect(0.0, 0.0, 1.0, 1.0),
            CropRect(0.20, 0.30, 0.50, 0.40),
            now=0.0,
        )

        self.assertEqual(session.pointer_reference_size, 0.40)

    def test_decision_pipeline_scales_motion_from_display_metrics(self) -> None:
        session = FakeDecisionSession()

        GestureDecisionPipeline(
            session,
            FakeZoomController(),
            display_metrics=FakeDisplayMetrics(360, 720),
        ).evaluate(
            [],
            CropRect(0.0, 0.0, 1.0, 1.0),
            CropRect(0.25, 0.25, 0.50, 0.50),
            now=0.0,
        )

        self.assertEqual(session.motion_scale.x, 1.0)
        self.assertEqual(session.motion_scale.y, 2.0)

    def test_update_zoom_recovers_crop_during_temporary_active_hand_loss(self) -> None:
        zoom_controller = FakeZoomController()

        changed = GestureDecisionPipeline(
            FakeDecisionSession(),
            zoom_controller,
        ).update_zoom(
            GestureDecision(
                command_gesture=None,
                activated=True,
                debug_message="",
                active_temporarily_lost=True,
            )
        )

        self.assertTrue(changed)
        self.assertEqual(
            zoom_controller.updated_with,
            ([], CropRect(0.0, 0.0, 1.0, 1.0)),
        )

    def test_update_zoom_holds_crop_during_temporary_loss_when_motion_anchor_is_locked(
        self,
    ) -> None:
        zoom_controller = FakeZoomController()

        changed = GestureDecisionPipeline(
            FakeDecisionSession(),
            zoom_controller,
        ).update_zoom(
            GestureDecision(
                command_gesture=None,
                activated=True,
                debug_message="",
                active_temporarily_lost=True,
                anchor_locked=True,
            )
        )

        self.assertFalse(changed)
        self.assertIsNone(zoom_controller.updated_with)
        self.assertIsNone(zoom_controller.conditional_update_with)

    def test_update_zoom_holds_crop_while_motion_anchor_is_locked(self) -> None:
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
                anchor_locked=True,
                zoom_landmarks=[landmarks],
            )
        )

        self.assertFalse(changed)
        self.assertIsNone(zoom_controller.updated_with)
        self.assertIsNone(zoom_controller.conditional_update_with)

    def test_update_zoom_holds_crop_when_freeze_has_no_landmarks(self) -> None:
        zoom_controller = FakeZoomController()

        changed = GestureDecisionPipeline(
            FakeDecisionSession(),
            zoom_controller,
        ).update_zoom(
            GestureDecision(
                command_gesture=None,
                activated=True,
                debug_message="",
                active_temporarily_lost=True,
                freeze_zoom=True,
            )
        )

        self.assertFalse(changed)
        self.assertIsNone(zoom_controller.updated_with)
        self.assertIsNone(zoom_controller.conditional_update_with)

    def test_update_zoom_conditionally_frames_hands_when_motion_freezes_zoom(
        self,
    ) -> None:
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
        debug_message = OpenCvDisplay().debug_message(
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


class DisplayPipelineTests(unittest.TestCase):
    def test_detected_hand_overlay_is_smoothed_and_held_through_brief_dropout(
        self,
    ) -> None:
        drawn = []
        original_draw = display_module.draw_simple_landmarks
        display_module.draw_simple_landmarks = lambda frame, landmarks: drawn.append(
            landmarks
        )
        try:
            pipeline = OpenCvDisplay()
            frame = FakeFrame(100, 100)
            crop = CropRect(0.0, 0.0, 1.0, 1.0)

            pipeline.draw_detected_hands(
                frame,
                [
                    SimpleNamespace(
                        landmarks=[_landmark(0.20, 0.20)], handedness="Right"
                    )
                ],
                crop,
                crop,
            )
            pipeline.draw_detected_hands(
                frame,
                [
                    SimpleNamespace(
                        landmarks=[_landmark(0.60, 0.20)], handedness="Right"
                    )
                ],
                crop,
                crop,
            )
            pipeline.draw_detected_hands(frame, [], crop, crop)
        finally:
            display_module.draw_simple_landmarks = original_draw

        self.assertEqual(len(drawn), 3)
        self.assertAlmostEqual(drawn[0][0].x, 0.20)
        self.assertAlmostEqual(drawn[1][0].x, 0.38)
        self.assertAlmostEqual(drawn[2][0].x, 0.38)

    def test_detected_hand_overlay_handles_none_optional_landmark_fields(self) -> None:
        drawn = []
        original_draw = display_module.draw_simple_landmarks
        display_module.draw_simple_landmarks = lambda frame, landmarks: drawn.append(
            landmarks
        )
        try:
            pipeline = OpenCvDisplay()
            frame = FakeFrame(100, 100)
            crop = CropRect(0.0, 0.0, 1.0, 1.0)

            pipeline.draw_detected_hands(
                frame,
                [
                    SimpleNamespace(
                        landmarks=[_landmark(0.20, 0.20, z=None, visibility=None)],
                        handedness="Right",
                    )
                ],
                crop,
                crop,
            )
            pipeline.draw_detected_hands(
                frame,
                [
                    SimpleNamespace(
                        landmarks=[_landmark(0.60, 0.20, z=None, visibility=None)],
                        handedness="Right",
                    )
                ],
                crop,
                crop,
            )
        finally:
            display_module.draw_simple_landmarks = original_draw

        self.assertEqual(len(drawn), 2)
        self.assertAlmostEqual(drawn[1][0].x, 0.38)
        self.assertIsNone(drawn[1][0].z)
        self.assertIsNone(drawn[1][0].visibility)


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

    async def test_mic_decision_starts_voice_capture(self) -> None:
        voice_capture = FakeVoiceCapture()
        command_dispatcher = FakeCommandDispatcher()
        pipeline = CommandDispatchPipeline(
            FakeGestureSession(),
            voice_capture,
            command_dispatcher,
            None,
            FakeLogger(),
        )

        voice_task = await pipeline.handle_decision(
            command_gesture=GESTURE_MIC,
            activated=True,
            now=1.0,
            voice_task=None,
        )
        self.assertIsNotNone(voice_task)
        await voice_task

        self.assertEqual(voice_capture.capture_count, 1)
        self.assertEqual(command_dispatcher.enqueued, [])

    async def test_app_voice_request_starts_capture_stream(self) -> None:
        service = GestureRemoteService.__new__(GestureRemoteService)
        voice_capture = FakeVoiceCapture()
        service._voice_capture = voice_capture
        service._voice_task = None
        service._logger = FakeLogger()
        stream = FakeVoiceStream()

        await service._handle_app_voice_input(
            AppVoiceInputRequest(
                stream=stream,
                session_id=7,
                package_name="com.example.app",
            )
        )
        self.assertIsNotNone(service._voice_task)
        await service._voice_task

        self.assertEqual(
            voice_capture.capture_streams,
            [(stream, "android_app_voice session_id=7 package=com.example.app")],
        )
        self.assertFalse(stream.ended)

    async def test_app_voice_request_is_rejected_while_capture_is_running(
        self,
    ) -> None:
        service = GestureRemoteService.__new__(GestureRemoteService)
        service._voice_capture = FakeVoiceCapture()
        service._logger = FakeLogger()
        service._voice_task = asyncio.create_task(asyncio.sleep(60.0))
        stream = FakeVoiceStream()

        try:
            await service._handle_app_voice_input(
                AppVoiceInputRequest(
                    stream=stream,
                    session_id=8,
                    package_name="com.example.app",
                )
            )
        finally:
            service._voice_task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await service._voice_task

        self.assertTrue(stream.ended)
        self.assertIn(
            (
                "Rejecting Android app voice input because microphone capture "
                "is already running: android_app_voice session_id=8 "
                "package=com.example.app"
            ),
            service._logger.messages,
        )


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
        logger = FakeLogger()
        gesture_session = FakeReloadableConfig()
        voice_capture = FakeReloadableConfig()
        camera = FakeReloadableConfig()
        hand_tracker = FakeReloadableConfig()
        coordinator = ConfigReloadCoordinator(
            initial_config,
            gesture_session=gesture_session,
            voice_capture=voice_capture,
            camera=camera,
            hand_tracker=hand_tracker,
            logger=logger,
            config_provider=lambda: latest_config,
        )

        config = coordinator.reload_if_needed_sync(now=CONFIG_RELOAD_INTERVAL_SECONDS)

        self.assertEqual(config.tv.host, "10.0.0.10")
        self.assertEqual(config.camera.webcam_index, 0)
        self.assertEqual(config.camera.zoom, 2.0)
        self.assertEqual(config.debug.log_seconds, 0.1)
        self.assertEqual(gesture_session.config, config)
        self.assertEqual(voice_capture.config, config)
        self.assertEqual(camera.config, config)
        self.assertEqual(hand_tracker.config, config)
        self.assertIn("Reloaded live config settings.", logger.messages)

    def test_reload_config_is_throttled(self) -> None:
        provider = ProviderCounter(app_config())
        coordinator = ConfigReloadCoordinator(
            app_config(),
            gesture_session=FakeReloadableConfig(),
            voice_capture=FakeReloadableConfig(),
            camera=FakeReloadableConfig(),
            hand_tracker=FakeReloadableConfig(),
            logger=FakeLogger(),
            config_provider=provider,
        )
        coordinator.reload_if_needed_sync(now=10.0)

        coordinator.reload_if_needed_sync(
            now=10.0 + CONFIG_RELOAD_INTERVAL_SECONDS - 0.01
        )

        self.assertEqual(provider.calls, 1)


class DisplayDebugCoordinatorTests(unittest.TestCase):
    def test_debug_message_is_logged_on_change_or_interval(self) -> None:
        display = FakeDebugDisplay()
        logger = FakeLogger()
        coordinator = DisplayDebugCoordinator(display, logger)
        config = app_config(debug_log_seconds=1.0)
        crop = CropRect(0.0, 0.0, 1.0, 1.0)

        coordinator.render(
            config=config,
            frame=object(),
            detected_hands=[],
            detection_crop=crop,
            display_crop=crop,
            decision=GestureDecision(None, False, "same"),
            now=1.0,
        )
        coordinator.render(
            config=config,
            frame=object(),
            detected_hands=[],
            detection_crop=crop,
            display_crop=crop,
            decision=GestureDecision(None, False, "same"),
            now=1.5,
        )
        coordinator.render(
            config=config,
            frame=object(),
            detected_hands=[],
            detection_crop=crop,
            display_crop=crop,
            decision=GestureDecision(None, False, "same"),
            now=2.1,
        )
        coordinator.render(
            config=config,
            frame=object(),
            detected_hands=[],
            detection_crop=crop,
            display_crop=crop,
            decision=GestureDecision(None, False, "changed"),
            now=2.2,
        )

        self.assertEqual(logger.messages, ["same", "same", "changed"])
        self.assertEqual(display.rendered, 4)


class GestureRemoteCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_cleanup_timeout_does_not_wait_for_blocked_method(self) -> None:
        logger = FakeLogger()
        coordinator = CleanupCoordinator(
            remote=FakeCleanupRemote(),
            frame_source=FakeCleanupFrameSource(),
            hand_tracker=FakeCleanupHandTracker(),
            display=FakeDebugDisplay(),
            command_dispatcher=FakeCleanupCommandDispatcher(),
            logger=logger,
        )

        def blocked_cleanup() -> None:
            time.sleep(10.0)

        with patch(
            "src.application.services.coordinators.cleanup.CLEANUP_TIMEOUT_SECONDS",
            0.01,
        ):
            started = time.monotonic()
            await coordinator._cleanup_sync_step("blocked cleanup", blocked_cleanup)
            elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.5)
        self.assertIn(
            "Timed out while cleaning up blocked cleanup.",
            logger.messages,
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

    async def test_repeated_pending_commands_are_coalesced(self) -> None:
        remote = BlockingRemote()
        dispatcher = RemoteCommandDispatcher(remote, FakeLogger())
        dispatcher.start()

        dispatcher.enqueue("POINT_DOWN", TV_COMMAND_DPAD_DOWN)
        await asyncio.wait_for(remote.first_started.wait(), timeout=1.0)

        dispatcher.enqueue("POINT_DOWN", TV_COMMAND_DPAD_DOWN)
        dispatcher.enqueue("POINT_DOWN", TV_COMMAND_DPAD_DOWN)

        remote.release_first.set()
        await asyncio.wait_for(remote.second_started.wait(), timeout=1.0)

        self.assertEqual(
            remote.commands,
            [TV_COMMAND_DPAD_DOWN, TV_COMMAND_DPAD_DOWN],
        )
        await dispatcher.close()

    async def test_repeated_pending_commands_can_skip_coalescing(self) -> None:
        remote = BlockingRemote()
        dispatcher = RemoteCommandDispatcher(remote, FakeLogger())
        dispatcher.start()

        dispatcher.enqueue("remote:DPAD_DOWN", TV_COMMAND_DPAD_DOWN)
        await asyncio.wait_for(remote.first_started.wait(), timeout=1.0)

        dispatcher.enqueue(
            "remote:DPAD_DOWN",
            TV_COMMAND_DPAD_DOWN,
            coalesce_repeats=False,
        )
        dispatcher.enqueue(
            "remote:DPAD_DOWN",
            TV_COMMAND_DPAD_DOWN,
            coalesce_repeats=False,
        )
        dispatcher.enqueue(
            "remote:DPAD_DOWN",
            TV_COMMAND_DPAD_DOWN,
            coalesce_repeats=False,
        )

        remote.release_first.set()
        await self._wait_for_commands(remote, 4)

        self.assertEqual(
            remote.commands,
            [
                TV_COMMAND_DPAD_DOWN,
                TV_COMMAND_DPAD_DOWN,
                TV_COMMAND_DPAD_DOWN,
                TV_COMMAND_DPAD_DOWN,
            ],
        )
        await dispatcher.close()

    async def test_queue_overflow_drops_oldest_pending_command(self) -> None:
        remote = BlockingRemote()
        dispatcher = RemoteCommandDispatcher(remote, FakeLogger())
        dispatcher.start()

        dispatcher.enqueue("VOLUME_UP", TV_COMMAND_VOLUME_UP)
        await asyncio.wait_for(remote.first_started.wait(), timeout=1.0)
        for index in range(MAX_PENDING_COMMANDS):
            command = TV_COMMAND_HOME if index % 2 == 0 else TV_COMMAND_VOLUME_UP
            dispatcher.enqueue(f"PENDING_{index}", command)

        dispatcher.enqueue("VOLUME_DOWN", TV_COMMAND_VOLUME_DOWN)

        self.assertEqual(dispatcher.queue_depth, MAX_PENDING_COMMANDS)
        self.assertEqual(dispatcher.dropped_commands, 1)

        remote.release_first.set()
        await dispatcher.close()

    async def test_queue_overflow_replaces_newest_duplicate_without_drop_count(
        self,
    ) -> None:
        remote = BlockingRemote()
        dispatcher = RemoteCommandDispatcher(remote, FakeLogger())
        dispatcher.start()

        dispatcher.enqueue("VOLUME_UP", TV_COMMAND_VOLUME_UP)
        await asyncio.wait_for(remote.first_started.wait(), timeout=1.0)
        for index in range(MAX_PENDING_COMMANDS):
            command = TV_COMMAND_HOME if index % 2 == 0 else TV_COMMAND_VOLUME_UP
            dispatcher.enqueue(f"PENDING_{index}", command)

        dispatcher.enqueue("VOLUME_UP_NEWER", TV_COMMAND_VOLUME_UP)

        self.assertEqual(dispatcher.queue_depth, MAX_PENDING_COMMANDS)
        self.assertEqual(dispatcher.dropped_commands, 0)

        remote.release_first.set()
        await dispatcher.close()

    async def test_unsupported_command_is_not_enqueued(self) -> None:
        remote = BlockingRemote(supported_commands=frozenset({TV_COMMAND_HOME}))
        logger = FakeLogger()
        dispatcher = RemoteCommandDispatcher(remote, logger)

        dispatcher.enqueue("VOLUME_UP", TV_COMMAND_VOLUME_UP)

        self.assertEqual(remote.commands, [])
        self.assertEqual(dispatcher.queue_depth, 0)
        self.assertEqual(dispatcher.dropped_commands, 1)
        self.assertIn(
            (
                "Adapter does not support command. "
                f"Skipping source=VOLUME_UP command={TV_COMMAND_VOLUME_UP}"
            ),
            logger.messages,
        )
        await dispatcher.close()

    async def _wait_for_commands(self, remote: "BlockingRemote", count: int) -> None:
        for _ in range(100):
            if len(remote.commands) >= count:
                return
            await asyncio.sleep(0.01)
        self.fail(f"Timed out waiting for {count} commands")


class DirectRemoteServiceTests(unittest.TestCase):
    def test_dispatch_enqueues_supported_direct_remote_command(self) -> None:
        remote = BlockingRemote(supported_commands=frozenset({TV_COMMAND_HOME}))
        dispatcher = FakeCommandDispatcher()
        service = DirectRemoteService(remote, dispatcher)

        result = service.dispatch(TV_COMMAND_HOME)

        self.assertTrue(result.accepted)
        self.assertEqual(
            dispatcher.enqueued,
            [(f"remote:{TV_COMMAND_HOME}", TV_COMMAND_HOME)],
        )
        self.assertEqual(
            dispatcher.enqueue_options,
            [
                {
                    "coalesce_repeats": False,
                    "max_pending": MAX_DIRECT_REMOTE_PENDING_COMMANDS,
                }
            ],
        )

    def test_dispatch_rejects_unknown_direct_remote_command(self) -> None:
        remote = BlockingRemote(supported_commands=frozenset({TV_COMMAND_HOME}))
        dispatcher = FakeCommandDispatcher()
        service = DirectRemoteService(remote, dispatcher)

        result = service.dispatch("NOPE")

        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "unknown_command")
        self.assertEqual(dispatcher.enqueued, [])

    def test_dispatch_rejects_unsupported_direct_remote_command(self) -> None:
        remote = BlockingRemote(supported_commands=frozenset({TV_COMMAND_HOME}))
        dispatcher = FakeCommandDispatcher()
        service = DirectRemoteService(remote, dispatcher)

        result = service.dispatch(TV_COMMAND_VOLUME_UP)

        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "unsupported_command")
        self.assertEqual(dispatcher.enqueued, [])

    def test_dispatch_enqueues_supported_power_command(self) -> None:
        remote = BlockingRemote(supported_commands=frozenset({TV_COMMAND_POWER_TOGGLE}))
        dispatcher = FakeCommandDispatcher()
        service = DirectRemoteService(remote, dispatcher)

        result = service.dispatch(TV_COMMAND_POWER_TOGGLE)

        self.assertTrue(result.accepted)
        self.assertEqual(
            dispatcher.enqueued,
            [(f"remote:{TV_COMMAND_POWER_TOGGLE}", TV_COMMAND_POWER_TOGGLE)],
        )

    def test_capabilities_group_supported_direct_remote_commands(self) -> None:
        remote = BlockingRemote(
            supported_commands=frozenset(
                {
                    TV_COMMAND_HOME,
                    TV_COMMAND_POWER_TOGGLE,
                    TV_COMMAND_VOLUME_UP,
                }
            )
        )
        dispatcher = FakeCommandDispatcher()
        service = DirectRemoteService(remote, dispatcher)

        capabilities = service.capabilities()

        self.assertEqual(
            capabilities.supported_commands,
            (TV_COMMAND_POWER_TOGGLE, TV_COMMAND_HOME, TV_COMMAND_VOLUME_UP),
        )
        self.assertEqual(
            capabilities.command_groups["power"],
            (TV_COMMAND_POWER_TOGGLE,),
        )
        self.assertEqual(capabilities.command_groups["navigation"], (TV_COMMAND_HOME,))


class BlockingRemote:
    def __init__(self, supported_commands: frozenset[str] | None = None) -> None:
        self.commands = []
        self.first_started = asyncio.Event()
        self.second_started = asyncio.Event()
        self.release_first = asyncio.Event()
        self._supported_commands = supported_commands or frozenset(
            {
                TV_COMMAND_DPAD_DOWN,
                TV_COMMAND_HOME,
                TV_COMMAND_VOLUME_DOWN,
                TV_COMMAND_VOLUME_UP,
            }
        )

    def capabilities(self) -> TvAdapterCapabilities:
        return TvAdapterCapabilities(
            supported_commands=self._supported_commands,
            power=CapabilityStatus.UNSUPPORTED,
            volume=CapabilityStatus.IMPLEMENTED,
            directional_navigation=CapabilityStatus.IMPLEMENTED,
            media_controls=CapabilityStatus.UNSUPPORTED,
            text_input=CapabilityStatus.UNSUPPORTED,
            source_selection=CapabilityStatus.UNSUPPORTED,
            wake_on_lan=CapabilityStatus.UNSUPPORTED,
            pairing=CapabilityStatus.UNSUPPORTED,
            voice_input=VoiceInputCapabilities(
                remote_mic_stream=CapabilityStatus.UNSUPPORTED,
                native_voice_search=CapabilityStatus.UNSUPPORTED,
                app_voice_input=CapabilityStatus.UNSUPPORTED,
                app_text_input=CapabilityStatus.UNSUPPORTED,
            ),
            connection_type="fake",
        )

    async def send_command(self, command: str) -> None:
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

    def debug(self, message: str) -> None:
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
    def __init__(self) -> None:
        self.pointer_reference_size = None
        self.motion_scale = None

    def evaluate(
        self,
        hand_states,
        now,
        pointer_reference_size=1.0,
        motion_scale=None,
    ):
        self.pointer_reference_size = pointer_reference_size
        self.motion_scale = motion_scale
        return GestureDecision(None, False, "")


class FakeDisplayMetrics:
    def __init__(self, width: float, height: float) -> None:
        self._size = DisplaySize(width, height)

    def latest_size(self) -> DisplaySize:
        return self._size


class FakeVoiceCapture:
    def __init__(self) -> None:
        self.capture_count = 0
        self.capture_streams = []

    async def capture(self) -> None:
        self.capture_count += 1

    async def capture_stream(self, voice_stream, context: str) -> None:
        self.capture_streams.append((voice_stream, context))


class FakeVoiceStream:
    def __init__(self) -> None:
        self.ended = False

    def send_chunk(self, chunk: bytes) -> bool:
        del chunk
        return True

    def end(self) -> None:
        self.ended = True


class FakeCommandDispatcher:
    queue_depth = 0
    last_send_latency_seconds = None
    dropped_commands = 0

    def __init__(self) -> None:
        self.enqueued = []
        self.enqueue_options = []

    def enqueue(
        self,
        source,
        command,
        *,
        coalesce_repeats=True,
        max_pending=None,
    ) -> None:
        self.enqueued.append((source, command))
        self.enqueue_options.append(
            {
                "coalesce_repeats": coalesce_repeats,
                "max_pending": max_pending,
            }
        )


class FakeDebugDisplay:
    def __init__(self) -> None:
        self.rendered = 0
        self.closed = False

    def debug_message(
        self,
        decision_debug_message: str,
        detection_crop: CropRect,
        display_crop: CropRect,
        zoom_frozen: bool = False,
    ) -> str:
        del detection_crop, display_crop, zoom_frozen
        return decision_debug_message

    def draw_detected_hands(
        self,
        frame: Any,
        detected_hands: list[Any],
        source_crop: CropRect,
        display_crop: CropRect,
    ) -> None:
        del frame, detected_hands, source_crop, display_crop

    def draw_pointer_zones(
        self,
        frame: Any,
        pointer_debug: Any,
        display_crop: CropRect,
    ) -> None:
        del frame, pointer_debug, display_crop

    def draw_volume_zones(
        self,
        frame: Any,
        volume_debug: Any,
        display_crop: CropRect,
    ) -> None:
        del frame, volume_debug, display_crop

    def render(self, app_name: str, frame: Any) -> bool:
        del app_name, frame
        self.rendered += 1
        return False

    def close(self) -> None:
        self.closed = True


class FakeCleanupRemote:
    def capabilities(self) -> Any:
        return None

    def set_app_voice_input_handler(self, handler) -> None:
        del handler

    async def connect(self) -> bool:
        return True

    async def wake(self) -> bool:
        return True

    async def discover_mac_address(self) -> None:
        return None

    async def send_command(self, command: str) -> None:
        del command

    async def start_voice(self, mode: Any) -> None:
        del mode

    async def disconnect(self) -> None:
        pass


class FakeCleanupFrameSource:
    def is_open(self) -> bool:
        return True

    def start(self) -> None:
        pass

    def latest_versioned(self) -> tuple[int, Any | None]:
        return 0, None

    def failed(self) -> bool:
        return False

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass


class FakeCleanupHandTracker:
    def update_config(self, config: AppConfig) -> None:
        del config

    def detect(self, frame: Any, timestamp_ms: int) -> tuple[list[Any], list[Any]]:
        del frame, timestamp_ms
        return [], []

    def close(self) -> None:
        pass


class FakeCleanupCommandDispatcher:
    def start(self) -> None:
        pass

    def enqueue(
        self,
        gesture: str,
        command: str,
        *,
        coalesce_repeats: bool = True,
        max_pending: int | None = None,
    ) -> None:
        del coalesce_repeats, max_pending
        del gesture, command

    @property
    def queue_depth(self) -> int:
        return 0

    @property
    def dropped_commands(self) -> int:
        return 0

    @property
    def last_send_latency_seconds(self) -> float | None:
        return None

    async def close(self) -> None:
        pass


def _landmark(x: float, y: float, **attributes):
    return SimpleNamespace(x=x, y=y, **attributes)


def _decision_with_hands(
    hand_count: int,
    freeze_zoom: bool = False,
    hand_size: float = 0.20,
) -> GestureDecision:
    centers = [(0.38, 0.50), (0.62, 0.50), (0.50, 0.70)]
    return GestureDecision(
        command_gesture=None,
        activated=True,
        debug_message="",
        freeze_zoom=freeze_zoom,
        zoom_landmarks=[
            _hand_landmarks(centers[index], hand_size) for index in range(hand_count)
        ],
    )


def _hand_landmarks(center: tuple[float, float], size: float):
    center_x, center_y = center
    half_size = size / 2
    return [
        _landmark(center_x - half_size, center_y - half_size),
        _landmark(center_x + half_size, center_y + half_size),
    ]


if __name__ == "__main__":
    unittest.main()
