import json
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.application.ports.config_provider import ConfigStorePort
from src.application.ports.logger import LoggerPort
from src.shared.config import AppConfig
from src.shared.logging import AppLogger
from src.web.assets import read_app_css
from src.web.settings.handlers import (
    render_settings_page,
    save_settings_form,
    settings_redirect,
)

ConfigProvider = Callable[[], AppConfig]


def create_config_server(
    repository: ConfigStorePort,
    config_provider: ConfigProvider,
    host: str = AppConfig().web.host,
    port: int = AppConfig().web.port,
    logger: LoggerPort | None = None,
) -> ThreadingHTTPServer:
    web_logger = logger or AppLogger()

    class ConfigRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            request_url = urlparse(self.path)
            path = request_url.path
            if path == "/":
                self._redirect("/settings")
                return
            if path == "/settings":
                web_logger.info(f"Web config page viewed from {self.client_address[0]}")
                self._send_html(
                    render_settings_page(
                        config_provider(),
                        query=request_url.query,
                    )
                )
                return
            if path == "/health":
                self._send_json({"status": "ok"})
                return
            if path == "/static/app.css":
                self._send_css(read_app_css())
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/settings":
                self._handle_settings()
                return
            if path == "/reset":
                repository.reset_config()
                web_logger.info(
                    f"Web config settings reset from {self.client_address[0]}"
                )
                self._redirect("/settings?reset=1")
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _handle_settings(self) -> None:
            form: dict[str, list[str]] = {}
            try:
                form = self._read_form()
                active_tab, restart_fields = save_settings_form(
                    form,
                    config_provider(),
                    repository,
                )
            except ValueError as error:
                web_logger.info(
                    "Web config validation failed from "
                    f"{self.client_address[0]}: {error}"
                )
                self._send_html(
                    render_settings_page(
                        config_provider(),
                        query={"tab": _first_form_value(form, "tab") or "tv"},
                        error_message=str(error),
                    ),
                    HTTPStatus.BAD_REQUEST,
                )
                return

            web_logger.info(f"Web config settings saved from {self.client_address[0]}")
            self._redirect(settings_redirect(active_tab, restart_fields))

        def _read_form(self) -> dict[str, list[str]]:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8")
            return parse_qs(raw_body, keep_blank_values=True)

        def _send_html(
            self,
            html: str,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            body = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, payload: dict[str, str]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_css(self, css: str) -> None:
            body = css.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, location: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

    return ThreadingHTTPServer((host, port), ConfigRequestHandler)


def _first_form_value(form: dict[str, list[str]], name: str) -> str | None:
    values = form.get(name)
    if not values:
        return None
    return values[0]
