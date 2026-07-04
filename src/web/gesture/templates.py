import time

from src.shared.config import AppConfig
from src.web.rendering import render_template


def render_gesture_page(config: AppConfig) -> str:
    return render_template(
        "gesture.html",
        active_page="gesture",
        app_name=config.app_name,
        body_class="gesture-page",
        cache_buster=str(time.time_ns()),
        page_title=f"{config.app_name} Gesture",
    )
