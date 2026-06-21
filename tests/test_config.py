import unittest
from pathlib import Path

from src.shared.config import DEFAULT_CONFIG, EnvVar, load_config_from_env


class ConfigTests(unittest.TestCase):
    def test_load_config_uses_defaults_when_env_is_empty(self) -> None:
        config = load_config_from_env({})

        self.assertEqual(config.tv_adapter, DEFAULT_CONFIG.tv_adapter)
        self.assertEqual(config.tv_host, DEFAULT_CONFIG.tv_host)
        self.assertEqual(config.config_db_file, DEFAULT_CONFIG.config_db_file)
        self.assertEqual(config.webcam_index, DEFAULT_CONFIG.webcam_index)
        self.assertEqual(config.android_cert_file, DEFAULT_CONFIG.android_cert_file)
        self.assertEqual(config.model_file, DEFAULT_CONFIG.model_file)

    def test_load_config_applies_env_overrides(self) -> None:
        config = load_config_from_env(
            {
                EnvVar.TV_ADAPTER: "samsung",
                EnvVar.TV_HOST: "10.0.0.25",
                EnvVar.CONFIG_DB_FILE: "local/config.sqlite3",
                EnvVar.WEBCAM_INDEX: "2",
                EnvVar.CAMERA_ZOOM: "1.5",
                EnvVar.AUTO_ZOOM_ENABLED: "true",
                EnvVar.AUTO_ZOOM_MIN: "1.1",
                EnvVar.AUTO_ZOOM_MAX: "2.4",
                EnvVar.AUTO_ZOOM_PADDING: "0.5",
                EnvVar.AUTO_ZOOM_SMOOTHING: "0.25",
                EnvVar.ANDROID_CERT_FILE: "local/android/cert.pem",
                EnvVar.ANDROID_KEY_FILE: "local/android/key.pem",
                EnvVar.SAMSUNG_TOKEN_FILE: "local/samsung/token.txt",
                EnvVar.SAMSUNG_PORT: "8001",
                EnvVar.WEBOS_CLIENT_KEY_FILE: "local/webos/client_key.txt",
                EnvVar.ROKU_PORT: "8061",
                EnvVar.MODEL_DOWNLOAD_TIMEOUT_SECONDS: "3.5",
                EnvVar.MODEL_DOWNLOAD_RETRIES: "4",
                EnvVar.DEBOUNCE_SECONDS: "0.25",
                EnvVar.POINTER_DISTANCE_RATIO: "0.5",
                EnvVar.VOLUME_MAX_DISTANCE: "0.3",
                EnvVar.REQUIRE_UPRIGHT_HANDS: "false",
                EnvVar.HAND_UPRIGHT_MAX_TILT_RATIO: "0.5",
                EnvVar.PRIMARY_LOST_GRACE_SECONDS: "0.45",
                EnvVar.PRIMARY_MATCH_MAX_DISTANCE: "0.25",
            }
        )

        self.assertEqual(config.tv_adapter, "samsung")
        self.assertEqual(config.tv_host, "10.0.0.25")
        self.assertEqual(config.config_db_file, Path("local/config.sqlite3"))
        self.assertEqual(config.webcam_index, 2)
        self.assertEqual(config.camera_zoom, 1.5)
        self.assertTrue(config.auto_zoom_enabled)
        self.assertEqual(config.auto_zoom_min, 1.1)
        self.assertEqual(config.auto_zoom_max, 2.4)
        self.assertEqual(config.auto_zoom_padding, 0.5)
        self.assertEqual(config.auto_zoom_smoothing, 0.25)
        self.assertEqual(config.android_cert_file, Path("local/android/cert.pem"))
        self.assertEqual(config.android_key_file, Path("local/android/key.pem"))
        self.assertEqual(config.samsung_token_file, Path("local/samsung/token.txt"))
        self.assertEqual(config.samsung_port, 8001)
        self.assertEqual(
            config.webos_client_key_file,
            Path("local/webos/client_key.txt"),
        )
        self.assertEqual(config.roku_port, 8061)
        self.assertEqual(config.model_download_timeout_seconds, 3.5)
        self.assertEqual(config.model_download_retries, 4)
        self.assertEqual(config.debounce_seconds, 0.25)
        self.assertEqual(config.pointer_distance_ratio, 0.5)
        self.assertEqual(config.volume_max_distance, 0.3)
        self.assertFalse(config.require_upright_hands)
        self.assertEqual(config.hand_upright_max_tilt_ratio, 0.5)
        self.assertEqual(config.primary_lost_grace_seconds, 0.45)
        self.assertEqual(config.primary_match_max_distance, 0.25)

    def test_load_config_rejects_invalid_boolean(self) -> None:
        with self.assertRaisesRegex(ValueError, EnvVar.AUTO_ZOOM_ENABLED):
            load_config_from_env({EnvVar.AUTO_ZOOM_ENABLED: "maybe"})

    def test_load_config_rejects_unknown_adapter(self) -> None:
        with self.assertRaisesRegex(ValueError, "tv_adapter"):
            load_config_from_env({EnvVar.TV_ADAPTER: "unknown"})

    def test_load_config_rejects_empty_host(self) -> None:
        with self.assertRaisesRegex(ValueError, "tv_host"):
            load_config_from_env({EnvVar.TV_HOST: " "})

    def test_load_config_rejects_invalid_adapter_port(self) -> None:
        with self.assertRaisesRegex(ValueError, "roku_port"):
            load_config_from_env({EnvVar.ROKU_PORT: "0"})

    def test_load_config_rejects_camera_zoom_below_one(self) -> None:
        with self.assertRaisesRegex(ValueError, "camera_zoom"):
            load_config_from_env({EnvVar.CAMERA_ZOOM: "0.9"})

    def test_load_config_rejects_auto_zoom_max_below_min(self) -> None:
        with self.assertRaisesRegex(ValueError, "auto_zoom_max"):
            load_config_from_env(
                {
                    EnvVar.AUTO_ZOOM_MIN: "2.0",
                    EnvVar.AUTO_ZOOM_MAX: "1.5",
                }
            )

    def test_load_config_rejects_confidence_outside_unit_interval(self) -> None:
        with self.assertRaisesRegex(ValueError, "min_tracking_confidence"):
            load_config_from_env({EnvVar.MIN_TRACKING_CONFIDENCE: "1.2"})

    def test_load_config_rejects_invalid_model_download_settings(self) -> None:
        with self.assertRaisesRegex(ValueError, "model_download_timeout_seconds"):
            load_config_from_env({EnvVar.MODEL_DOWNLOAD_TIMEOUT_SECONDS: "0"})


if __name__ == "__main__":
    unittest.main()
