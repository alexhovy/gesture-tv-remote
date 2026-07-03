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

    def test_logs_https_scheme_when_configured(self) -> None:
        server = FakeServer()
        logger = FakeLogger()
        runner = ConfigServerRunner(server, None, logger, scheme="https")

        runner.start()
        runner.stop()

        self.assertIn("Config UI listening on https://127.0.0.1:80", logger.messages)

    def test_stop_handles_keyboard_interrupt_during_shutdown(self) -> None:
        server = FakeServer(interrupt_shutdown=True)
        logger = FakeLogger()
        runner = ConfigServerRunner(server, None, logger)
        runner._thread = FakeThread()

        runner.stop()

        self.assertTrue(server.closed)
        self.assertIsNone(runner._thread)
        self.assertIn("Config UI cleanup interrupted.", logger.messages)


class FakeServer:
    server_address = ("127.0.0.1", 80)

    def __init__(self, interrupt_shutdown: bool = False) -> None:
        self.interrupt_shutdown = interrupt_shutdown
        self.closed = False
        self.shutdown_called = False

    def serve_forever(self) -> None:
        pass

    def shutdown(self) -> None:
        self.shutdown_called = True
        if self.interrupt_shutdown:
            raise KeyboardInterrupt

    def server_close(self) -> None:
        self.closed = True


class FakeThread:
    def join(self, timeout: float | None = None) -> None:
        pass


class FakeLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)


if __name__ == "__main__":
    unittest.main()
