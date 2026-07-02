from pathlib import Path

_STATIC_DIR = Path(__file__).with_name("static")
_CONFIG_CSS_FILE = _STATIC_DIR / "config.css"
_CONTROL_CSS_FILE = _STATIC_DIR / "control.css"
_CONTROL_JS_FILE = _STATIC_DIR / "control.js"


def read_config_css() -> str:
    return _CONFIG_CSS_FILE.read_text(encoding="utf-8")


def read_control_css() -> str:
    return _CONTROL_CSS_FILE.read_text(encoding="utf-8")


def read_control_js() -> str:
    return _CONTROL_JS_FILE.read_text(encoding="utf-8")
