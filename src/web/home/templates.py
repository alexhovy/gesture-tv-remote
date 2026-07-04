from src.shared.config import AppConfig
from src.web.rendering import render_template


def render_home_page(config: AppConfig) -> str:
    return render_template(
        "home.html",
        active_page="home",
        app_name=config.app_name,
        body_class="home-page",
        page_title=config.app_name,
    )
