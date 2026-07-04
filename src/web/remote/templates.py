import time
from pathlib import Path
from string import Template

from src.shared.config import AppConfig

_REMOTE_TEMPLATE = Template(
    (Path(__file__).parents[1] / "templates" / "remote_page.html").read_text(
        encoding="utf-8"
    )
)


def render_remote_page(config: AppConfig) -> str:
    return _REMOTE_TEMPLATE.substitute(
        page_title=f"{config.app_name} Remote",
        heading=config.app_name,
        remote_cache_buster=str(time.time_ns()),
    )
