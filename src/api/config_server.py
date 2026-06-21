from src.infrastructure.data_access.sqlite_store import SqliteStore
from src.infrastructure.network.mdns import MdnsPublisher
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.shared.config import AppConfig, load_config_from_env
from src.shared.logging import AppLogger
from src.web.config_app import create_config_server


def run_config_server(
    host: str | None = None,
    port: int | None = None,
) -> None:
    bootstrap_config = load_config_from_env()
    repository = ConfigRepository(SqliteStore(bootstrap_config.config_db_file))
    config = _effective_config(repository)
    bind_host = config.config_web_host if host is None else host
    bind_port = config.config_web_port if port is None else port
    server = create_config_server(
        repository,
        lambda: _effective_config(repository),
        bind_host,
        bind_port,
    )
    logger = AppLogger()
    mdns_publisher = None
    if config.config_web_mdns_enabled:
        mdns_publisher = MdnsPublisher(config.config_web_mdns_name, bind_port, logger)
        mdns_publisher.start()

    logger.info(f"Config UI listening on http://{bind_host}:{bind_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Config UI stopped.")
    finally:
        if mdns_publisher is not None:
            try:
                mdns_publisher.stop()
            except KeyboardInterrupt:
                logger.info("mDNS cleanup interrupted.")
        server.server_close()


def run() -> None:
    run_config_server()


def _effective_config(repository: ConfigRepository) -> AppConfig:
    bootstrap_config = load_config_from_env()
    saved_config = repository.get_config()
    return load_config_from_env(base_config=saved_config or bootstrap_config)
