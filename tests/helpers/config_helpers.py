from typing import Any

from src.shared.config import AppConfig, replace_config_value


def app_config(**field_values: Any) -> AppConfig:
    config = AppConfig()
    for name, value in field_values.items():
        config = replace_config_value(config, name, value)
    return config
