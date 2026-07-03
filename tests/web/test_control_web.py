import unittest
from unittest.mock import patch

from src.shared.config import AppConfig
from src.web.control_templates import render_control_page
from src.web.static_files import read_control_css, read_control_js


class ControlWebTests(unittest.TestCase):
    def test_control_page_renders_browser_capture_assets(self) -> None:
        with patch("src.web.control_templates.time.time_ns", return_value=123456789):
            html = render_control_page(AppConfig(app_name="Gesture Test"))

        self.assertIn("Gesture Test", html)
        self.assertIn("/static/control.css", html)
        self.assertIn("/static/control.js?v=123456789", html)
        self.assertIn('id="preview"', html)
        self.assertIn('id="overlay"', html)

    def test_control_static_assets_are_available(self) -> None:
        self.assertIn("getUserMedia", read_control_js())
        self.assertIn("isSecureContext", read_control_js())
        self.assertIn("/api/log/client", read_control_js())
        self.assertIn("/api/control/debug", read_control_js())
        self.assertIn("debug stream connected", read_control_js())
        self.assertIn("devicePixelRatio", read_control_js())
        self.assertIn("setTransform(1, 0, 0, 1, 0, 0)", read_control_js())
        self.assertIn("latestDebug?.displayCrop", read_control_js())
        self.assertIn("layoutPreviewFrame", read_control_js())
        self.assertIn("containedPreviewArea", read_control_js())
        self.assertIn("preview.style.left", read_control_js())
        self.assertIn("crop.x * videoWidth", read_control_js())
        self.assertIn("scaleX(-1)", read_control_css())
        self.assertIn("object-fit: fill", read_control_css())
        self.assertIn("transform-origin: center center", read_control_css())
        self.assertIn("height: 100dvh", read_control_css())
        self.assertIn("overflow: hidden", read_control_css())
        self.assertIn("z-index: 2", read_control_css())
        self.assertIn(".control-shell", read_control_css())


if __name__ == "__main__":
    unittest.main()
