import threading
from http.server import ThreadingHTTPServer

from src.infrastructure.network.mdns import MdnsPublisher
from src.shared.logging import AppLogger, configure_app_logging


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
        host = _display_host(host)
        self._logger.info(f"Config UI listening on http://{host}:{port}")

    def run_forever(self) -> None:
        if self._mdns_publisher is not None:
            self._mdns_publisher.start()
        host, port = self._server.server_address[:2]
        host = _display_host(host)
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
    from src.runtime.builders.web import build_config_server_runner

    return build_config_server_runner(host, port)


def _display_host(host: str | bytes | bytearray) -> str:
    if isinstance(host, str):
        return host
    return host.decode("utf-8", errors="replace")


def run_config_server(
    host: str | None = None,
    port: int | None = None,
) -> None:
    create_runner(host, port).run_forever()


def run() -> None:
    configure_app_logging()
    run_config_server()
