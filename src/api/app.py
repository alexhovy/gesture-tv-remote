import asyncio
from collections.abc import Callable

from src.infrastructure.data_access.sqlite_store import SqliteStore
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.shared.config import AppConfig, load_config_from_env
from src.shared.logging import AppLogger


async def main() -> None:
    from src.services.gesture_remote_service import GestureRemoteService

    config_provider = create_config_provider()
    service = GestureRemoteService(config_provider(), config_provider)
    await service.run()


def load_config() -> AppConfig:
    return create_config_provider()()


def create_config_provider() -> Callable[[], AppConfig]:
    bootstrap_config = load_config_from_env()
    repository = ConfigRepository(SqliteStore(bootstrap_config.config_db_file))

    def provide_config() -> AppConfig:
        saved_config = repository.get_config()
        return load_config_from_env(base_config=saved_config or bootstrap_config)

    return provide_config


def run() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        AppLogger().info("Exiting.")
