import unittest
from unittest.mock import patch

from src.shared.config import AppConfig
from src.web.assets import (
    read_app_css,
    read_gesture_js,
    read_remote_js,
    read_text_input_js,
)
from src.web.gesture.templates import render_gesture_page
from src.web.remote.templates import render_remote_page


class GestureWebTests(unittest.TestCase):
    def test_gesture_page_renders_browser_capture_assets(self) -> None:
        with patch("src.web.gesture.templates.time.time_ns", return_value=123456789):
            html = render_gesture_page(AppConfig(app_name="Gesture Test"))

        self.assertIn("Gesture Test", html)
        self.assertIn("/static/app.css", html)
        self.assertIn("/static/gesture.js?v=123456789", html)
        self.assertIn('id="preview"', html)
        self.assertIn('id="overlay"', html)
        self.assertIn('href="/remote"', html)
        self.assertIn('href="/settings"', html)

    def test_gesture_static_assets_are_available(self) -> None:
        self.assertIn("getUserMedia", read_gesture_js())
        self.assertIn("isSecureContext", read_gesture_js())
        self.assertIn("/api/log/client", read_gesture_js())
        self.assertIn("/api/gesture/debug", read_gesture_js())
        self.assertIn("debug stream connected", read_gesture_js())
        self.assertIn("devicePixelRatio", read_gesture_js())
        self.assertIn("setTransform(1, 0, 0, 1, 0, 0)", read_gesture_js())
        self.assertIn("latestDebug?.displayCrop", read_gesture_js())
        self.assertIn("layoutPreviewFrame", read_gesture_js())
        self.assertIn("containedPreviewArea", read_gesture_js())
        self.assertIn("preview.style.left", read_gesture_js())
        self.assertIn("crop.x * videoWidth", read_gesture_js())
        self.assertIn("pointToCropPixels", read_gesture_js())
        self.assertIn("/api/gesture/layout", read_gesture_js())
        self.assertIn("postLayoutMetrics", read_gesture_js())
        self.assertIn("motionScaleX", read_gesture_js())
        self.assertIn("motionScaleY", read_gesture_js())
        self.assertIn("xMotionDistanceToCropPixels", read_gesture_js())
        self.assertIn("yMotionDistanceToCropPixels", read_gesture_js())
        self.assertIn("overlayContext.ellipse", read_gesture_js())
        self.assertIn("scaleX(-1)", read_app_css())
        self.assertIn("object-fit: fill", read_app_css())
        self.assertIn("transform-origin: center center", read_app_css())
        self.assertIn("height: 100dvh", read_app_css())
        self.assertIn("overflow: hidden", read_app_css())
        self.assertIn("z-index: 2", read_app_css())
        self.assertIn(".gesture-panel", read_app_css())

    def test_remote_page_renders_direct_remote_assets(self) -> None:
        with patch("src.web.remote.templates.time.time_ns", return_value=123456789):
            html = render_remote_page(AppConfig(app_name="Gesture Test"))

        self.assertIn("Gesture Test", html)
        self.assertIn("/static/app.css", html)
        self.assertIn("/static/remote.js?v=123456789", html)
        self.assertIn('data-command="DPAD_CENTER"', html)
        self.assertIn('data-command-options="POWER_TOGGLE POWER_OFF POWER_ON"', html)
        self.assertIn('data-mode="touchpad"', html)
        self.assertIn('id="touchpad"', html)
        self.assertIn('href="/gesture"', html)
        self.assertIn('href="/settings"', html)

    def test_remote_static_assets_are_available(self) -> None:
        self.assertIn("/api/remote/capabilities", read_remote_js())
        self.assertIn("/api/remote/commands", read_remote_js())
        self.assertIn("[data-command]", read_remote_js())
        self.assertIn("[data-command-options]", read_remote_js())
        self.assertIn("[data-mode]", read_remote_js())
        self.assertIn("commandFromTouch", read_remote_js())
        self.assertIn("commandForButton", read_remote_js())
        self.assertIn("restoreKeyboardCaptureFocus", read_remote_js())
        self.assertIn("window.focusTvKeyboardCapture", read_remote_js())
        self.assertIn("dismissKeyboardCapture", read_remote_js())
        self.assertIn("window.dismissTvKeyboardCapture", read_remote_js())
        self.assertIn("keyboardDismissCommands", read_remote_js())
        self.assertIn(".remote-shell", read_app_css())
        self.assertIn(".remote-touchpad", read_app_css())
        self.assertIn(".remote-dpad", read_app_css())

    def test_text_input_asset_syncs_visible_overlay_value(self) -> None:
        script = read_text_input_js()

        css = read_app_css()
        self.assertIn('"input"', script)
        self.assertIn("tvKeyboardOverlay", script)
        self.assertIn("TV_SYNC_DELAY_MS = 650", script)
        self.assertIn("showTvKeyboardOverlay", script)
        self.assertIn("hideTvKeyboardOverlay", script)
        self.assertIn("resetTvTextSession", script)
        self.assertIn("handleTvCaptureValueChanged", script)
        self.assertIn("commitTvCaptureValue", script)
        self.assertIn("scheduleTvSync", script)
        self.assertIn("flushTvSyncNow", script)
        self.assertIn("/api/remote/text/sync", script)
        self.assertIn("queueTvSubmit()", script)
        self.assertIn("tvManualTextEnabled", script)
        self.assertIn("shouldEnableManualTextCapture()", script)
        self.assertIn('focusDetection !== "implemented"', script)
        self.assertIn('browserCapture === "hardware_keys"', script)
        self.assertIn('browserCapture === "auto_focus"', script)
        self.assertIn('browserCapture !== "auto_focus"', script)
        self.assertIn('"pointerup"', script)
        self.assertIn('"click"', script)
        self.assertIn('"blur"', script)
        self.assertIn('"focusout"', script)
        self.assertIn('"visibilitychange"', script)
        self.assertIn("force: true", script)
        self.assertIn("isTvTextCaptureEnabled()", script)
        self.assertIn("window.focusTvKeyboardCapture", script)
        self.assertIn("window.isTvTextCaptureEnabled", script)
        self.assertIn("window.dismissTvKeyboardCapture", script)
        self.assertIn("isTvKeyboardDismissTarget", script)
        self.assertIn("keyboard overlay shown", script)
        self.assertIn("keyboard overlay hidden", script)
        self.assertIn("POWER_TOGGLE", script)
        self.assertIn("keyboard capture focus requested", script)
        self.assertIn("keyboard capture capabilities loaded", script)
        self.assertIn("keyboard capture blurred", script)
        self.assertIn("keyboard capture focused", script)
        self.assertIn("keyboard capture focusout", script)
        self.assertIn("keyboard capture visibility changed", script)
        self.assertIn("/api/log/client", script)
        self.assertIn(".tv-keyboard-overlay", css)
        self.assertIn(".tv-keyboard-overlay.active", css)
        self.assertIn("top: max(12px, env(safe-area-inset-top))", css)
        self.assertIn("z-index: 1000", css)
        self.assertNotIn("queueTvCaptureDiff", script)
        self.assertNotIn("visualViewport", script)
        self.assertNotIn("keyboard text held for commit", script)
        self.assertNotIn("canLiveReplaceTvText", script)
        self.assertNotIn("startsWith(previousValue)", script)
        self.assertNotIn("keyboard text substitution ignored", script)
        self.assertNotIn("beforeinput", script)

    def test_shared_app_css_is_dark_and_contains_navigation(self) -> None:
        css = read_app_css()

        self.assertIn("color-scheme: dark", css)
        self.assertIn(".app-nav", css)
        self.assertIn(".nav-link.active", css)


if __name__ == "__main__":
    unittest.main()
