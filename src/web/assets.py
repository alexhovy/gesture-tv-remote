from pathlib import Path

_STATIC_DIR = Path(__file__).with_name("static")
_CONFIG_CSS_FILE = _STATIC_DIR / "config.css"
_GESTURE_CSS_FILE = _STATIC_DIR / "gesture.css"
_GESTURE_JS_FILE = _STATIC_DIR / "gesture.js"
_REMOTE_CSS_FILE = _STATIC_DIR / "remote.css"
_REMOTE_JS_FILE = _STATIC_DIR / "remote.js"


def read_config_css() -> str:
    return _CONFIG_CSS_FILE.read_text(encoding="utf-8")


def read_gesture_css() -> str:
    return _GESTURE_CSS_FILE.read_text(encoding="utf-8")


def read_gesture_js() -> str:
    return _GESTURE_JS_FILE.read_text(encoding="utf-8")


def read_remote_css() -> str:
    return _REMOTE_CSS_FILE.read_text(encoding="utf-8")


def read_remote_js() -> str:
    return _REMOTE_JS_FILE.read_text(encoding="utf-8")
