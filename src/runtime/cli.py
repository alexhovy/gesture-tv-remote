import argparse
import sys

from src.runtime import config_server, local_gesture_app, web_app
from src.shared.logging import AppLogger, configure_app_logging


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run Gesture TV Remote runtimes.",
    )
    parser.add_argument(
        "runtime",
        nargs="?",
        choices=("app", "local-gesture", "settings"),
        default="app",
        help="Runtime to start. Defaults to app.",
    )
    args = parser.parse_args(argv)

    if args.runtime == "app":
        web_app.run()
        return
    if args.runtime == "local-gesture":
        local_gesture_app.run()
        return
    if args.runtime == "settings":
        config_server.run()
        return


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
        local_gesture_app.run(configure_logging=False)
    finally:
        if config_runner is not None:
            config_runner.stop()


def main() -> None:
    run(sys.argv[1:])
