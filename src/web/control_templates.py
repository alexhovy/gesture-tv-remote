import time
from pathlib import Path
from string import Template

from src.shared.config import AppConfig

_CONTROL_TEMPLATE = Template(
    (Path(__file__).with_name("templates") / "control_page.html").read_text(
        encoding="utf-8"
    )
)


def render_control_page(config: AppConfig) -> str:
    return _CONTROL_TEMPLATE.substitute(
        control_cache_buster=str(time.time_ns()),
        page_title=f"{config.app_name} Control",
        heading=config.app_name,
    )
