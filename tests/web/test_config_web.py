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

    def test_model_file_setting_is_not_editable_from_settings_form(self) -> None:
        base_config = AppConfig()
        html = render_config_page(base_config, active_tab="system")

        self.assertIn('name="model_file"', html)
        self.assertIn('value="models/hand_landmarker.task" readonly', html)

        config = config_from_form(
            {"model_file": ["models/custom.task"]},
            base_config,
        )

        self.assertEqual(config.model.file, base_config.model.file)

    def test_model_url_and_web_tls_files_are_not_editable_from_settings_form(
        self,
    ) -> None:
        base_config = AppConfig()
        html = render_config_page(base_config, active_tab="system")

        self.assertIn('name="model_url"', html)
        self.assertIn('name="config_web_tls_cert_file"', html)
        self.assertIn('name="config_web_tls_key_file"', html)
        self.assertIn(
            (
                'value="https://storage.googleapis.com/mediapipe-models/'
                "hand_landmarker/hand_landmarker/float16/latest/"
                'hand_landmarker.task" readonly'
            ),
            html,
        )
        self.assertIn('value="certs/web/server.crt" readonly', html)
        self.assertIn('value="certs/web/server.key" readonly', html)

        config = config_from_form(
            {
                "model_url": ["https://example.test/custom.task"],
                "config_web_tls_cert_file": ["custom/server.crt"],
                "config_web_tls_key_file": ["custom/server.key"],
            },
            base_config,
        )

        self.assertEqual(config.model.url, base_config.model.url)
        self.assertEqual(config.web.tls_cert_file, base_config.web.tls_cert_file)
        self.assertEqual(config.web.tls_key_file, base_config.web.tls_key_file)

    def test_tv_credential_file_settings_are_not_editable_from_settings_form(
        self,
    ) -> None:
        base_config = AppConfig()
        html = render_config_page(base_config, active_tab="tv")

        self.assertIn('name="android_cert_file"', html)
        self.assertIn('name="android_key_file"', html)
        self.assertIn('name="samsung_token_file"', html)
        self.assertIn('name="webos_client_key_file"', html)
        self.assertIn('name="appletv_storage_file"', html)
        self.assertIn('value="certs/android/cert.pem" readonly', html)
        self.assertIn('value="certs/android/key.pem" readonly', html)
        self.assertIn('value="certs/samsung/token.txt" readonly', html)
        self.assertIn('value="certs/webos/client_key.txt" readonly', html)
        self.assertIn('value="certs/appletv/pyatv.json" readonly', html)

        config = config_from_form(
            {
                "android_cert_file": ["custom/android/cert.pem"],
                "android_key_file": ["custom/android/key.pem"],
                "samsung_token_file": ["custom/samsung/token.txt"],
                "webos_client_key_file": ["custom/webos/client_key.txt"],
                "appletv_storage_file": ["custom/appletv/pyatv.json"],
            },
            base_config,
        )

        self.assertEqual(config.tv.android_cert_file, base_config.tv.android_cert_file)
        self.assertEqual(config.tv.android_key_file, base_config.tv.android_key_file)
        self.assertEqual(
            config.tv.samsung_token_file,
            base_config.tv.samsung_token_file,
        )
        self.assertEqual(
            config.tv.webos_client_key_file,
            base_config.tv.webos_client_key_file,
        )
        self.assertEqual(
            config.tv.appletv_storage_file,
            base_config.tv.appletv_storage_file,
        )

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
