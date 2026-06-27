from __future__ import annotations

from src.runtime.builders.config import build_config_provider, build_config_repository
from src.runtime.config_server import ConfigServerRunner
from src.shared.config import load_config_from_env
from src.shared.logging import AppLogger


def build_config_server_runner(
    host: str | None = None,
    port: int | None = None,
) -> ConfigServerRunner:
    from src.infrastructure.network.mdns import MdnsPublisher
    from src.web.config_app import create_config_server

    bootstrap_config = load_config_from_env()
    repository = build_config_repository(bootstrap_config)
    config_provider = build_config_provider(repository)
    config = config_provider()
    bind_host = config.web.host if host is None else host
    bind_port = config.web.port if port is None else port
    server = create_config_server(
        repository,
        config_provider,
        bind_host,
        bind_port,
    )
    logger = AppLogger()
    mdns_publisher = None
    if config.web.mdns_enabled:
        mdns_publisher = MdnsPublisher(config.web.mdns_name, bind_port, logger)
    return ConfigServerRunner(server, mdns_publisher, logger)
