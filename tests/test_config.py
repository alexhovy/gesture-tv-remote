import unittest
from pathlib import Path

from src.shared.config import load_config_from_env


class ConfigTests(unittest.TestCase):
    def test_load_config_uses_defaults_when_env_is_empty(self) -> None:
        config = load_config_from_env({})

        self.assertEqual(config.tv_ip, "192.168.0.5")
        self.assertEqual(config.webcam_index, 0)
        self.assertEqual(config.cert_file, Path("certs/cert.pem"))
        self.assertEqual(config.model_file, Path("models/hand_landmarker.task"))

    def test_load_config_applies_env_overrides(self) -> None:
        config = load_config_from_env(
            {
                "GESTURE_TV_IP": "10.0.0.25",
                "GESTURE_TV_WEBCAM_INDEX": "2",
                "GESTURE_TV_CERT_FILE": "local/cert.pem",
                "GESTURE_TV_DEBOUNCE_SECONDS": "0.25",
            }
        )

        self.assertEqual(config.tv_ip, "10.0.0.25")
        self.assertEqual(config.webcam_index, 2)
        self.assertEqual(config.cert_file, Path("local/cert.pem"))
        self.assertEqual(config.debounce_seconds, 0.25)


if __name__ == "__main__":
    unittest.main()
