import http.client
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from src.infrastructure.data_access.sqlite_store import SqliteStore
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.shared.config import AppConfig, load_config_from_env
from src.web.config_app import create_config_server


class ConfigWebTests(unittest.TestCase):
    def test_health_returns_ok(self) -> None:
        with _running_config_server() as client:
            response = client.request("GET", "/health")

        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, '{"status": "ok"}')

    def test_home_renders_saved_config(self) -> None:
        with _running_config_server(
            AppConfig(tv_adapter="roku", tv_host="10.0.0.60")
        ) as client:
            response = client.request("GET", "/")

        self.assertEqual(response.status, 200)
        self.assertIn('option value="roku" selected', response.body)
        self.assertIn('value="10.0.0.60"', response.body)

    def test_settings_post_saves_config(self) -> None:
        with _running_config_server() as client:
            response = client.post_form("/settings", {"tv_host": "10.0.0.61"})

            saved_config = client.repository.get_config()

        self.assertEqual(response.status, 303)
        self.assertIsNotNone(saved_config)
        self.assertEqual(saved_config.tv_host, "10.0.0.61")

    def test_settings_post_rejects_invalid_config(self) -> None:
        with _running_config_server() as client:
            response = client.post_form("/settings", {"tv_host": " "})

            saved_config = client.repository.get_config()

        self.assertEqual(response.status, 400)
        self.assertIsNone(saved_config)
        self.assertIn("tv_host must not be empty", response.body)

    def test_reset_post_deletes_saved_config(self) -> None:
        with _running_config_server(AppConfig(tv_host="10.0.0.62")) as client:
            response = client.post_form("/reset", {})

            saved_config = client.repository.get_config()

        self.assertEqual(response.status, 303)
        self.assertIsNone(saved_config)


class _ConfigWebClient:
    def __init__(
        self,
        server: ThreadingHTTPServer,
        repository: ConfigRepository,
    ) -> None:
        self._server = server
        self.repository = repository

    def request(self, method: str, path: str, body: str | None = None) -> "_Response":
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            self._server.server_port,
            timeout=5,
        )
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return _Response(
                status=response.status,
                body=response.read().decode("utf-8"),
            )
        finally:
            connection.close()

    def post_form(self, path: str, values: dict[str, str]) -> "_Response":
        return self.request("POST", path, urlencode(values))


class _Response:
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body


class _running_config_server:
    def __init__(self, saved_config: AppConfig | None = None) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._env_patch = patch.dict(os.environ, {}, clear=True)
        db_file = Path(self._temp_dir.name) / "config.sqlite3"
        self.repository = ConfigRepository(SqliteStore(db_file))
        if saved_config is not None:
            self.repository.save_config(saved_config)
        self._server = create_config_server(
            self.repository,
            self._effective_config,
            "127.0.0.1",
            0,
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
        )

    def _effective_config(self) -> AppConfig:
        saved_config = self.repository.get_config()
        return load_config_from_env(base_config=saved_config or AppConfig())

    def __enter__(self) -> _ConfigWebClient:
        self._env_patch.__enter__()
        self._thread.start()
        return _ConfigWebClient(self._server, self.repository)

    def __exit__(self, *args: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
        self._env_patch.__exit__(*args)
        self._temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
