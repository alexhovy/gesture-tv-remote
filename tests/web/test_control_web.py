import unittest

from src.shared.config import AppConfig
from src.web.control_templates import render_control_page
from src.web.static_files import read_control_css, read_control_js


class ControlWebTests(unittest.TestCase):
    def test_control_page_renders_browser_capture_assets(self) -> None:
        html = render_control_page(AppConfig(app_name="Gesture Test"))

        self.assertIn("Gesture Test", html)
        self.assertIn("/static/control.css", html)
        self.assertIn("/static/control.js", html)
        self.assertIn('id="preview"', html)

    def test_control_static_assets_are_available(self) -> None:
        self.assertIn("getUserMedia", read_control_js())
        self.assertIn("isSecureContext", read_control_js())
        self.assertIn("/api/log/client", read_control_js())
        self.assertIn(".control-shell", read_control_css())


if __name__ == "__main__":
    unittest.main()
