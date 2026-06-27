from __future__ import annotations

from src.application.ports.config_provider import ConfigProviderPort, ConfigStorePort
from src.shared.config import AppConfig, load_config_from_env


def build_config_repository(config: AppConfig) -> ConfigStorePort:
    from src.infrastructure.data_access.sqlite_store import SqliteStore
    from src.infrastructure.repositories.config_repository import ConfigRepository

    return ConfigRepository(SqliteStore(config.config_db_file))


def build_config_provider(repository: ConfigStorePort) -> ConfigProviderPort:
    bootstrap_config = load_config_from_env()

    def provide_config() -> AppConfig:
        saved_config = repository.get_config()
        return load_config_from_env(base_config=saved_config or bootstrap_config)

    return provide_config
