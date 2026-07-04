from __future__ import annotations

import ssl

from src.infrastructure.web.tls import ensure_web_certificate
from src.runtime.builders.config import build_config_provider, build_config_repository
from src.runtime.config_server import ConfigServerRunner
from src.shared.config import DEFAULT_CONFIG, AppConfig, load_config_from_env
from src.shared.logging import AppLogger


def build_config_server_runner(
    host: str | None = None,
    port: int | None = None,
) -> ConfigServerRunner:
    from src.infrastructure.network.mdns import MdnsPublisher
    from src.web.settings.app import create_config_server

    bootstrap_config = load_config_from_env()
    repository = build_config_repository(bootstrap_config)
    config_provider = build_config_provider(repository)
    config = config_provider()
    logger = AppLogger()
    ssl_context = _build_ssl_context(config, logger)
    bind_host = config.web.host if host is None else host
    bind_port = _config_web_port(config, ssl_context) if port is None else port
    server = create_config_server(
        repository,
        config_provider,
        bind_host,
        bind_port,
    )
    if ssl_context is not None:
        server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    scheme = "https" if ssl_context is not None else "http"
    mdns_publisher = None
    if config.web.mdns_enabled:
        mdns_publisher = MdnsPublisher(
            config.web.mdns_name,
            bind_port,
            logger,
            scheme=scheme,
        )
    return ConfigServerRunner(server, mdns_publisher, logger, scheme=scheme)


def _build_ssl_context(config: AppConfig, logger: AppLogger) -> ssl.SSLContext:
    certificate = ensure_web_certificate(
        cert_file=config.web.tls_cert_file,
        key_file=config.web.tls_key_file,
        mdns_name=config.web.mdns_name,
    )
    if certificate.generated:
        logger.info(
            "Generated web TLS certificate: "
            f"cert={certificate.cert_file} key={certificate.key_file} "
            f"hosts={', '.join(certificate.hosts)}"
        )
    logger.info(
        "Using web TLS certificate. Trust this certificate on web devices "
        f"before opening https://{_mdns_host(config.web.mdns_name)}"
    )
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(
        certfile=config.web.tls_cert_file,
        keyfile=config.web.tls_key_file,
    )
    return context


def _config_web_port(config: AppConfig, ssl_context: ssl.SSLContext | None) -> int:
    if ssl_context is not None and config.web.port == DEFAULT_CONFIG.web.port:
        return 443
    return config.web.port


def _mdns_host(name: str) -> str:
    normalized = name.strip().lower()
    if normalized.endswith(".local"):
        return normalized
    return f"{normalized}.local"
