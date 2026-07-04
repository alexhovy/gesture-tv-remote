from typing import Any
from urllib.parse import parse_qs, urlencode

from src.application.ports.config_provider import ConfigStorePort
from src.shared.config import AppConfig
from src.web.settings.forms import config_from_form
from src.web.settings.templates import (
    render_config_page,
    reset_status_message,
    saved_status_message,
)
from src.web.settings.view import changed_restart_fields, tab_by_slug


def render_settings_page(
    config: AppConfig,
    *,
    query: Any,
    error_message: str | None = None,
    status_message_override: str | None = None,
    restart_available: bool = False,
) -> str:
    message = status_message_override
    if message is None and error_message is None:
        message = status_message(query)
    return render_config_page(
        config,
        active_tab=active_tab(query),
        status_message=message,
        error_message=error_message,
        restart_fields=restart_fields(query),
        restart_available=restart_available,
    )


def save_settings_form(
    form: dict[str, list[str]],
    current_config: AppConfig,
    repository: ConfigStorePort,
) -> tuple[str, tuple[str, ...]]:
    selected_tab = tab_by_slug(_first_form_value(form, "tab"))
    config = config_from_form(form, current_config)
    changed_fields = changed_restart_fields(current_config, config)
    repository.save_config(config)
    return selected_tab.slug, changed_fields


def settings_redirect(active_tab: str, changed_restart_fields: tuple[str, ...]) -> str:
    params: list[tuple[str, str]] = [("tab", active_tab), ("saved", "1")]
    params.extend(("restart", field) for field in changed_restart_fields)
    return f"/settings?{urlencode(params)}"


def status_message(query: Any) -> str | None:
    params = _query_values(query)
    if "saved" in params:
        return saved_status_message(restart_fields(query))
    if "reset" in params:
        return reset_status_message()
    return None


def active_tab(query: Any) -> str:
    return tab_by_slug(_first_query_value(query, "tab")).slug


def restart_fields(query: Any) -> tuple[str, ...]:
    return tuple(_query_values(query).get("restart", ()))


def form_tab(form: dict[str, list[str]]) -> str:
    return tab_by_slug(_first_form_value(form, "tab")).slug


def _first_query_value(query: Any, name: str) -> str | None:
    return _first_form_value(_query_values(query), name)


def _query_values(query: Any) -> dict[str, list[str]]:
    if isinstance(query, str):
        return parse_qs(query)
    values: dict[str, list[str]] = {}
    for key in query:
        raw_values = query.getall(key) if hasattr(query, "getall") else query.get(key)
        if raw_values is None:
            values[key] = []
        elif isinstance(raw_values, str):
            values[key] = [raw_values]
        else:
            values[key] = [str(value) for value in raw_values]
    return values


def _first_form_value(form: dict[str, list[str]], name: str) -> str | None:
    values = form.get(name)
    if not values:
        return None
    return values[0]
