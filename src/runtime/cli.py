import argparse
import sys

from src.runtime import config_server, gesture_app
from src.shared.logging import AppLogger, configure_app_logging


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run Gesture TV Remote runtimes.",
    )
    parser.add_argument(
        "runtime",
        nargs="?",
        choices=("all", "gesture", "config", "web-control"),
        default="all",
        help="Runtime to start. Defaults to all.",
    )
    args = parser.parse_args(argv)

    if args.runtime == "gesture":
        gesture_app.run()
        return
    if args.runtime == "config":
        config_server.run()
        return
    if args.runtime == "web-control":
        from src.runtime import browser_control_app

        browser_control_app.run()
        return
    run_all()


def run_all() -> None:
    configure_app_logging()
    logger = AppLogger()
    config_runner = None
    try:
        config_runner = config_server.create_runner()
        config_runner.start()
    except OSError as error:
        logger.error(f"Config UI failed to start: {error}")

    try:
        gesture_app.run(configure_logging=False)
    finally:
        if config_runner is not None:
            config_runner.stop()


def main() -> None:
    run(sys.argv[1:])
