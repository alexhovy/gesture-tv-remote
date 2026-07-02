import ssl
import unittest

from src.runtime.browser_control_app import _browser_control_port, _mdns_host
from src.shared.config import AppConfig, WebConfig


class BrowserControlAppTests(unittest.TestCase):
    def test_browser_control_uses_https_port_when_default_web_port_is_unchanged(
        self,
    ) -> None:
        self.assertEqual(
            _browser_control_port(AppConfig(), ssl.create_default_context()),
            443,
        )

    def test_browser_control_keeps_explicit_web_port_for_https(self) -> None:
        config = AppConfig(web=WebConfig(port=8443))

        self.assertEqual(
            _browser_control_port(config, ssl.create_default_context()),
            8443,
        )

    def test_browser_control_keeps_http_port_without_tls(self) -> None:
        self.assertEqual(_browser_control_port(AppConfig(), None), 80)

    def test_mdns_host_does_not_duplicate_local_suffix(self) -> None:
        self.assertEqual(_mdns_host("GestureTvRemote"), "gesturetvremote.local")
        self.assertEqual(_mdns_host("GestureTvRemote.local"), "gesturetvremote.local")


if __name__ == "__main__":
    unittest.main()
