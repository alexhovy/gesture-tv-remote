from html import escape
from pathlib import Path
from string import Template

from src.shared.config import AppConfig, get_config_value
from src.web.settings.forms import BOOLEAN_FIELD_MARKER
from src.web.settings.view import (
    SECTIONS,
    TV_ADAPTERS,
    ConfigSection,
    field_applies_live,
    field_help,
    field_readonly,
    input_constraints,
)

_TEMPLATE_FILE = Path(__file__).parents[1] / "templates" / "config_page.html"


def render_config_page(
    config: AppConfig,
    status_message: str | None = None,
    error_message: str | None = None,
) -> str:
    status = ""
    if error_message:
        status = f'<div class="status error">{escape(error_message)}</div>'
    elif status_message:
        status = f'<div class="status">{escape(status_message)}</div>'

    sections_html = "\n".join(_render_section(config, section) for section in SECTIONS)
    return _load_page_template().substitute(
        page_title="Gesture TV Remote Config",
        heading="Gesture TV Remote Config",
        status=status,
        sections=sections_html,
    )


def saved_status_message() -> str:
    return (
        "Saved. Live settings reload automatically; "
        "integration changes require restart."
    )


def reset_status_message() -> str:
    return (
        "Reset. Live settings reload automatically; "
        "integration changes require restart."
    )


def _load_page_template() -> Template:
    return Template(_TEMPLATE_FILE.read_text(encoding="utf-8"))


def _render_section(config: AppConfig, section: ConfigSection) -> str:
    fields_html = "\n".join(_render_field(config, name) for name in section.fields)
    return f"""
      <section class="section" aria-labelledby="{_section_id(section.title)}">
        <div class="section-header">
          <div>
            <h2 id="{_section_id(section.title)}">{escape(section.title)}</h2>
            <p class="section-description">{escape(section.description)}</p>
          </div>
        </div>
        <div class="field-grid">
          {fields_html}
        </div>
      </section>"""


def _render_field(config: AppConfig, name: str) -> str:
    value = get_config_value(config, name)
    label = escape(name.replace("_", " ").title())
    field_id = f"field-{name}"
    help_id = f"{field_id}-help"
    help_text = field_help(name)
    help_html = (
        f'<p class="field-help" id="{help_id}">{escape(help_text)}</p>'
        if help_text
        else ""
    )
    described_by = f' aria-describedby="{help_id}"' if help_text else ""
    badge = _render_reload_badge(name)
    field_top = f"""
          <div class="field-top">
            <label for="{field_id}">{label}</label>
            {badge}
          </div>"""
    if isinstance(value, bool):
        checked = " checked" if value else ""
        return f"""
        <div class="field">
          {field_top}
          <input type="hidden" name="{BOOLEAN_FIELD_MARKER}" value="{escape(name)}">
          <span class="check">
            <input
              id="{field_id}"
              type="checkbox"
              name="{escape(name)}"{checked}{described_by}
            >
            <span>{_boolean_status(value)}</span>
          </span>
          {help_html}
        </div>"""
    if name == "tv_adapter":
        options = "\n".join(
            _render_option(adapter, adapter == value) for adapter in TV_ADAPTERS
        )
        return f"""
        <div class="field">
          {field_top}
          <select id="{field_id}" name="{escape(name)}"{described_by}>{options}</select>
          {help_html}
        </div>"""

    input_type = "number" if isinstance(value, int | float) else "text"
    step = ' step="any"' if isinstance(value, float) else ""
    readonly = " readonly" if field_readonly(name) else ""
    constraints = input_constraints(name)
    return f"""
        <div class="field">
          {field_top}
          <input
            id="{field_id}"
            type="{input_type}"
            name="{escape(name)}"
            value="{escape(str(value))}"{step}{constraints}{readonly}{described_by}
          >
          {help_html}
        </div>"""


def _render_option(value: str, selected: bool) -> str:
    selected_attribute = " selected" if selected else ""
    return (
        f'<option value="{escape(value)}"{selected_attribute}>'
        f"{escape(value)}</option>"
    )


def _render_reload_badge(name: str) -> str:
    if field_applies_live(name):
        return '<span class="badge live">Applies live</span>'
    return '<span class="badge restart">Requires restart</span>'


def _boolean_status(value: bool) -> str:
    return "Enabled" if value else "Disabled"


def _section_id(title: str) -> str:
    return "section-" + title.lower().replace(" ", "-")
