import tempfile
import unittest
from pathlib import Path

from src.shared.logging import AppLogger, configure_app_logging


class LoggingTests(unittest.TestCase):
    def tearDown(self) -> None:
        AppLogger._log_file = None
        AppLogger._console = True

    def test_configured_logger_writes_and_resets_log_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "logs" / "logs.txt"

            configure_app_logging(log_file, reset=True, console=False)
            AppLogger().info("first")
            AppLogger().error("second")

            self.assertEqual(
                log_file.read_text(encoding="utf-8").splitlines(),
                ["[INFO] first", "[ERROR] second"],
            )

            configure_app_logging(log_file, reset=True, console=False)

            self.assertEqual(log_file.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
