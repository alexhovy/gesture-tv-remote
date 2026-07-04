import ssl
import unittest

from src.runtime.builders.web import _config_web_port
from src.runtime.config_server import ConfigServerRunner
from src.shared.config import AppConfig, WebConfig


class ConfigServerRunnerTests(unittest.TestCase):
    def test_https_config_server_uses_443_when_default_web_port_is_unchanged(
        self,
    ) -> None:
        self.assertEqual(
            _config_web_port(AppConfig(), ssl.create_default_context()),
            443,
        )

    def test_https_config_server_keeps_explicit_web_port(self) -> None:
        config = AppConfig(web=WebConfig(port=8443))

        self.assertEqual(
            _config_web_port(config, ssl.create_default_context()),
            8443,
        )

    def test_stop_handles_keyboard_interrupt_during_shutdown(self) -> None:
        server = FakeServer(interrupt_shutdown=True)
        logger = FakeLogger()
        runner = ConfigServerRunner(server, None, logger)
        runner._thread = FakeThread()

        runner.stop()

        self.assertTrue(server.shutdown_called)
        self.assertTrue(server.server_close_called)
        self.assertIsNone(runner._thread)


class FakeServer:
    def __init__(self, interrupt_shutdown: bool = False) -> None:
        self.interrupt_shutdown = interrupt_shutdown
        self.server_address = ("127.0.0.1", 0)
        self.shutdown_called = False
        self.server_close_called = False

    def shutdown(self) -> None:
        self.shutdown_called = True
        if self.interrupt_shutdown:
            raise KeyboardInterrupt

    def server_close(self) -> None:
        self.server_close_called = True


class FakeThread:
    def join(self, timeout: float) -> None:
        del timeout


class FakeLogger:
    def info(self, message: str) -> None:
        del message


if __name__ == "__main__":
    unittest.main()
