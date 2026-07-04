import unittest

from src.application.services.gesture_remote_service import GestureRemoteService
from src.application.services.pipeline_metrics import PipelineMetrics
from tests.fakes.fake_application_adapters import (
    FakeCamera,
    FakeCommandDispatcher,
    FakeDisplay,
    FakeFrameProcessor,
    FakeVoiceCapture,
)
from tests.fakes.fake_frame_source import FakeFrameSource
from tests.fakes.fake_hand_tracker import FakeHandTracker
from tests.fakes.fake_logger import FakeLogger
from tests.fakes.fake_tv_remote import FakeTVRemote
from tests.helpers.config_helpers import app_config


class ApplicationPortsTests(unittest.IsolatedAsyncioTestCase):
    async def test_gesture_remote_service_runs_with_swappable_fakes(self) -> None:
        config = app_config()
        remote = FakeTVRemote()
        frame_source = FakeFrameSource(frames=[object()])
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
            logger=FakeLogger(),
            metrics=PipelineMetrics(config.tv.adapter),
        )

        await service.run()

        self.assertEqual(remote.connect_calls, 1)
        self.assertEqual(remote.disconnect_calls, 1)
        self.assertTrue(frame_source.started)
        self.assertTrue(frame_source.closed)
        self.assertTrue(dispatcher.started)
        self.assertTrue(dispatcher.closed)
        self.assertEqual(len(hand_tracker.detected_frames), 1)
        self.assertTrue(hand_tracker.closed)
        self.assertEqual(display.rendered, 1)
        self.assertTrue(display.closed)

    async def test_gesture_remote_service_wakes_before_connect_when_enabled(
        self,
    ) -> None:
        config = app_config(
            tv_wake_enabled=True,
            tv_mac_address="00:11:22:33:44:55",
            tv_wake_connect_timeout_seconds=0.0,
        )
        remote = FakeTVRemote()

        service = GestureRemoteService(
            config,
            remote=remote,
            frame_source=FakeFrameSource(open=False),
            hand_tracker=FakeHandTracker(),
            camera=FakeCamera(),
            frame_processor=FakeFrameProcessor(),
            display=FakeDisplay(),
            voice_capture=FakeVoiceCapture(),
            command_dispatcher=FakeCommandDispatcher(),
            logger=FakeLogger(),
            metrics=PipelineMetrics(config.tv.adapter),
        )

        await service.run()

        self.assertEqual(remote.wake_calls, 1)
        self.assertEqual(remote.connect_calls, 1)

    async def test_gesture_remote_service_stores_discovered_mac_and_enables_wake(
        self,
    ) -> None:
        config = app_config(tv_wake_enabled=False, tv_mac_address="")
        store = FakeConfigStore(config)

        service = GestureRemoteService(
            config,
            remote=FakeTVRemote(),
            frame_source=FakeFrameSource(frames=[object()]),
            hand_tracker=FakeHandTracker(),
            camera=FakeCamera(),
            frame_processor=FakeFrameProcessor(),
            display=FakeDisplay(),
            voice_capture=FakeVoiceCapture(),
            command_dispatcher=FakeCommandDispatcher(),
            logger=FakeLogger(),
            metrics=PipelineMetrics(config.tv.adapter),
            config_store=store,
            mac_address_resolver=FakeMacAddressResolver("aa:bb:cc:dd:ee:ff"),
        )

        await service.run()

        self.assertIsNotNone(store.saved_config)
        assert store.saved_config is not None
        self.assertEqual(store.saved_config.tv.mac_address, "aa:bb:cc:dd:ee:ff")
        self.assertTrue(store.saved_config.tv.wake_enabled)


class FakeConfigStore:
    def __init__(self, config):
        self.config = config
        self.saved_config = None

    def get_config(self):
        return self.config

    def save_config(self, config) -> None:
        self.saved_config = config
        self.config = config

    def reset_config(self) -> None:
        self.config = None


class FakeMacAddressResolver:
    def __init__(self, mac_address: str | None) -> None:
        self.mac_address = mac_address
        self.hosts: list[str] = []

    def resolve(self, host: str) -> str | None:
        self.hosts.append(host)
        return self.mac_address


if __name__ == "__main__":
    unittest.main()
