import unittest

from src.shared.config import AppConfig
from src.web.assets import read_app_css
from src.web.settings.forms import config_from_form
from src.web.settings.templates import render_config_page
from src.web.settings.view import changed_restart_fields
from tests.helpers.config_helpers import app_config


class ConfigWebTests(unittest.TestCase):
    def test_settings_page_renders_tabbed_tv_settings_by_default(self) -> None:
        html = render_config_page(app_config(tv_adapter="roku", tv_host="10.0.0.60"))

        self.assertIn('class="settings-tab active"', html)
        self.assertIn('href="/settings?tab=gesture"', html)
        self.assertIn("Connection", html)
        self.assertIn("Advanced TV Integration", html)
        self.assertIn("Applies live", html)
        self.assertIn("Requires restart", html)
        self.assertIn('option value="roku" selected', html)
        self.assertIn('option value="appletv"', html)
        self.assertIn("Appletv Storage File", html)
        self.assertIn('value="10.0.0.60"', html)

    def test_settings_page_renders_selected_camera_tab(self) -> None:
        html = render_config_page(AppConfig(), active_tab="camera")

        self.assertIn('name="tab" value="camera"', html)
        self.assertIn("Camera Input", html)
        self.assertIn("Advanced Auto Zoom", html)
        self.assertNotIn("Advanced TV Integration", html)

    def test_settings_page_renders_restart_prompt_when_available(self) -> None:
        html = render_config_page(
            AppConfig(),
            restart_fields=("tv_host",),
            restart_available=True,
        )

        self.assertIn("Restart required", html)
        self.assertIn("Changed settings: Tv Host.", html)
        self.assertIn('action="/restart"', html)

    def test_settings_page_renders_restart_unavailable_message(self) -> None:
        html = render_config_page(
            AppConfig(),
            restart_fields=("tv_host",),
            restart_available=False,
        )

        self.assertIn("Restart the active runtime from the terminal.", html)
        self.assertNotIn('action="/restart"', html)

    def test_partial_tab_form_saves_only_posted_settings(self) -> None:
        base_config = app_config(tv_host="10.0.0.60", webcam_index=2)

        config = config_from_form({"tv_host": ["10.0.0.61"]}, base_config)

        self.assertEqual(config.tv.host, "10.0.0.61")
        self.assertEqual(config.camera.webcam_index, 2)

    def test_restart_impact_detects_only_restart_required_changes(self) -> None:
        before = app_config(tv_host="10.0.0.60", camera_zoom=1.0)
        after = app_config(tv_host="10.0.0.61", camera_zoom=2.0)

        self.assertEqual(changed_restart_fields(before, after), ("tv_host",))

    def test_settings_form_rejects_invalid_config(self) -> None:
        with self.assertRaisesRegex(ValueError, "tv_host must not be empty"):
            config_from_form({"tv_host": [" "]}, AppConfig())

    def test_config_css_contains_settings_navigation(self) -> None:
        css = read_app_css()

        self.assertIn(".settings-tabs", css)
        self.assertIn(".advanced-section", css)
        self.assertIn(".restart-prompt", css)


if __name__ == "__main__":
    unittest.main()
