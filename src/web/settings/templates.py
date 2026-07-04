from html import escape

from markupsafe import Markup

from src.shared.config import AppConfig, get_config_value
from src.web.rendering import render_template
from src.web.settings.forms import BOOLEAN_FIELD_MARKER
from src.web.settings.view import (
    TABS,
    ConfigGroup,
    ConfigTab,
    field_applies_live,
    field_help,
    field_label,
    field_readonly,
    input_constraints,
    select_options,
    tab_by_slug,
)


def render_config_page(
    config: AppConfig,
    active_tab: str | None = None,
    status_message: str | None = None,
    error_message: str | None = None,
    restart_fields: tuple[str, ...] = (),
    restart_available: bool = False,
) -> str:
    selected_tab = tab_by_slug(active_tab)
    status = ""
    if error_message:
        status = f'<div class="status error">{escape(error_message)}</div>'
    elif status_message:
        status = f'<div class="status">{escape(status_message)}</div>'

    tabs_html = _render_tabs(selected_tab)
    groups_html = "\n".join(
        _render_group(config, group) for group in selected_tab.groups
    )
    restart_html = _render_restart_prompt(restart_fields, restart_available)
    return render_template(
        "settings.html",
        active_page="settings",
        app_name=config.app_name,
        body_class="settings-page",
        page_title=f"{config.app_name} Settings",
        selected_tab=selected_tab.slug,
        tabs=Markup(tabs_html),
        status=Markup(status),
        sections=Markup(groups_html),
        restart_prompt=Markup(restart_html),
    )


def saved_status_message(restart_fields: tuple[str, ...] = ()) -> str:
    if not restart_fields:
        return "Saved. Live settings apply automatically."
    field_names = ", ".join(field_label(name) for name in restart_fields)
    return f"Saved. Restart required for: {field_names}."


def reset_status_message() -> str:
    return "Reset. Restart the active runtime so all default settings take effect."


def _render_tabs(active_tab: ConfigTab) -> str:
    tab_links = "\n".join(_render_tab_link(tab, tab == active_tab) for tab in TABS)
    return (
        '<nav class="settings-tabs" aria-label="Settings sections">'
        f"{tab_links}</nav>"
    )


def _render_tab_link(tab: ConfigTab, selected: bool) -> str:
    active_class = " active" if selected else ""
    aria_current = ' aria-current="page"' if selected else ""
    return (
        f'<a class="settings-tab{active_class}" href="/settings?tab={escape(tab.slug)}"'
        f"{aria_current}>"
        f"<span>{escape(tab.title)}</span>"
        f"<small>{escape(tab.description)}</small>"
        "</a>"
    )


def _render_group(config: AppConfig, group: ConfigGroup) -> str:
    fields_html = "\n".join(_render_field(config, name) for name in group.fields)
    content = f"""
        <div class="section-header">
          <div>
            <h2 id="{_section_id(group.title)}">{escape(group.title)}</h2>
            <p class="section-description">{escape(group.description)}</p>
          </div>
        </div>
        <div class="field-grid">
          {fields_html}
        </div>"""
    if group.advanced:
        return f"""
      <details class="section advanced-section">
        <summary>
          <span>{escape(group.title)}</span>
          <small>{escape(group.description)}</small>
        </summary>
        <div class="advanced-content">
          <div class="field-grid">
            {fields_html}
          </div>
        </div>
      </details>"""
    return f"""
      <section class="section" aria-labelledby="{_section_id(group.title)}">
        {content}
      </section>"""


def _render_field(config: AppConfig, name: str) -> str:
    value = get_config_value(config, name)
    label = escape(field_label(name))
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
    options_values = select_options(name)
    if options_values:
        options = "\n".join(
            _render_option(option, option == value) for option in options_values
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


def _render_restart_prompt(
    restart_fields: tuple[str, ...],
    restart_available: bool,
) -> str:
    if not restart_fields:
        return ""
    field_names = ", ".join(field_label(name) for name in restart_fields)
    action = (
        '<form method="post" action="/restart">'
        '<button class="button warning" type="submit">Restart runtime</button>'
        "</form>"
        if restart_available
        else (
            '<span class="restart-unavailable">'
            "Restart the active runtime from the terminal.</span>"
        )
    )
    return f"""
    <aside class="restart-prompt" aria-live="polite">
      <div>
        <h2>Restart required</h2>
        <p>Changed settings: {escape(field_names)}.</p>
      </div>
      {action}
    </aside>"""


def _boolean_status(value: bool) -> str:
    return "Enabled" if value else "Disabled"


def _section_id(title: str) -> str:
    return "section-" + title.lower().replace(" ", "-")
