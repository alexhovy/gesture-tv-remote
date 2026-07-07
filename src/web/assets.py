from pathlib import Path

_STATIC_DIR = Path(__file__).with_name("static")
_APP_CSS_FILE = _STATIC_DIR / "app.css"
_GESTURE_JS_FILE = _STATIC_DIR / "gesture.js"
_REMOTE_JS_FILE = _STATIC_DIR / "remote.js"
_TEXT_INPUT_JS_FILE = _STATIC_DIR / "text-input.js"


def static_dir() -> Path:
    return _STATIC_DIR


def read_app_css() -> str:
    return _APP_CSS_FILE.read_text(encoding="utf-8")


def read_gesture_js() -> str:
    return _GESTURE_JS_FILE.read_text(encoding="utf-8")


def read_remote_js() -> str:
    return _REMOTE_JS_FILE.read_text(encoding="utf-8")


def read_text_input_js() -> str:
    return _TEXT_INPUT_JS_FILE.read_text(encoding="utf-8")
