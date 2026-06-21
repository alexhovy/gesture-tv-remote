import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.api.app import create_config_provider, load_config
from src.infrastructure.data_access.sqlite_store import SqliteStore
from src.infrastructure.repositories.config_repository import ConfigRepository
from src.shared.config import AppConfig, EnvVar


class AppConfigTests(unittest.TestCase):
    def test_load_config_uses_saved_config_from_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "config.sqlite3"
            ConfigRepository(SqliteStore(db_file)).save_config(
                AppConfig(
                    config_db_file=db_file,
                    tv_adapter="roku",
                    tv_host="10.0.0.50",
                    webcam_index=1,
                )
            )

            with patch.dict(
                os.environ,
                {EnvVar.CONFIG_DB_FILE: str(db_file)},
                clear=True,
            ):
                config = load_config()

        self.assertEqual(config.tv_adapter, "roku")
        self.assertEqual(config.tv_host, "10.0.0.50")
        self.assertEqual(config.webcam_index, 1)

    def test_load_config_applies_env_overrides_after_saved_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "config.sqlite3"
            ConfigRepository(SqliteStore(db_file)).save_config(
                AppConfig(
                    config_db_file=db_file,
                    tv_adapter="roku",
                    tv_host="10.0.0.50",
                    webcam_index=1,
                )
            )

            with patch.dict(
                os.environ,
                {
                    EnvVar.CONFIG_DB_FILE: str(db_file),
                    EnvVar.TV_HOST: "10.0.0.51",
                },
                clear=True,
            ):
                config = load_config()

        self.assertEqual(config.tv_adapter, "roku")
        self.assertEqual(config.tv_host, "10.0.0.51")
        self.assertEqual(config.webcam_index, 1)

    def test_config_provider_reads_saved_config_on_each_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "config.sqlite3"
            repository = ConfigRepository(SqliteStore(db_file))
            repository.save_config(AppConfig(config_db_file=db_file, camera_zoom=1.5))

            with patch.dict(
                os.environ,
                {EnvVar.CONFIG_DB_FILE: str(db_file)},
                clear=True,
            ):
                config_provider = create_config_provider()
                first_config = config_provider()

                repository.save_config(
                    AppConfig(config_db_file=db_file, camera_zoom=2.0)
                )
                second_config = config_provider()

        self.assertEqual(first_config.camera_zoom, 1.5)
        self.assertEqual(second_config.camera_zoom, 2.0)


if __name__ == "__main__":
    unittest.main()
