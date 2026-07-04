import ssl
import unittest

from src.runtime.web_app import _mdns_host, _web_app_port
from src.shared.config import AppConfig, WebConfig


class WebAppTests(unittest.TestCase):
    def test_web_app_uses_https_port_when_default_web_port_is_unchanged(
        self,
    ) -> None:
        self.assertEqual(
            _web_app_port(AppConfig(), ssl.create_default_context()),
            443,
        )

    def test_web_app_keeps_explicit_web_port_for_https(self) -> None:
        config = AppConfig(web=WebConfig(port=8443))

        self.assertEqual(
            _web_app_port(config, ssl.create_default_context()),
            8443,
        )

    def test_web_app_keeps_http_port_without_tls(self) -> None:
        self.assertEqual(_web_app_port(AppConfig(), None), 80)

    def test_mdns_host_does_not_duplicate_local_suffix(self) -> None:
        self.assertEqual(_mdns_host("GestureTvRemote"), "gesturetvremote.local")
        self.assertEqual(_mdns_host("GestureTvRemote.local"), "gesturetvremote.local")


if __name__ == "__main__":
    unittest.main()
