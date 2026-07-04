from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).with_name("templates")
_ENVIRONMENT = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(("html", "xml")),
)


def render_template(template_name: str, **context: Any) -> str:
    return _ENVIRONMENT.get_template(template_name).render(**context)
