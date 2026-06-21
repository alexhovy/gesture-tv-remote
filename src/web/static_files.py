from pathlib import Path

_STATIC_DIR = Path(__file__).with_name("static")
_CONFIG_CSS_FILE = _STATIC_DIR / "config.css"


def read_config_css() -> str:
    return _CONFIG_CSS_FILE.read_text(encoding="utf-8")
