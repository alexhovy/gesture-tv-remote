import threading
from http.server import ThreadingHTTPServer

from src.infrastructure.data_access.sqlite_store import SqliteStore
from src.infrastructure.network.mdns import MdnsPublisher
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.shared.config import AppConfig, load_config_from_env
from src.shared.logging import AppLogger, configure_app_logging
from src.web.config_app import create_config_server


class ConfigServerRunner:
    def __init__(
        self,
        server: ThreadingHTTPServer,
        mdns_publisher: MdnsPublisher | None,
        logger: AppLogger,
    ) -> None:
        self._server = server
        self._mdns_publisher = mdns_publisher
        self._logger = logger
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._mdns_publisher is not None:
            self._mdns_publisher.start()
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
        )
        self._thread.start()
        host, port = self._server.server_address[:2]
        self._logger.info(f"Config UI listening on http://{host}:{port}")

    def run_forever(self) -> None:
        if self._mdns_publisher is not None:
            self._mdns_publisher.start()
        host, port = self._server.server_address[:2]
        self._logger.info(f"Config UI listening on http://{host}:{port}")
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            self._logger.info("Config UI stopped.")
        finally:
            self.stop()

    def stop(self) -> None:
        if self._thread is not None:
            try:
                self._server.shutdown()
                self._thread.join(timeout=5)
            except KeyboardInterrupt:
                self._logger.info("Config UI cleanup interrupted.")
            finally:
                self._thread = None
        self._server.server_close()
        if self._mdns_publisher is not None:
            try:
                self._mdns_publisher.stop()
            except KeyboardInterrupt:
                self._logger.info("mDNS cleanup interrupted.")


def create_runner(
    host: str | None = None,
    port: int | None = None,
) -> ConfigServerRunner:
    bootstrap_config = load_config_from_env()
    repository = ConfigRepository(SqliteStore(bootstrap_config.config_db_file))
    config = _effective_config(repository)
    bind_host = config.web.host if host is None else host
    bind_port = config.web.port if port is None else port
    server = create_config_server(
        repository,
        lambda: _effective_config(repository),
        bind_host,
        bind_port,
    )
    logger = AppLogger()
    mdns_publisher = None
    if config.web.mdns_enabled:
        mdns_publisher = MdnsPublisher(config.web.mdns_name, bind_port, logger)
    return ConfigServerRunner(server, mdns_publisher, logger)


def run_config_server(
    host: str | None = None,
    port: int | None = None,
) -> None:
    create_runner(host, port).run_forever()


def run() -> None:
    configure_app_logging()
    run_config_server()


def _effective_config(repository: ConfigRepository) -> AppConfig:
    bootstrap_config = load_config_from_env()
    saved_config = repository.get_config()
    return load_config_from_env(base_config=saved_config or bootstrap_config)
