import json
from dataclasses import fields
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.infrastructure.data_access.sqlite_store import SqliteStore
from src.infrastructure.network.mdns import MdnsPublisher
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.shared.config import AppConfig, load_config_from_env
from src.shared.logging import AppLogger

_BOOLEAN_FIELD_MARKER = "__present_bool"
_READONLY_FIELDS = {"config_db_file"}
_TV_ADAPTERS = ("androidtv", "samsung", "webos", "roku")


def create_config_server(
    repository: ConfigRepository,
    host: str = AppConfig.config_web_host,
    port: int = AppConfig.config_web_port,
) -> ThreadingHTTPServer:
    class ConfigRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            request_url = urlparse(self.path)
            path = request_url.path
            if path == "/":
                self._send_html(
                    _render_config_page(
                        _effective_config(repository),
                        status_message=_status_message(request_url.query),
                    )
                )
                return
            if path == "/health":
                self._send_json({"status": "ok"})
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
                config = _config_from_form(form, _effective_config(repository))
                repository.save_config(config)
            except ValueError as error:
                self._send_html(
                    _render_config_page(
                        _effective_config(repository),
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

        def _redirect(self, location: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

    return ThreadingHTTPServer((host, port), ConfigRequestHandler)


def run_config_server(
    host: str | None = None,
    port: int | None = None,
) -> None:
    bootstrap_config = load_config_from_env()
    repository = ConfigRepository(SqliteStore(bootstrap_config.config_db_file))
    config = _effective_config(repository)
    bind_host = config.config_web_host if host is None else host
    bind_port = config.config_web_port if port is None else port
    server = create_config_server(repository, bind_host, bind_port)
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


def _config_from_form(
    form: dict[str, list[str]],
    base_config: AppConfig,
) -> AppConfig:
    config_values = {}
    present_bool_fields = set(form.get(_BOOLEAN_FIELD_MARKER, []))
    for field in fields(AppConfig):
        current_value = getattr(base_config, field.name)
        raw_value = _first_form_value(form, field.name)
        if isinstance(current_value, bool):
            if field.name in present_bool_fields:
                config_values[field.name] = raw_value is not None
            else:
                config_values[field.name] = current_value
            continue
        if raw_value is None:
            config_values[field.name] = current_value
            continue
        config_values[field.name] = _parse_field_value(
            field.name,
            raw_value,
            current_value,
        )

    return AppConfig(**config_values)


def _first_form_value(form: dict[str, list[str]], name: str) -> str | None:
    values = form.get(name)
    if values is None:
        return None
    return values[0]


def _parse_field_value(name: str, raw_value: str, current_value: Any) -> Any:
    try:
        if isinstance(current_value, int):
            return int(raw_value)
        if isinstance(current_value, float):
            return float(raw_value)
        if isinstance(current_value, Path):
            return Path(raw_value)
        return raw_value
    except ValueError as error:
        raise ValueError(f"{name} has an invalid value") from error


def _render_config_page(
    config: AppConfig,
    status_message: str | None = None,
    error_message: str | None = None,
) -> str:
    status = ""
    if error_message:
        status = f'<div class="status error">{escape(error_message)}</div>'
    elif status_message:
        status = f'<div class="status">{escape(status_message)}</div>'

    fields_html = "\n".join(
        _render_field(config, field.name) for field in fields(AppConfig)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gesture TV Remote Config</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #667085;
      --line: #d7dce2;
      --accent: #14745f;
      --danger: #b42318;
      font-family: Arial, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      margin-bottom: 18px;
    }}
    h1 {{ font-size: 28px; line-height: 1.2; margin: 0; }}
    .status {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 6px;
      padding: 10px 12px;
      margin-bottom: 14px;
      color: var(--muted);
    }}
    .error {{ border-color: #f3b0aa; color: var(--danger); }}
    form {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      padding: 18px;
    }}
    label {{ display: grid; gap: 7px; font-size: 13px; color: var(--muted); }}
    input, select {{
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
      color: var(--ink);
      background: #fff;
    }}
    input[readonly] {{ background: #eef1f4; color: var(--muted); }}
    .check {{ display: flex; align-items: center; gap: 10px; min-height: 38px; }}
    .check input {{ width: 18px; min-height: 18px; }}
    .actions {{
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      border-top: 1px solid var(--line);
      padding: 14px 18px;
    }}
    button {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 14px;
      font: inherit;
      background: #fff;
      color: var(--ink);
      cursor: pointer;
    }}
    button.primary {{
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
    }}
    button.danger {{ color: var(--danger); }}
    @media (max-width: 640px) {{
      main {{ padding: 14px; }}
      header, .actions {{ align-items: stretch; flex-direction: column; }}
      button {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Gesture TV Remote Config</h1>
    </header>
    {status}
    <form method="post" action="/settings">
      <div class="grid">
        {fields_html}
      </div>
      <div class="actions">
        <button class="primary" type="submit">Save</button>
        <button class="danger" type="submit" formaction="/reset">Reset</button>
      </div>
    </form>
  </main>
</body>
</html>
"""


def _render_field(config: AppConfig, name: str) -> str:
    value = getattr(config, name)
    label = escape(name.replace("_", " ").title())
    if isinstance(value, bool):
        checked = " checked" if value else ""
        return f"""
        <label>
          {label}
          <input type="hidden" name="{_BOOLEAN_FIELD_MARKER}" value="{escape(name)}">
          <span class="check">
            <input type="checkbox" name="{escape(name)}"{checked}>
          </span>
        </label>"""
    if name == "tv_adapter":
        options = "\n".join(
            _render_option(adapter, adapter == value) for adapter in _TV_ADAPTERS
        )
        return f"""
        <label>
          {label}
          <select name="{escape(name)}">{options}</select>
        </label>"""

    input_type = "number" if isinstance(value, int | float) else "text"
    step = ' step="any"' if isinstance(value, float) else ""
    readonly = " readonly" if name in _READONLY_FIELDS else ""
    return f"""
        <label>
          {label}
          <input
            type="{input_type}"
            name="{escape(name)}"
            value="{escape(str(value))}"{step}{readonly}
          >
        </label>"""


def _render_option(value: str, selected: bool) -> str:
    selected_attribute = " selected" if selected else ""
    return (
        f'<option value="{escape(value)}"{selected_attribute}>'
        f"{escape(value)}</option>"
    )


def _status_message(query: str) -> str | None:
    params = parse_qs(query)
    if "saved" in params:
        return "Saved. Restart gesture runtime to apply."
    if "reset" in params:
        return "Reset. Restart gesture runtime to apply."
    return None
