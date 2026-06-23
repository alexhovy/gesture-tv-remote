import unittest

from src.runtime.config_server import ConfigServerRunner


class ConfigServerRunnerTests(unittest.TestCase):
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

    def shutdown(self) -> None:
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
