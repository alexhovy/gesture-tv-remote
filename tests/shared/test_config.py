import unittest
from pathlib import Path

from src.shared.config import (
    DEFAULT_CONFIG,
    EnvVar,
    apply_reloadable_config,
    load_config_from_env,
)
from tests.helpers.config_helpers import app_config


class ConfigTests(unittest.TestCase):
    def test_load_config_uses_defaults_when_env_is_empty(self) -> None:
        config = load_config_from_env({})

        self.assertEqual(config.tv.adapter, DEFAULT_CONFIG.tv.adapter)
        self.assertEqual(config.tv.host, DEFAULT_CONFIG.tv.host)
        self.assertEqual(config.config_db_file, DEFAULT_CONFIG.config_db_file)
        self.assertEqual(config.camera.webcam_index, DEFAULT_CONFIG.camera.webcam_index)
        self.assertEqual(
            config.tv.android_cert_file, DEFAULT_CONFIG.tv.android_cert_file
        )
        self.assertEqual(config.model.file, DEFAULT_CONFIG.model.file)
        self.assertEqual(config.tv.voice_input_target, "auto")

    def test_load_config_applies_env_overrides(self) -> None:
        config = load_config_from_env(
            {
                EnvVar.TV_ADAPTER: "samsung",
                EnvVar.TV_HOST: "10.0.0.25",
                EnvVar.CONFIG_DB_FILE: "local/config.sqlite3",
                EnvVar.CONFIG_WEB_HOST: "127.0.0.1",
                EnvVar.CONFIG_WEB_PORT: "9000",
                EnvVar.CONFIG_WEB_MDNS_ENABLED: "false",
                EnvVar.CONFIG_WEB_MDNS_NAME: "livingroomremote",
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
                EnvVar.APPLETV_STORAGE_FILE: "local/appletv/pyatv.json",
                EnvVar.VOICE_INPUT_TARGET: "remote_search",
                EnvVar.MODEL_DOWNLOAD_TIMEOUT_SECONDS: "3.5",
                EnvVar.MODEL_DOWNLOAD_RETRIES: "4",
                EnvVar.DEBOUNCE_SECONDS: "0.25",
                EnvVar.POINTER_SCREEN_RADIUS_RATIO: "0.12",
                EnvVar.VOLUME_MAX_DISTANCE: "0.3",
                EnvVar.REQUIRE_UPRIGHT_HANDS: "false",
                EnvVar.HAND_UPRIGHT_MAX_TILT_RATIO: "0.5",
                EnvVar.FIST_HOLD_HOME_SECONDS: "0.65",
                EnvVar.ACTIVE_HAND_LOST_GRACE_SECONDS: "0.45",
                EnvVar.ACTIVE_HAND_MATCH_MAX_DISTANCE: "0.25",
                EnvVar.VERBOSE_PIPELINE_DIAGNOSTICS: "true",
                EnvVar.METRICS_LOG_SECONDS: "1.5",
            }
        )

        self.assertEqual(config.tv.adapter, "samsung")
        self.assertEqual(config.tv.host, "10.0.0.25")
        self.assertEqual(config.config_db_file, Path("local/config.sqlite3"))
        self.assertEqual(config.web.host, "127.0.0.1")
        self.assertEqual(config.web.port, 9000)
        self.assertFalse(config.web.mdns_enabled)
        self.assertEqual(config.web.mdns_name, "livingroomremote")
        self.assertEqual(config.camera.webcam_index, 2)
        self.assertEqual(config.camera.zoom, 1.5)
        self.assertTrue(config.camera.auto_zoom_enabled)
        self.assertEqual(config.camera.auto_zoom_min, 1.1)
        self.assertEqual(config.camera.auto_zoom_max, 2.4)
        self.assertEqual(config.camera.auto_zoom_padding, 0.5)
        self.assertEqual(config.camera.auto_zoom_smoothing, 0.25)
        self.assertEqual(config.tv.android_cert_file, Path("local/android/cert.pem"))
        self.assertEqual(config.tv.android_key_file, Path("local/android/key.pem"))
        self.assertEqual(config.tv.samsung_token_file, Path("local/samsung/token.txt"))
        self.assertEqual(config.tv.samsung_port, 8001)
        self.assertEqual(
            config.tv.webos_client_key_file,
            Path("local/webos/client_key.txt"),
        )
        self.assertEqual(config.tv.roku_port, 8061)
        self.assertEqual(
            config.tv.appletv_storage_file,
            Path("local/appletv/pyatv.json"),
        )
        self.assertEqual(config.tv.voice_input_target, "remote_search")
        self.assertEqual(config.model.download_timeout_seconds, 3.5)
        self.assertEqual(config.model.download_retries, 4)
        self.assertEqual(config.gesture.debounce_seconds, 0.25)
        self.assertEqual(config.gesture.fist_hold_home_seconds, 0.65)
        self.assertEqual(config.gesture.pointer_screen_radius_ratio, 0.12)
        self.assertEqual(config.gesture.volume_max_distance, 0.3)
        self.assertFalse(config.gesture.require_upright_hands)
        self.assertEqual(config.gesture.hand_upright_max_tilt_ratio, 0.5)
        self.assertEqual(config.gesture.active_hand_lost_grace_seconds, 0.45)
        self.assertEqual(config.gesture.active_hand_match_max_distance, 0.25)
        self.assertTrue(config.debug.verbose_pipeline_diagnostics)
        self.assertEqual(config.performance.metrics_log_seconds, 1.5)

    def test_load_config_applies_env_overrides_to_base_config(self) -> None:
        base_config = app_config(
            tv_adapter="roku",
            tv_host="10.0.0.40",
            webcam_index=1,
            camera_zoom=1.5,
        )

        config = load_config_from_env(
            {
                EnvVar.TV_HOST: "10.0.0.41",
                EnvVar.CAMERA_ZOOM: "2.0",
            },
            base_config=base_config,
        )

        self.assertEqual(config.tv.adapter, "roku")
        self.assertEqual(config.tv.host, "10.0.0.41")
        self.assertEqual(config.camera.webcam_index, 1)
        self.assertEqual(config.camera.zoom, 2.0)

    def test_apply_reloadable_config_keeps_restart_required_fields(self) -> None:
        current = app_config(
            tv_adapter="samsung",
            tv_host="10.0.0.10",
            webcam_index=0,
            camera_zoom=1.0,
            debug_log_seconds=0.5,
        )
        latest = app_config(
            tv_adapter="roku",
            tv_host="10.0.0.20",
            webcam_index=2,
            camera_zoom=2.0,
            debug_log_seconds=0.1,
        )

        config = apply_reloadable_config(current, latest)

        self.assertEqual(config.tv.adapter, "samsung")
        self.assertEqual(config.tv.host, "10.0.0.10")
        self.assertEqual(config.camera.webcam_index, 0)
        self.assertEqual(config.camera.zoom, 2.0)
        self.assertEqual(config.debug.log_seconds, 0.1)

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

    def test_load_config_rejects_unknown_voice_input_target(self) -> None:
        with self.assertRaisesRegex(ValueError, "voice_input_target"):
            load_config_from_env({EnvVar.VOICE_INPUT_TARGET: "assistant"})

    def test_load_config_rejects_invalid_config_web_port(self) -> None:
        with self.assertRaisesRegex(ValueError, "config_web_port"):
            load_config_from_env({EnvVar.CONFIG_WEB_PORT: "0"})

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

    def test_load_config_rejects_max_hands_below_two(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_hands"):
            load_config_from_env({EnvVar.MAX_HANDS: "1"})

    def test_load_config_rejects_invalid_model_download_settings(self) -> None:
        with self.assertRaisesRegex(ValueError, "model_download_timeout_seconds"):
            load_config_from_env({EnvVar.MODEL_DOWNLOAD_TIMEOUT_SECONDS: "0"})

    def test_load_config_rejects_invalid_metrics_log_seconds(self) -> None:
        with self.assertRaisesRegex(ValueError, "metrics_log_seconds"):
            load_config_from_env({EnvVar.METRICS_LOG_SECONDS: "-1"})


if __name__ == "__main__":
    unittest.main()
