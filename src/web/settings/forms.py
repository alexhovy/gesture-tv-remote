from pathlib import Path
from typing import Any

from src.shared.config import (
    CONFIG_FIELDS,
    AppConfig,
    get_config_value,
    replace_config_value,
    validate_config,
)

BOOLEAN_FIELD_MARKER = "__present_bool"


def config_from_form(
    form: dict[str, list[str]],
    base_config: AppConfig,
) -> AppConfig:
    config = base_config
    present_bool_fields = set(form.get(BOOLEAN_FIELD_MARKER, []))
    for field in CONFIG_FIELDS:
        current_value = get_config_value(config, field.name)
        raw_value = _first_form_value(form, field.name)
        if isinstance(current_value, bool):
            if field.name in present_bool_fields:
                config = replace_config_value(config, field.name, raw_value is not None)
            continue
        if raw_value is None:
            continue
        config = replace_config_value(
            config,
            field.name,
            _parse_field_value(field.name, raw_value, current_value),
        )

    validate_config(config)
    return config


def _first_form_value(form: dict[str, list[str]], name: str) -> str | None:
    values = form.get(name)
    if values is None:
        return None
    return values[0]


def _parse_field_value(name: str, raw_value: str, current_value: Any) -> Any:
    try:
        if isinstance(current_value, int):
            return int(raw_value)
        if isinstance(current_value, float):
            return float(raw_value)
        if isinstance(current_value, Path):
            return Path(raw_value)
        return raw_value
    except ValueError as error:
        raise ValueError(f"{name} has an invalid value") from error
