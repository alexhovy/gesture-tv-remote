import asyncio
import sys

from src.runtime.builders.config import build_config_provider, build_config_repository
from src.runtime.container import build_gesture_remote_service
from src.shared.config import AppConfig, load_config_from_env
from src.shared.logging import AppLogger, configure_app_logging


async def main() -> None:
    service = build_gesture_remote_service(create_config_provider())
    await service.run()


def load_config() -> AppConfig:
    return create_config_provider()()


def create_config_provider():
    bootstrap_config = load_config_from_env()
    repository = build_config_repository(bootstrap_config)
    return build_config_provider(repository)


def run(configure_logging: bool = True) -> None:
    if configure_logging:
        configure_app_logging()
    _configure_windows_event_loop_policy()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        AppLogger().info("Exiting.")


def _configure_windows_event_loop_policy() -> None:
    if sys.platform != "win32":
        return

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
