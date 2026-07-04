import time

from src.shared.config import AppConfig
from src.web.rendering import render_template


def render_remote_page(config: AppConfig) -> str:
    return render_template(
        "remote.html",
        active_page="remote",
        app_name=config.app_name,
        body_class="remote-page",
        cache_buster=str(time.time_ns()),
        page_title=f"{config.app_name} Remote",
    )
