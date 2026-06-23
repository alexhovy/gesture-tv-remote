import unittest

from src.application.services.gesture_remote_service import GestureRemoteService
from src.application.services.pipeline_metrics import PipelineMetrics
from tests.config_helpers import app_config
from tests.fakes.fake_application_adapters import (
    FakeCamera,
    FakeCommandDispatcher,
    FakeDisplay,
    FakeFrameProcessor,
    FakeModelStore,
    FakeVoiceCapture,
)
from tests.fakes.fake_frame_source import FakeFrameSource
from tests.fakes.fake_hand_tracker import FakeHandTracker
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_tv_remote import FakeTVRemote


class ApplicationPortsTests(unittest.IsolatedAsyncioTestCase):
    async def test_gesture_remote_service_runs_with_swappable_fakes(self) -> None:
        config = app_config()
        remote = FakeTVRemote()
        frame_source = FakeFrameSource(frames=[object()])
        model_store = FakeModelStore()
        dispatcher = FakeCommandDispatcher()
        display = FakeDisplay()
        hand_tracker = FakeHandTracker()

        service = GestureRemoteService(
            config,
            remote=remote,
            frame_source=frame_source,
            hand_tracker=hand_tracker,
            camera=FakeCamera(),
            frame_processor=FakeFrameProcessor(),
            display=display,
            voice_capture=FakeVoiceCapture(),
            command_dispatcher=dispatcher,
            model_store=model_store,
            logger=FakeLogger(),
            metrics=PipelineMetrics(config.tv.adapter),
        )

        await service.run()

        self.assertEqual(remote.connect_calls, 1)
        self.assertEqual(remote.disconnect_calls, 1)
        self.assertTrue(frame_source.started)
        self.assertTrue(frame_source.closed)
        self.assertTrue(model_store.ensured)
        self.assertTrue(dispatcher.started)
        self.assertTrue(dispatcher.closed)
        self.assertEqual(len(hand_tracker.detected_frames), 1)
        self.assertTrue(hand_tracker.closed)
        self.assertEqual(display.rendered, 1)
        self.assertTrue(display.closed)


if __name__ == "__main__":
    unittest.main()
