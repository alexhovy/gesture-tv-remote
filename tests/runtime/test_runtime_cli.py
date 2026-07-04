import unittest
from unittest.mock import Mock, patch

from src.runtime import cli, local_gesture_app


class RuntimeCliTests(unittest.TestCase):
    def test_run_defaults_to_web_app_runtime(self) -> None:
        with patch("src.runtime.web_app.run") as run_app:
            cli.run([])

        run_app.assert_called_once_with()

    def test_run_starts_local_gesture_runtime(self) -> None:
        with patch("src.runtime.local_gesture_app.run") as run_local_gesture:
            cli.run(["local-gesture"])

        run_local_gesture.assert_called_once_with()

    def test_run_starts_settings_runtime(self) -> None:
        with patch("src.runtime.config_server.run") as run_settings:
            cli.run(["settings"])

        run_settings.assert_called_once_with()

    def test_run_all_stops_config_runner_after_local_gesture_runtime(self) -> None:
        runner = Mock()
        with (
            patch("src.runtime.cli.configure_app_logging"),
            patch("src.runtime.config_server.create_runner", return_value=runner),
            patch("src.runtime.local_gesture_app.run") as run_local_gesture,
        ):
            cli.run_all()

        runner.start.assert_called_once_with()
        run_local_gesture.assert_called_once_with(configure_logging=False)
        runner.stop.assert_called_once_with()

    def test_run_all_continues_when_config_runner_fails_to_start(self) -> None:
        with (
            patch("src.runtime.cli.configure_app_logging"),
            patch("src.runtime.config_server.create_runner", side_effect=OSError),
            patch("src.runtime.local_gesture_app.run") as run_local_gesture,
        ):
            cli.run_all()

        run_local_gesture.assert_called_once_with(configure_logging=False)

    def test_windows_local_gesture_runtime_uses_selector_event_loop_policy(
        self,
    ) -> None:
        policy = object()
        with (
            patch("src.runtime.local_gesture_app.sys.platform", "win32"),
            patch(
                "src.runtime.local_gesture_app.asyncio.WindowsSelectorEventLoopPolicy",
                return_value=policy,
                create=True,
            ) as policy_factory,
            patch(
                "src.runtime.local_gesture_app.asyncio.set_event_loop_policy"
            ) as set_policy,
        ):
            local_gesture_app._configure_windows_event_loop_policy()

        policy_factory.assert_called_once_with()
        set_policy.assert_called_once_with(policy)


if __name__ == "__main__":
    unittest.main()
