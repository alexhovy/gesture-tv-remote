import time
from pathlib import Path
from string import Template

from src.shared.config import AppConfig

_GESTURE_TEMPLATE = Template(
    (Path(__file__).parents[1] / "templates" / "gesture_page.html").read_text(
        encoding="utf-8"
    )
)


def render_gesture_page(config: AppConfig) -> str:
    return _GESTURE_TEMPLATE.substitute(
        gesture_cache_buster=str(time.time_ns()),
        page_title=f"{config.app_name} Gesture",
        heading=config.app_name,
    )
