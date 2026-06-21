import unittest
from unittest.mock import Mock, patch

from src.runtime import cli


class RuntimeCliTests(unittest.TestCase):
    def test_run_defaults_to_all_runtime(self) -> None:
        with patch("src.runtime.cli.run_all") as run_all:
            cli.run([])

        run_all.assert_called_once_with()

    def test_run_starts_gesture_runtime(self) -> None:
        with patch("src.runtime.gesture_app.run") as run_gesture:
            cli.run(["gesture"])

        run_gesture.assert_called_once_with()

    def test_run_starts_config_runtime(self) -> None:
        with patch("src.runtime.config_server.run") as run_config:
            cli.run(["config"])

        run_config.assert_called_once_with()

    def test_run_all_stops_config_runner_after_gesture_runtime(self) -> None:
        runner = Mock()
        with (
            patch("src.runtime.cli.configure_app_logging"),
            patch("src.runtime.config_server.create_runner", return_value=runner),
            patch("src.runtime.gesture_app.run") as run_gesture,
        ):
            cli.run_all()

        runner.start.assert_called_once_with()
        run_gesture.assert_called_once_with(configure_logging=False)
        runner.stop.assert_called_once_with()

    def test_run_all_continues_when_config_runner_fails_to_start(self) -> None:
        with (
            patch("src.runtime.cli.configure_app_logging"),
            patch("src.runtime.config_server.create_runner", side_effect=OSError),
            patch("src.runtime.gesture_app.run") as run_gesture,
        ):
            cli.run_all()

        run_gesture.assert_called_once_with(configure_logging=False)


if __name__ == "__main__":
    unittest.main()
