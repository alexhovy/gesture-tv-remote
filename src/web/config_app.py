import json
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.infrastructure.repositories.config_repository import ConfigRepository
from src.shared.config import AppConfig
from src.web.config_forms import config_from_form
from src.web.config_templates import (
    render_config_page,
    reset_status_message,
    saved_status_message,
)
from src.web.static_files import read_config_css

ConfigProvider = Callable[[], AppConfig]


def create_config_server(
    repository: ConfigRepository,
    config_provider: ConfigProvider,
    host: str = AppConfig().web.host,
    port: int = AppConfig().web.port,
) -> ThreadingHTTPServer:
    class ConfigRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            request_url = urlparse(self.path)
            path = request_url.path
            if path == "/":
                self._send_html(
                    render_config_page(
                        config_provider(),
                        status_message=_status_message(request_url.query),
                    )
                )
                return
            if path == "/health":
                self._send_json({"status": "ok"})
                return
            if path == "/static/config.css":
                self._send_css(read_config_css())
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/settings":
                self._handle_settings()
                return
            if path == "/reset":
                repository.reset_config()
                self._redirect("/?reset=1")
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _handle_settings(self) -> None:
            try:
                form = self._read_form()
                config = config_from_form(form, config_provider())
                repository.save_config(config)
            except ValueError as error:
                self._send_html(
                    render_config_page(
                        config_provider(),
                        error_message=str(error),
                    ),
                    HTTPStatus.BAD_REQUEST,
                )
                return

            self._redirect("/?saved=1")

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


def _status_message(query: str) -> str | None:
    params = parse_qs(query)
    if "saved" in params:
        return saved_status_message()
    if "reset" in params:
        return reset_status_message()
    return None
