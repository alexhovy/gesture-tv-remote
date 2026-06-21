import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.infrastructure.data_access.sqlite_store import SqliteStore
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.shared.config import AppConfig


class ConfigRepositoryTests(unittest.TestCase):
    def test_get_config_returns_none_when_config_has_not_been_saved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = _repository(Path(temp_dir) / "config.sqlite3")

            self.assertIsNone(repository.get_config())

    def test_save_and_get_config_round_trips_typed_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "nested" / "config.sqlite3"
            repository = _repository(db_file)
            config = AppConfig(
                app_name="Local Remote",
                config_db_file=db_file,
                tv_adapter="roku",
                tv_host="10.0.0.42",
                roku_port=8061,
                webcam_index=2,
                camera_zoom=1.5,
                auto_zoom_enabled=False,
                debug_log_seconds=0.25,
            )

            repository.save_config(config)

            self.assertEqual(repository.get_config(), config)

    def test_save_config_replaces_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = _repository(Path(temp_dir) / "config.sqlite3")
            repository.save_config(AppConfig(tv_host="10.0.0.10"))

            repository.save_config(AppConfig(tv_host="10.0.0.20"))

            config = repository.get_config()
            self.assertIsNotNone(config)
            self.assertEqual(config.tv_host, "10.0.0.20")

    def test_reset_config_deletes_saved_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = _repository(Path(temp_dir) / "config.sqlite3")
            repository.save_config(AppConfig())

            repository.reset_config()

            self.assertIsNone(repository.get_config())

    def test_config_is_stored_with_typed_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "config.sqlite3"
            repository = _repository(db_file)
            repository.save_config(
                AppConfig(
                    app_name="Local Remote",
                    webcam_index=3,
                    camera_zoom=2.0,
                    auto_zoom_enabled=False,
                )
            )

            with sqlite3.connect(db_file) as connection:
                column_types = {
                    row[1]: row[2]
                    for row in connection.execute("PRAGMA table_info(app_config)")
                }
                stored_types = connection.execute(
                    """
                    SELECT
                        typeof(app_name),
                        typeof(webcam_index),
                        typeof(camera_zoom),
                        typeof(auto_zoom_enabled)
                    FROM app_config
                    WHERE id = 1
                    """
                ).fetchone()

            self.assertEqual(column_types["app_name"], "TEXT")
            self.assertEqual(column_types["webcam_index"], "INTEGER")
            self.assertEqual(column_types["camera_zoom"], "REAL")
            self.assertEqual(column_types["auto_zoom_enabled"], "INTEGER")
            self.assertEqual(stored_types, ("text", "integer", "real", "integer"))

    def test_get_config_adds_missing_columns_to_existing_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "config.sqlite3"
            with sqlite3.connect(db_file) as connection:
                connection.execute(
                    """
                    CREATE TABLE app_config (
                        id INTEGER PRIMARY KEY,
                        app_name TEXT NOT NULL,
                        tv_adapter TEXT NOT NULL,
                        tv_host TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO app_config (
                        id,
                        app_name,
                        tv_adapter,
                        tv_host,
                        updated_at
                    )
                    VALUES (1, 'Old Config', 'roku', '10.0.0.63', 'now')
                    """
                )

            config = _repository(db_file).get_config()

        self.assertIsNotNone(config)
        self.assertEqual(config.app_name, "Old Config")
        self.assertEqual(config.tv_adapter, "roku")
        self.assertEqual(config.tv_host, "10.0.0.63")
        self.assertEqual(config.config_web_port, 80)

    def test_save_config_rejects_invalid_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = _repository(Path(temp_dir) / "config.sqlite3")

            with self.assertRaisesRegex(ValueError, "tv_host"):
                repository.save_config(AppConfig(tv_host=" "))


def _repository(db_file: Path) -> ConfigRepository:
    return ConfigRepository(SqliteStore(db_file))


if __name__ == "__main__":
    unittest.main()
