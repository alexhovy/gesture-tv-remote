import unittest
from pathlib import Path

from src.shared.config import DEFAULT_CONFIG, EnvVar, load_config_from_env


class ConfigTests(unittest.TestCase):
    def test_load_config_uses_defaults_when_env_is_empty(self) -> None:
        config = load_config_from_env({})

        self.assertEqual(config.tv_ip, DEFAULT_CONFIG.tv_ip)
        self.assertEqual(config.webcam_index, DEFAULT_CONFIG.webcam_index)
        self.assertEqual(config.cert_file, DEFAULT_CONFIG.cert_file)
        self.assertEqual(config.model_file, DEFAULT_CONFIG.model_file)

    def test_load_config_applies_env_overrides(self) -> None:
        config = load_config_from_env(
            {
                EnvVar.TV_IP: "10.0.0.25",
                EnvVar.WEBCAM_INDEX: "2",
                EnvVar.CAMERA_ZOOM: "1.5",
                EnvVar.AUTO_ZOOM_ENABLED: "true",
                EnvVar.AUTO_ZOOM_MIN: "1.1",
                EnvVar.AUTO_ZOOM_MAX: "2.4",
                EnvVar.AUTO_ZOOM_PADDING: "0.5",
                EnvVar.AUTO_ZOOM_SMOOTHING: "0.25",
                EnvVar.CERT_FILE: "local/cert.pem",
                EnvVar.DEBOUNCE_SECONDS: "0.25",
                EnvVar.POINTER_DISTANCE_RATIO: "0.5",
                EnvVar.VOLUME_MAX_DISTANCE: "0.3",
                EnvVar.REQUIRE_UPRIGHT_HANDS: "false",
                EnvVar.HAND_UPRIGHT_MAX_TILT_RATIO: "0.5",
            }
        )

        self.assertEqual(config.tv_ip, "10.0.0.25")
        self.assertEqual(config.webcam_index, 2)
        self.assertEqual(config.camera_zoom, 1.5)
        self.assertTrue(config.auto_zoom_enabled)
        self.assertEqual(config.auto_zoom_min, 1.1)
        self.assertEqual(config.auto_zoom_max, 2.4)
        self.assertEqual(config.auto_zoom_padding, 0.5)
        self.assertEqual(config.auto_zoom_smoothing, 0.25)
        self.assertEqual(config.cert_file, Path("local/cert.pem"))
        self.assertEqual(config.debounce_seconds, 0.25)
        self.assertEqual(config.pointer_distance_ratio, 0.5)
        self.assertEqual(config.volume_max_distance, 0.3)
        self.assertFalse(config.require_upright_hands)
        self.assertEqual(config.hand_upright_max_tilt_ratio, 0.5)


if __name__ == "__main__":
    unittest.main()
